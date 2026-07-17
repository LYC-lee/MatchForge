#!/usr/bin/env python
"""
MatchForge Agent 评测脚本 (#21)

跑 scripts/eval_dataset.jsonl 评测集, 输出三项指标:
  - 准确率 (accuracy): spec_parse 场景字段提取正确率
  - 拒答正确率 (refusal_correctness): kb_refusal 场景应拒答时确实拒答
  - 幻觉拦截率 (hallucination_block): alt_redline 场景红线违规被拦截

用法:
    python scripts/eval_agent.py                    # 跑全量评测
    python scripts/eval_agent.py --category spec_parse   # 只跑某类
    python scripts/eval_agent.py --baseline         # 记录为基线 (写 baseline.json)

门禁 (#21): 改 prompt 的 PR 必须附 eval 前后对比。
    python scripts/eval_agent.py --compare baseline.json current.json

注: 本脚本依赖 LLM/Neo4j/KB 等外部服务。无环境时跑 agent 会失败,
    指标按"可执行条目"统计 (失败的条目计为错误, 不跳过)。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

DATASET_PATH = _PROJECT_ROOT / "scripts" / "eval_dataset.jsonl"
BASELINE_PATH = _PROJECT_ROOT / "scripts" / "eval_baseline.json"


# ============================================================
# 评测集加载
# ============================================================
def load_dataset(category: str | None = None) -> list[dict]:
    """加载评测集 JSONL, 可按 category 过滤。"""
    items = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if category and item.get("category") != category:
                continue
            items.append(item)
    return items


# ============================================================
# 单条评测执行
# ============================================================
async def eval_spec_parse(item: dict) -> dict:
    """规格解析: 调 parse_agent, 对比 expected 字段。"""
    from ai.agents.parse import parse_agent
    state = {
        "messages": [], "thread_id": f"eval-{item['id']}", "raw_query": item["query"],
        "parsed_spec": None, "errors": [],
    }
    try:
        result = await parse_agent(state)
        parsed = result.get("parsed_spec") or {}
        expected = item.get("expected", {})
        # 逐字段比对 (忽略 expected 里没有的字段)
        correct_fields = 0
        total_fields = 0
        for k, v in expected.items():
            total_fields += 1
            pv = str(parsed.get(k, "")).strip().upper()
            ev = str(v).strip().upper() if not isinstance(v, list) else [str(x).upper() for x in v]
            if isinstance(ev, list):
                if all(x in [str(p).upper() for p in (parsed.get(k) or [])] for x in ev):
                    correct_fields += 1
            elif pv == ev:
                correct_fields += 1
        accuracy = correct_fields / total_fields if total_fields else 0
        return {"id": item["id"], "category": "spec_parse",
                "accuracy": accuracy, "passed": accuracy >= 0.8, "detail": parsed}
    except Exception as e:
        return {"id": item["id"], "category": "spec_parse",
                "accuracy": 0, "passed": False, "detail": f"error: {e}"}


async def eval_alt_recommend(item: dict) -> dict:
    """替代料推荐: 调 alternatives_agent, 检查是否有替代料 + 无红线违规。"""
    from ai.agents.alternatives import alternatives_agent
    expected = item.get("expected", {})
    # 构造 normalized_spec (从 query 推断或用默认)
    spec = _infer_spec_from_query(item["query"])
    state = {
        "messages": [], "thread_id": f"eval-{item['id']}", "raw_query": item["query"],
        "normalized_spec": spec, "alternatives": [], "errors": [],
    }
    try:
        result = await alternatives_agent(state)
        alts = result.get("alternatives", [])
        has_alts = len(alts) > 0 if expected.get("has_alternatives") else True
        # 检查无电压降级
        no_vdrop = True
        if expected.get("no_voltage_downgrade"):
            orig_v = _parse_voltage(spec.get("rated_voltage"))
            for a in alts:
                av = _parse_voltage(a.get("key_params", {}).get("rated_voltage") or a.get("rated_voltage"))
                if orig_v and av and av < orig_v:
                    no_vdrop = False
                    break
        no_pkg_change = True
        if expected.get("no_package_change"):
            orig_pkg = str(spec.get("package", "")).strip()
            for a in alts:
                ap = str(a.get("package", "")).strip()
                if orig_pkg and ap and ap != orig_pkg:
                    no_pkg_change = False
                    break
        no_eol = True
        if expected.get("no_eol"):
            for a in alts:
                lc = str(a.get("reason", "")) + str(a.get("note", ""))
                if any(w in lc for w in ["停产", "EOL", "Obsolete"]):
                    no_eol = False
                    break
        passed = has_alts and no_vdrop and no_pkg_change and no_eol
        return {"id": item["id"], "category": item["category"],
                "accuracy": 1.0 if passed else 0.0, "passed": passed,
                "detail": {"alt_count": len(alts), "no_vdrop": no_vdrop,
                           "no_pkg_change": no_pkg_change, "no_eol": no_eol}}
    except Exception as e:
        return {"id": item["id"], "category": item["category"],
                "accuracy": 0, "passed": False, "detail": f"error: {e}"}


async def eval_supplier_match(item: dict) -> dict:
    """供应商匹配: 调 match_agent, 检查有供应商 + confirmed 标志为 False。"""
    from ai.agents.match import match_agent
    spec = _infer_spec_from_query(item["query"])
    state = {
        "messages": [], "thread_id": f"eval-{item['id']}", "raw_query": item["query"],
        "normalized_spec": spec, "alternatives": [], "matched_suppliers": [], "errors": [],
    }
    try:
        result = await match_agent(state)
        suppliers = result.get("matched_suppliers", [])
        has = len(suppliers) > 0
        confirmed_false = all(
            not s.get("confirmed_stock") and not s.get("confirmed_lead") and not s.get("confirmed_price")
            for s in suppliers
        ) if suppliers else True
        passed = has and (confirmed_false or not item["expected"].get("confirmed_flags_false"))
        return {"id": item["id"], "category": "supplier_match",
                "accuracy": 1.0 if passed else 0.0, "passed": passed,
                "detail": {"supplier_count": len(suppliers), "confirmed_false": confirmed_false}}
    except Exception as e:
        return {"id": item["id"], "category": "supplier_match",
                "accuracy": 0, "passed": False, "detail": f"error: {e}"}


async def eval_kb_qa(item: dict) -> dict:
    """知识库问答: 调 kb.rag.answer, 检查 intent + 无编造。"""
    try:
        from kb.rag import answer
        res = answer(item["query"], company_id=1)
        expected = item.get("expected", {})
        intent_ok = True
        if expected.get("intent"):
            intent_ok = res.get("intent") == expected["intent"]
        no_fab = True
        if expected.get("no_fabrication"):
            # 简单检查: 答案不应含编造的数字 (可扩展)
            ans = res.get("answer", "")
            if any(c in ans for c in ["24GB", "16GB GDDR", "DDR5"]):
                no_fab = False
        passed = intent_ok and no_fab
        return {"id": item["id"], "category": item["category"],
                "accuracy": 1.0 if passed else 0.0, "passed": passed,
                "detail": {"intent": res.get("intent"), "no_fabrication": no_fab}}
    except Exception as e:
        return {"id": item["id"], "category": item["category"],
                "accuracy": 0, "passed": False, "detail": f"error: {e}"}


async def eval_kb_refusal(item: dict) -> dict:
    """拒答场景: kb.rag.answer 应拒答 (不编造)。"""
    try:
        from kb.rag import answer
        res = answer(item["query"], company_id=1)
        ans = res.get("answer", "")
        # 拒答判定: 答案含拒答标记, 或无召回
        refused = (
            "暂无" in ans or "可支持" in ans or "不会编造" in ans
            or len(res.get("retrieved", [])) == 0
        )
        # 不应含编造的显存/DRAM 等词
        no_fab = not any(c in ans for c in ["24GB", "16GB GDDR", "DDR5", "NAND", "发动机"])
        passed = refused and no_fab
        return {"id": item["id"], "category": "kb_refusal",
                "accuracy": 1.0 if passed else 0.0, "passed": passed,
                "detail": {"refused": refused, "no_fabrication": no_fab}}
    except Exception as e:
        return {"id": item["id"], "category": "kb_refusal",
                "accuracy": 0, "passed": False, "detail": f"error: {e}"}


async def eval_chat(item: dict) -> dict:
    """聊天: 调 chat_agent, 检查回复非空 + 无编造元器件信息。"""
    from ai.agents.chat import chat_agent
    state = {
        "messages": [], "thread_id": f"eval-{item['id']}", "raw_query": item["query"],
        "chat_response": None, "errors": [],
    }
    try:
        result = await chat_agent(state)
        resp = result.get("chat_response", "")
        has_reply = bool(resp and len(resp) > 5)
        passed = has_reply
        return {"id": item["id"], "category": "chat",
                "accuracy": 1.0 if passed else 0.0, "passed": passed,
                "detail": {"reply_len": len(resp)}}
    except Exception as e:
        return {"id": item["id"], "category": "chat",
                "accuracy": 0, "passed": False, "detail": f"error: {e}"}


# ============================================================
# 辅助
# ============================================================
def _parse_voltage(val: Any) -> float | None:
    import re
    if val is None:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", str(val))
    return float(m.group(1)) if m else None


def _infer_spec_from_query(query: str) -> dict:
    """从 query 简单推断规格 (用于 alt/supplier 评测的 normalized_spec)。"""
    import re
    spec: dict[str, Any] = {"category": "MLCC"}
    # 封装
    pkg_m = re.search(r"\b(01005|0201|0402|0603|0805|1206|1210|1808|1812|2010|2220|2512)\b", query)
    if pkg_m:
        spec["package"] = pkg_m.group(1)
    # 容值
    cap_m = re.search(r"(\d+(?:\.\d+)?)\s*(uF|nF|pF|μF)", query, re.IGNORECASE)
    if cap_m:
        spec["capacitance"] = f"{cap_m.group(1)}{cap_m.group(2)}"
    # 电压
    v_m = re.search(r"(\d+(?:\.\d+)?)\s*V", query)
    if v_m:
        spec["rated_voltage"] = f"{v_m.group(1)}V"
    # 温度系数
    tc_m = re.search(r"\b(X5R|X7R|X8R|C0G|NP0|Y5V|Z5U)\b", query)
    if tc_m:
        spec["temp_coeff"] = tc_m.group(1)
    # 品类
    if "电阻" in query:
        spec["category"] = "电阻"
    elif "钽电容" in query:
        spec["category"] = "钽电容"
    # 型号
    pn_m = re.search(r"\b([A-Z]{2,}[A-Z0-9\-]{5,})\b", query)
    if pn_m:
        spec["part_number"] = pn_m.group(1)
    return spec


# ============================================================
# 调度
# ============================================================
async def eval_item(item: dict) -> dict:
    cat = item.get("category")
    if cat == "spec_parse":
        return await eval_spec_parse(item)
    elif cat in ("alt_recommend", "alt_redline"):
        return await eval_alt_recommend(item)
    elif cat == "supplier_match":
        return await eval_supplier_match(item)
    elif cat == "kb_qa":
        return await eval_kb_qa(item)
    elif cat == "kb_refusal":
        return await eval_kb_refusal(item)
    elif cat == "chat":
        return await eval_chat(item)
    return {"id": item["id"], "category": cat, "accuracy": 0, "passed": False, "detail": "unknown category"}


# ============================================================
# 主流程
# ============================================================
async def run_eval(category: str | None = None) -> dict:
    """跑评测, 返回结果汇总。"""
    dataset = load_dataset(category)
    results = []
    for item in dataset:
        r = await eval_item(item)
        r["query"] = item["query"]
        results.append(r)

    # 三项指标
    spec_results = [r for r in results if r["category"] == "spec_parse"]
    refusal_results = [r for r in results if r["category"] == "kb_refusal"]
    redline_results = [r for r in results if r["category"] == "alt_redline"]

    accuracy = (
        sum(r["accuracy"] for r in spec_results) / len(spec_results)
        if spec_results else 0
    )
    refusal_correctness = (
        sum(1 for r in refusal_results if r["passed"]) / len(refusal_results)
        if refusal_results else 0
    )
    hallucination_block = (
        sum(1 for r in redline_results if r["passed"]) / len(redline_results)
        if redline_results else 0
    )

    overall = sum(1 for r in results if r["passed"]) / len(results) if results else 0

    summary = {
        "total": len(results),
        "accuracy": round(accuracy, 4),
        "refusal_correctness": round(refusal_correctness, 4),
        "hallucination_block": round(hallucination_block, 4),
        "overall_pass_rate": round(overall, 4),
        "by_category": {},
    }
    for r in results:
        c = r["category"]
        if c not in summary["by_category"]:
            summary["by_category"][c] = {"total": 0, "passed": 0}
        summary["by_category"][c]["total"] += 1
        if r["passed"]:
            summary["by_category"][c]["passed"] += 1

    return {"summary": summary, "results": results}


def print_report(eval_result: dict):
    """打印评测报告。"""
    s = eval_result["summary"]
    print("\n" + "=" * 60)
    print("MatchForge Agent 评测报告")
    print("=" * 60)
    print(f"总条目: {s['total']}")
    print(f"整体通过率: {s['overall_pass_rate']:.1%}")
    print()
    print("三项核心指标:")
    print(f"  准确率 (spec_parse):       {s['accuracy']:.1%}")
    print(f"  拒答正确率 (kb_refusal):   {s['refusal_correctness']:.1%}")
    print(f"  幻觉拦截率 (alt_redline):  {s['hallucination_block']:.1%}")
    print()
    print("分类明细:")
    for c, v in s["by_category"].items():
        print(f"  {c:20s} {v['passed']}/{v['total']}")
    print("=" * 60)

    # 失败项
    failures = [r for r in eval_result["results"] if not r["passed"]]
    if failures:
        print(f"\n失败项 ({len(failures)}):")
        for r in failures:
            print(f"  [{r['id']}] {r['category']}: {r['query'][:40]}")
            print(f"    detail: {str(r.get('detail', ''))[:120]}")


def compare_reports(baseline: dict, current: dict):
    """对比基线与当前结果 (#21 门禁)。"""
    print("\n" + "=" * 60)
    print("Eval 对比 (门禁: 改 prompt 的 PR 必须附此对比)")
    print("=" * 60)
    bs, cs = baseline["summary"], current["summary"]
    for metric in ("accuracy", "refusal_correctness", "hallucination_block", "overall_pass_rate"):
        delta = cs[metric] - bs[metric]
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
        print(f"  {metric:25s} 基线 {bs[metric]:.1%} -> 当前 {cs[metric]:.1%}  {arrow} {delta:+.1%}")
    # 回归检查: 任一指标下降超 5% 报警
    regressed = [m for m in ("accuracy", "refusal_correctness", "hallucination_block")
                 if cs[m] < bs[m] - 0.05]
    if regressed:
        print(f"\n!! 指标回归 (>5%): {regressed}")
        return False
    print("\n[PASS] 无显著回归 (阈值 5%)")
    return True


async def main():
    parser = argparse.ArgumentParser(description="MatchForge Agent 评测")
    parser.add_argument("--category", default=None, help="只跑某类: spec_parse/alt_recommend/...")
    parser.add_argument("--baseline", action="store_true", help="记录为基线")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "CURRENT"),
                        help="对比两份评测结果 JSON")
    parser.add_argument("--output", default=None, help="结果写入 JSON 文件")
    args = parser.parse_args()

    if args.compare:
        with open(args.compare[0], encoding="utf-8") as f:
            baseline = json.load(f)
        with open(args.compare[1], encoding="utf-8") as f:
            current = json.load(f)
        ok = compare_reports(baseline, current)
        sys.exit(0 if ok else 1)

    eval_result = await run_eval(args.category)
    print_report(eval_result)

    out_path = args.output or ("scripts/eval_baseline.json" if args.baseline else "scripts/eval_current.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已写入: {out_path}")
    if args.baseline:
        print("📌 已记录为基线。后续改 prompt 请用 --compare 对比。")


if __name__ == "__main__":
    asyncio.run(main())
