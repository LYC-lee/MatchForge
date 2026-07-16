"""
演示场景沙盘种子脚本 (demo scenario sandbox)。

职责:
  1. 确保基线数据存在 (复用 Phase1 企业链路 + Phase2 驾驶舱 + RFQ 闭环种子)。
  2. init_db() 创建 demo_* 表 (SQLAlchemy ORM 自动建表, 幂等)。
  3. 创建默认演示场景 default_mvp_demo + 初始化 6 家主视角企业状态快照。

不复制整库, 不清空业务表; 演示数据全部带 scenario_id, 可随时重置。
基线业务表 (kb_production_orders/kb_inventory_items/kb_rfqs/...) 仅只读。

用法:
  python -m scripts.seed_demo_scenario
  # 或
  python scripts/seed_demo_scenario.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from kb.db import init_db, session_scope  # noqa: E402
from kb import demo_calc as dcalc  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_demo_scenario")


def seed() -> None:
    # 1. 基线数据 (Phase1 公司/关系 + Phase2 产品/BOM/订单/预测/库存/缺件)
    logger.info("==== [1/3] 确保基线数据 (Phase1 + Phase2) ====")
    try:
        import seed_enterprise_phase2 as seed2
        seed2.upsert_all()
    except Exception as e:
        logger.warning("Phase2 基线种子失败 (允许继续): %s", str(e)[:300])

    # 2. 创建 demo_* 表 (幂等)
    logger.info("==== [2/3] 创建 demo_* 表 ====")
    init_db()

    # 3. 默认场景 + 企业状态
    logger.info("==== [3/3] 初始化默认演示场景 default_mvp_demo ====")
    with session_scope() as s:
        sid = dcalc.ensure_default_scenario(s)
        logger.info("演示场景已就绪: %s (主视角企业 %s)", sid, dcalc.DEMO_COMPANY_IDS)
    logger.info("==== 演示场景沙盘种子完成 ====")


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
    sys.exit(0)
