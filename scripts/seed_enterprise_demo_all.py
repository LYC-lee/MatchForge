"""
企业演示全量种子脚本 (Phase 1 + Phase 2 Dashboard + RFQ 闭环)

按顺序执行:
  1. seed_enterprise_chain.main()      -- Phase 1: 企业链路 (公司/关系/知识)
  2. seed_enterprise_phase2.main()     -- Phase 2: 产品/BOM/订单/预测/库存/缺件
  3. seed_rfq_supplier_loop.seed()     -- RFQ: 询价/供应商线索/报价/审核队列

各子脚本仍可单独执行, 本脚本仅为集成演示便利。
幂等: 三个子脚本内部均 upsert / IF NOT EXISTS, 可重复运行。

用法:
  python -m scripts.seed_enterprise_demo_all
  # 或
  python scripts/seed_enterprise_demo_all.py
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger("seed_demo_all")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    # 1. Phase 1 企业链路 (公司 / 上下游关系 / 知识)
    logger.info("==== [1/3] Phase 1 企业链路种子 ====")
    from scripts.seed_enterprise_chain import main as seed_phase1

    try:
        seed_phase1()
    except Exception as e:
        logger.warning("Phase 1 种子失败 (允许继续): %s", str(e)[:300])

    # 2. Phase 2 Dashboard (产品 / BOM / 订单 / 预测 / 库存 / 缺件)
    logger.info("==== [2/3] Phase 2 Dashboard 种子 ====")
    from scripts.seed_enterprise_phase2 import main as seed_phase2

    try:
        seed_phase2()
    except Exception as e:
        logger.warning("Phase 2 种子失败 (允许继续): %s", str(e)[:300])

    # 3. RFQ 闭环 (询价 / 供应商线索 / 报价 / 审核队列)
    logger.info("==== [3/3] RFQ 闭环种子 ====")
    from scripts.seed_rfq_supplier_loop import seed as seed_rfq

    try:
        seed_rfq()
    except Exception as e:
        logger.warning("RFQ 种子失败 (允许继续): %s", str(e)[:300])

    logger.info("==== 企业演示全量种子完成 ====")


if __name__ == "__main__":
    main()
    sys.exit(0)
