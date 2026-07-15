"""
Agent ④ — 供应商匹配

流程:
  1. Milvus 向量召回 (按 spec 语义检索)
  2. MySQL 规则过滤 (品类 + 品牌 + 资质)
  3. 排序 (品牌覆盖度 + 资质等级 + 响应速度)
  4. LLM 生成匹配解释 (可选)

红线: 供应商必须来自 DB，首期库存/交期/价格一律标"未确认"

输出: matched_suppliers[]
"""

from __future__ import annotations

from ai.state import ProcureState
from ai.tools.mysql_client import filter_suppliers_raw
from ai.monitor import AgentLogger


async def match_agent(state: ProcureState) -> ProcureState:
    log = AgentLogger("match", thread_id=state.get("thread_id", ""))
    normalized_spec = state.get("normalized_spec") or {}
    alternatives = state.get("alternatives", [])

    if not normalized_spec:
        state["matched_suppliers"] = []
        return state

    log.start(state)

    try:
        category = normalized_spec.get("category", "")
        brands: list[str] = []
        for alt in alternatives:
            b = alt.get("brand", "")
            if b and b not in brands:
                brands.append(b)
        brand_pref = normalized_spec.get("brand_pref", [])
        if isinstance(brand_pref, list):
            for b in brand_pref:
                if b not in brands:
                    brands.append(b)

        suppliers = []
        if category:
            try:
                suppliers = filter_suppliers_raw(category=category, brands=brands if brands else None)
            except Exception as e:
                state.setdefault("errors", []).append(f"[match] MySQL 查询失败: {str(e)[:100]}")

        qual_rank = {"IATF16949": 3, "ISO14001": 2, "ISO9001": 2, "原厂授权": 3}

        def _rank(sup: dict) -> float:
            score = 0.0
            sup_brands = sup.get("brands", [])
            if isinstance(sup_brands, str):
                sup_brands = [b.strip() for b in sup_brands.split(",")]
            if brands:
                matched = sum(1 for b in brands if any(b.lower() in sb.lower() for sb in sup_brands))
                score += (matched / max(len(brands), 1)) * 0.4
            quals = sup.get("qualifications", [])
            if isinstance(quals, str):
                quals = [q.strip() for q in quals.split(",")]
            max_qual = 0
            for q in quals:
                for k, v in qual_rank.items():
                    if k.lower() in q.lower():
                        max_qual = max(max_qual, v)
            score += (max_qual / 3) * 0.3
            resp = sup.get("response_speed", "")
            if "24h" in resp or "12h" in resp:
                score += 0.2
            elif "48h" in resp:
                score += 0.1
            updated = sup.get("updated_at", "")
            if updated:
                try:
                    from datetime import datetime
                    days_ago = (datetime.now() - datetime.strptime(updated[:10], "%Y-%m-%d")).days
                    if days_ago < 30:
                        score += 0.1
                    elif days_ago < 90:
                        score += 0.05
                except Exception:
                    pass
            return score

        matched = []
        for s in suppliers:
            s_dict = dict(s) if hasattr(s, '_mapping') else s
            if isinstance(s_dict, dict):
                sup_score = _rank(s_dict)
                matched.append({
                    "id": str(s_dict.get("id", "")),
                    "name": s_dict.get("name", ""),
                    "score": sup_score,
                    "category": s_dict.get("category", category),
                    "region": s_dict.get("location", s_dict.get("region", "")),
                    "location": s_dict.get("location", s_dict.get("region", "")),
                    "categories": [s_dict.get("category", category)],
                    "brands": _ensure_list(s_dict.get("brands", [])),
                    "qualifications": _ensure_list(s_dict.get("qualifications", [])),
                    "moq": s_dict.get("moq", 0),
                    "lead_time_weeks": s_dict.get("lead_time_weeks", 0),
                    "in_stock": False,
                    "response_speed": _get_response_speed(s_dict.get("lead_time_weeks", 0)),
                    "data_source": s_dict.get("data_source", "平台数据"),
                    "updated_at": s_dict.get("updated_at", ""),
                    "confirmed_stock": False,
                    "confirmed_lead": False,
                    "confirmed_price": False,
                    "match_score": round(sup_score, 2),
                })

        matched.sort(key=lambda x: x["match_score"], reverse=True)
        for m in matched:
            if m["updated_at"]:
                try:
                    from datetime import datetime
                    days_ago = (datetime.now() - datetime.strptime(m["updated_at"][:10], "%Y-%m-%d")).days
                    if days_ago > 90:
                        m["data_source"] += " (信息可能过期)"
                except Exception:
                    pass

        state["matched_suppliers"] = matched
        log.end(state)

    except Exception as e:
        state.setdefault("errors", []).append(f"[match] {str(e)[:200]}")
        state["matched_suppliers"] = []
        log.fail(str(e)[:200])

    return state


# ecs_assistant 风格别名
process = match_agent


def _ensure_list(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [x.strip() for x in val.split(",") if x.strip()]
    return []


def _get_response_speed(lead_time_weeks: int) -> str:
    if lead_time_weeks <= 0:
        return "暂无数据"
    elif lead_time_weeks <= 1:
        return "24h 内首次响应"
    elif lead_time_weeks <= 2:
        return "48h 内首次响应"
    else:
        return "72h 内首次响应"