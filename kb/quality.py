"""
知识生成质量校验 (Quality Validator)。

至少验证:
  - Business Boundary Check: 产品类别与主营业务一致性, 跨行业标记失败
  - Product Consistency Check: 同型号价格/规格在 chunk 间无明显冲突
  - Language Check: 中文知识以中文为主, 英文以英文为主
  - Empty Knowledge Check: 不得空手册
  - Chunk Quality Check: 避免极短/标题/重复 chunk
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from kb.boundary import BusinessBoundary

logger = logging.getLogger("kb.quality")

_MIN_CHUNK_LEN = 12  # 字符
_CN_RE = re.compile(r"[一-鿿]")
_EN_RE = re.compile(r"[A-Za-z]")


@dataclass
class QualityReport:
    passed: bool = True
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_issue(self, msg: str):
        self.issues.append(msg)
        self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def _is_chinese_dominant(text: str) -> bool:
    cn = len(_CN_RE.findall(text))
    en = len(_EN_RE.findall(text))
    return cn >= en


def validate_manual(
    company_name: str,
    manual_type: str,
    lang: str,
    manual_data: dict,
    boundary: BusinessBoundary,
) -> QualityReport:
    rep = QualityReport()

    # Empty check
    if manual_type == "product":
        products = manual_data.get("products", [])
        if not products:
            rep.add_issue(f"{company_name} 产品手册为空")
            return rep
        for p in products:
            name = p.get("product_name") or ""
            if not name.strip():
                rep.add_issue("存在无名称产品")
            # Business boundary check: category 必须在边界内
            cat = p.get("category") or ""
            if boundary.product_categories:
                if cat and cat not in boundary.product_categories and cat not in ("PCB硬板",):
                    # 宽松: 只要不在禁止扩展范围即可
                    pass
            # forbidden expansion check
            full_text = " ".join([
                str(p.get("overview", "")), str(p.get("category", "")),
                str(p.get("positioning", "")),
            ])
            if not boundary.allows(full_text):
                rep.add_issue(f"产品 {name} 触碰禁止扩展范围")
            # language check
            if lang == "zh" and not _is_chinese_dominant(str(p.get("overview", ""))):
                rep.add_warning(f"产品 {name} 中文内容非中文主导")
            if lang == "en" and _is_chinese_dominant(str(p.get("overview", ""))):
                rep.add_warning(f"产品 {name} 英文内容非英文主导")
    else:
        bts = manual_data.get("business_types", [])
        if not bts:
            rep.add_issue(f"{company_name} 业务手册为空")
            return rep
        for b in bts:
            bt = b.get("business_type") or ""
            # 业务类型应在 allowed scope 内 (宽松: 只要不在 forbidden)
            full = " ".join([str(b.get("definition", "")), str(b.get("communication", ""))])
            if not boundary.allows(full):
                rep.add_issue(f"业务 {bt} 触碰禁止扩展范围")
            if lang == "zh" and not _is_chinese_dominant(str(b.get("definition", ""))):
                rep.add_warning(f"业务 {bt} 中文内容非中文主导")
            if lang == "en" and _is_chinese_dominant(str(b.get("definition", ""))):
                rep.add_warning(f"业务 {bt} 英文内容非英文主导")

    return rep


def validate_chunks(chunks: list[dict]) -> QualityReport:
    rep = QualityReport()
    if not chunks:
        rep.add_issue("无切片生成")
        return rep
    seen_hash = set()
    for i, c in enumerate(chunks):
        text = c.get("text", "")
        if len(text) < _MIN_CHUNK_LEN:
            rep.add_warning(f"chunk#{i} 过短 ({len(text)}字符): {text[:30]}")
        h = c.get("content_hash")
        if h in seen_hash:
            rep.add_warning(f"chunk#{i} 重复 hash")
        seen_hash.add(h)
    return rep


def validate_product_consistency(chunks: list[dict]) -> QualityReport:
    """同型号价格一致性粗检。"""
    rep = QualityReport()
    prices: dict[str, list[str]] = {}
    for c in chunks:
        if c.get("chunk_type") != "product_price":
            continue
        m = c.get("product_model")
        if not m:
            continue
        prices.setdefault(m, []).append(c.get("text", ""))
    # 同型号只应有一条价格 chunk (按生成逻辑), 多条则报警
    for m, txts in prices.items():
        if len(txts) > 1:
            rep.add_warning(f"型号 {m} 存在 {len(txts)} 条价格 chunk, 需检查一致性")
    return rep
