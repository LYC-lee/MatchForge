"""
语义切片器 (Semantic Chunker)。

不按固定字数机械切片。按语义边界:
  - 产品知识: 以 product_model 为重要边界, 切出 product_overview / product_specification /
    product_price / product_installation / product_procurement / product_faq / product_model_diff
  - 业务知识: 以 business_type 为重要边界, 切出 business_overview / business_process /
    business_sop / business_communication / business_exception / business_faq

每个 chunk 自带轻量上下文 (公司名 + 章节), 脱离手册仍可基本理解。
中英文独立切片, 不合并。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger("kb.chunker")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ctx(company_name: str, section: str, lang: str) -> str:
    """轻量上下文前缀。"""
    if lang == "en":
        return f"[{company_name} | {section}] "
    return f"[{company_name} | {section}] "


def chunk_product_manual(company_name: str, lang: str, manual_data: dict) -> list[dict]:
    """产品手册 -> 语义切片。"""
    chunks: list[dict] = []
    is_en = lang == "en"

    # company_overview / product_overview (手册级总览)
    products = manual_data.get("products", [])
    catalog = "; ".join(f"{p.get('product_name')} ({p.get('product_model')})" for p in products)
    if is_en:
        overview_text = (
            f"{company_name} product catalog: {catalog}. "
            f"Categories: {', '.join(sorted({p.get('category','') for p in products}))}."
        )
    else:
        overview_text = (
            f"{company_name} 产品目录：{catalog}。"
            f"品类：{', '.join(sorted({p.get('category','') for p in products}))}。"
        )
    chunks.append({
        "chunk_type": "product_overview",
        "section": "产品总览",
        "product_model": None,
        "business_type": None,
        "text": _ctx(company_name, "产品总览", lang) + overview_text,
    })

    for p in products:
        model = p.get("product_model")
        pname = p.get("product_name")
        ctx_model = _ctx(company_name, f"{pname}", lang)

        # overview
        chunks.append({
            "chunk_type": "product_overview",
            "section": f"{pname}-产品介绍",
            "product_model": model,
            "business_type": None,
            "text": ctx_model + p.get("overview", ""),
        })
        # specification
        spec = p.get("specification", {})
        spec_text = p.get("spec_text") or ("; ".join(f"{k}={v}" for k, v in spec.items()))
        if is_en:
            spec_full = f"{pname} ({model}) specifications: {spec_text}."
        else:
            spec_full = f"{pname}（{model}）规格参数：{spec_text}。"
        chunks.append({
            "chunk_type": "product_specification",
            "section": f"{pname}-规格",
            "product_model": model,
            "business_type": None,
            "text": ctx_model + spec_full,
        })
        # price
        pr = p.get("price", {})
        if pr.get("price") is not None or pr.get("price_min") is not None:
            if is_en:
                price_txt = (
                    f"{pname} ({model}) price: "
                    f"{pr.get('price_min','N/A')}~{pr.get('price_max','N/A')} {pr.get('currency','USD')} "
                    f"(type={pr.get('price_type','demo')}, confidence={pr.get('confidence',0.6)})."
                )
            else:
                price_txt = (
                    f"{pname}（{model}）价格："
                    f"{pr.get('price_min','N/A')}~{pr.get('price_max','N/A')} {pr.get('currency','USD')} "
                    f"（类型={pr.get('price_type','demo')}，置信度={pr.get('confidence',0.6)}）。"
                )
            chunks.append({
                "chunk_type": "product_price",
                "section": f"{pname}-价格",
                "product_model": model,
                "business_type": None,
                "text": ctx_model + price_txt,
            })
        # model differences
        if p.get("model_differences"):
            chunks.append({
                "chunk_type": "product_model",
                "section": f"{pname}-型号区别",
                "product_model": model,
                "business_type": None,
                "text": ctx_model + p.get("model_differences", ""),
            })
        # installation / usage
        if p.get("installation"):
            chunks.append({
                "chunk_type": "product_installation",
                "section": f"{pname}-安装使用",
                "product_model": model,
                "business_type": None,
                "text": ctx_model + p.get("installation", ""),
            })
        # procurement
        proc = p.get("procurement", {})
        if proc:
            if is_en:
                proc_txt = (
                    f"{pname} ({model}) procurement: MOQ={proc.get('moq','N/A')}; "
                    f"lead_time={proc.get('lead_time','N/A')}; payment={proc.get('payment','N/A')}; "
                    f"packaging={proc.get('packaging','N/A')}; customization={proc.get('customization','N/A')}."
                )
            else:
                proc_txt = (
                    f"{pname}（{model}）采购信息：MOQ={proc.get('moq','N/A')}；"
                    f"交期={proc.get('lead_time','N/A')}；付款={proc.get('payment','N/A')}；"
                    f"包装={proc.get('packaging','N/A')}；定制={proc.get('customization','N/A')}。"
                )
            chunks.append({
                "chunk_type": "product_procurement",
                "section": f"{pname}-采购",
                "product_model": model,
                "business_type": None,
                "text": ctx_model + proc_txt,
            })
        # faq
        for q in p.get("faq", []):
            chunks.append({
                "chunk_type": "product_faq",
                "section": f"{pname}-FAQ",
                "product_model": model,
                "business_type": None,
                "text": ctx_model + str(q),
            })

    # hash + dedupe within manual
    seen = set()
    out = []
    for c in chunks:
        c["content_hash"] = _hash(c["text"])
        if c["content_hash"] in seen:
            continue
        seen.add(c["content_hash"])
        out.append(c)
    return out


def chunk_business_manual(company_name: str, lang: str, manual_data: dict) -> list[dict]:
    """业务手册 -> 语义切片。"""
    chunks: list[dict] = []
    is_en = lang == "en"
    bts = manual_data.get("business_types", [])

    # business_overview 总览
    bt_list = ", ".join(b.get("business_type", "") for b in bts)
    if is_en:
        ov = f"{company_name} business types: {bt_list}."
    else:
        ov = f"{company_name} 业务类型：{bt_list}。"
    chunks.append({
        "chunk_type": "business_overview",
        "section": "业务总览",
        "product_model": None,
        "business_type": None,
        "text": _ctx(company_name, "业务总览", lang) + ov,
    })

    for b in bts:
        bt = b.get("business_type")
        ctx = _ctx(company_name, bt, lang)
        # overview = definition + applicable customers
        if is_en:
            ov_text = f"{bt}: {b.get('definition','')} Applicable customers: {b.get('applicable_customers','')}."
        else:
            ov_text = f"{bt}：{b.get('definition','')} 适用客户：{b.get('applicable_customers','')}。"
        chunks.append({
            "chunk_type": "business_overview",
            "section": f"{bt}-业务定义",
            "product_model": None,
            "business_type": bt,
            "text": ctx + ov_text,
        })
        # prerequisite
        pre = b.get("prerequisite_info", [])
        if pre:
            if is_en:
                pre_txt = f"{bt} prerequisite info: " + "; ".join(pre) + "."
            else:
                pre_txt = f"{bt} 前置信息：" + "；".join(pre) + "。"
            chunks.append({
                "chunk_type": "business_process",
                "section": f"{bt}-前置信息",
                "product_model": None,
                "business_type": bt,
                "text": ctx + pre_txt,
            })
        # process steps (SOP)
        steps = b.get("process_steps", [])
        if steps:
            if is_en:
                sop_txt = f"{bt} standard process: " + " ".join(steps)
            else:
                sop_txt = f"{bt} 标准流程：" + " ".join(steps)
            chunks.append({
                "chunk_type": "business_sop",
                "section": f"{bt}-标准流程",
                "product_model": None,
                "business_type": bt,
                "text": ctx + sop_txt,
            })
        # internal logic
        if b.get("internal_logic"):
            chunks.append({
                "chunk_type": "business_process",
                "section": f"{bt}-内部处理逻辑",
                "product_model": None,
                "business_type": bt,
                "text": ctx + b.get("internal_logic", ""),
            })
        # communication
        if b.get("communication"):
            chunks.append({
                "chunk_type": "business_communication",
                "section": f"{bt}-商务沟通",
                "product_model": None,
                "business_type": bt,
                "text": ctx + b.get("communication", ""),
            })
        # exceptions
        exc = b.get("exceptions", [])
        if exc:
            if is_en:
                exc_txt = f"{bt} exceptions: " + "; ".join(exc) + "."
            else:
                exc_txt = f"{bt} 异常情况：" + "；".join(exc) + "。"
            chunks.append({
                "chunk_type": "business_exception",
                "section": f"{bt}-异常情况",
                "product_model": None,
                "business_type": bt,
                "text": ctx + exc_txt,
            })
        # faq
        for q in b.get("faq", []):
            chunks.append({
                "chunk_type": "business_faq",
                "section": f"{bt}-FAQ",
                "product_model": None,
                "business_type": bt,
                "text": ctx + str(q),
            })

    seen = set()
    out = []
    for c in chunks:
        c["content_hash"] = _hash(c["text"])
        if c["content_hash"] in seen:
            continue
        seen.add(c["content_hash"])
        out.append(c)
    return out


def assemble_manual_markdown(company_name: str, manual_type: str, lang: str, data: dict) -> str:
    """把结构化知识组装成 Markdown 手册 (存入 KnowledgeManual.content)。"""
    is_en = lang == "en"
    title = data.get("manual_title", company_name)
    lines = [f"# {title}", ""]
    if manual_type == "product":
        for p in data.get("products", []):
            lines.append(f"## {p.get('product_name')}")
            lines.append(f"- 型号/Model: {p.get('product_model')}")
            lines.append(f"- 分类/Category: {p.get('category')}")
            lines.append(f"- 定位: {p.get('positioning')}")
            lines.append(f"\n### {'Overview' if is_en else '产品介绍'}\n{p.get('overview','')}")
            spec = p.get("specification", {})
            lines.append(f"\n### {'Specifications' if is_en else '规格参数'}")
            for k, v in spec.items():
                lines.append(f"- {k}: {v}")
            pr = p.get("price", {})
            if pr.get("price_min") is not None:
                lines.append(f"\n### {'Price' if is_en else '价格'}\n{pr.get('price_min')}~{pr.get('price_max')} {pr.get('currency')} (type={pr.get('price_type')})")
            if p.get("model_differences"):
                lines.append(f"\n### {'Model Differences' if is_en else '型号区别'}\n{p.get('model_differences')}")
            if p.get("installation"):
                lines.append(f"\n### {'Installation/Usage' if is_en else '安装使用'}\n{p.get('installation')}")
            proc = p.get("procurement", {})
            if proc:
                lines.append(f"\n### {'Procurement' if is_en else '采购信息'}")
                for k, v in proc.items():
                    lines.append(f"- {k}: {v}")
            faq = p.get("faq", [])
            if faq:
                lines.append(f"\n### FAQ")
                for q in faq:
                    lines.append(f"- {q}")
            lines.append("")
    else:
        for b in data.get("business_types", []):
            bt = b.get("business_type")
            lines.append(f"## {bt}")
            lines.append(f"\n### {'Definition' if is_en else '业务定义'}\n{b.get('definition','')}")
            lines.append(f"\n### {'Applicable Customers' if is_en else '适用客户'}\n{b.get('applicable_customers','')}")
            pre = b.get("prerequisite_info", [])
            if pre:
                lines.append(f"\n### {'Prerequisite' if is_en else '前置信息'}")
                for x in pre:
                    lines.append(f"- {x}")
            steps = b.get("process_steps", [])
            if steps:
                lines.append(f"\n### {'Process' if is_en else '标准流程'}")
                for s in steps:
                    lines.append(f"- {s}")
            if b.get("internal_logic"):
                lines.append(f"\n### {'Internal Logic' if is_en else '内部处理逻辑'}\n{b.get('internal_logic')}")
            if b.get("communication"):
                lines.append(f"\n### {'Communication' if is_en else '商务沟通'}\n{b.get('communication')}")
            exc = b.get("exceptions", [])
            if exc:
                lines.append(f"\n### {'Exceptions' if is_en else '异常情况'}")
                for x in exc:
                    lines.append(f"- {x}")
            faq = b.get("faq", [])
            if faq:
                lines.append(f"\n### FAQ")
                for q in faq:
                    lines.append(f"- {q}")
            lines.append("")
    return "\n".join(lines)
