"""
测试 Agent ⑤ — 询价单生成 + Agent ⑥ — 线索分级
"""

import pytest
from ai.agents.gen_rfq import gen_rfq_agent, build_rfq_template
from ai.agents.grade import grade_agent, score_lead


# ============================================================
# ⑤ 询价单生成
# ============================================================

@pytest.mark.asyncio
async def test_gen_rfq_template():
    """模板填充：生成标准格式 RFQ"""
    rfq_id = "MF-20260715-TEST"
    doc = build_rfq_template(
        spec={"category": "MLCC", "package": "0805", "capacitance": "10uF",
              "temp_coeff": "X7R", "rated_voltage": "50V", "monthly_qty": 500000},
        alternatives=[{"part_name": "CC0805KKX7R9BB106", "brand": "YAGEO", "level": "L1"}],
        suppliers=[{"name": "深圳芯联电子"}],
        rfq_id=rfq_id,
        raw_query="0805 10uF X7R 50V 找替代",
    )
    assert "RFQ-ID: MF-20260715-TEST" in doc
    assert "CC0805KKX7R9BB106" in doc
    assert "深圳芯联电子" in doc
    # 首期库存/交期/价格 声明
    assert "本平台不承诺实时库存与报价" in doc
    # MLCC 品类品名正确
    assert "多层陶瓷贴片电容(MLCC)" in doc


@pytest.mark.asyncio
async def test_gen_rfq_template_non_mlcc_category():
    """#17: 非 MLCC 品类生成的 RFQ 品名正确 (不再硬编码 MLCC)"""
    rfq_id = "MF-20260715-RES"
    doc = build_rfq_template(
        spec={"category": "电阻", "package": "0603", "resistance": "10kΩ",
              "tolerance": "±1%", "rated_power": "1/10W"},
        alternatives=[{"part_name": "RC0603FR-0710KL", "brand": "YAGEO", "level": "L1"}],
        suppliers=[{"name": "电阻供应商A"}],
        rfq_id=rfq_id,
        raw_query="0603 10k 1% 电阻",
    )
    # 电阻品类 -> 贴片电阻, 不应是 MLCC
    assert "贴片电阻" in doc
    assert "多层陶瓷贴片电容" not in doc


@pytest.mark.asyncio
async def test_gen_rfq_template_unknown_category_fallback():
    """#17: 未知品类用通用品名, 不张冠李戴为 MLCC"""
    doc = build_rfq_template(
        spec={"category": "传感器"},
        alternatives=[], suppliers=[],
        rfq_id="MF-X",
        raw_query="某传感器",
    )
    assert "电子元器件" in doc
    assert "多层陶瓷贴片电容" not in doc


@pytest.mark.asyncio
async def test_gen_rfq_agent_empty(sample_state):
    """空输入：仍然生成有效模板（兜底）"""
    sample_state["parsed_spec"] = {}
    result = await gen_rfq_agent(sample_state)
    assert result["rfq_doc"] is not None
    assert result["rfq_id"] is not None
    assert "RFQ-ID" in result["rfq_doc"]


# ============================================================
# ⑥ 线索分级
# ============================================================

def test_score_lead_a():
    """高分 = A 级"""
    spec = {"monthly_qty": 1000000, "lead_time_weeks": 1,
            "brand_pref": ["YAGEO", "Murata"], "has_alternatives": True}
    grade = score_lead(spec)
    assert grade["grade"] == "A"
    assert grade["score"] >= 80


def test_score_lead_b():
    """中分 = B 级"""
    spec = {"monthly_qty": 100000, "lead_time_weeks": 2,
            "brand_pref": ["YAGEO"], "has_alternatives": False}
    grade = score_lead(spec)
    assert grade["grade"] == "B" or grade["grade"] == "A"
    assert grade["score"] >= 60


def test_score_lead_d():
    """低分 = D 级"""
    spec = {"monthly_qty": 100, "lead_time_weeks": 999,
            "brand_pref": [], "has_alternatives": False}
    grade = score_lead(spec)
    assert grade["grade"] == "D"
    assert grade["score"] < 40


@pytest.mark.asyncio
async def test_grade_agent_no_spec(sample_state):
    """无 parsed_spec：仍然运行（用空 dict）"""
    sample_state["parsed_spec"] = {}
    result = await grade_agent(sample_state)
    assert result["lead_grade"] is not None
    assert isinstance(result["lead_grade"]["grade"], str)