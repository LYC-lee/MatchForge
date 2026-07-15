#!/usr/bin/env python3
"""
MatchForge 知识库 CLI。

用法:
  python scripts/kb_cli.py init                      # 全部公司知识初始化
  python scripts/kb_cli.py init --companies 1,2,3    # 指定公司
  python scripts/kb_cli.py init --force              # 强制重新生成
  python scripts/kb_cli.py generate --company 5      # 单公司生成
  python scripts/kb_cli.py incremental --company 5   # 单公司增量更新
  python scripts/kb_cli.py rebuild-index             # 从 Source of Truth 重建向量
  python scripts/kb_cli.py rebuild-index --drop      # 先清空向量集合再重建
  python scripts/kb_cli.py stats                     # 知识库统计
  python scripts/kb_cli.py status --company 5        # 单公司知识状态
  python scripts/kb_cli.py capabilities              # 运行时能力
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kb.db import init_db, session_scope  # noqa: E402
from kb.companies import collect_companies, get_company  # noqa: E402
from kb.config import runtime_capabilities  # noqa: E402
from kb.pipeline import (  # noqa: E402
    generate_all,
    generate_for_company,
    incremental_update,
    knowledge_stats,
    company_knowledge_status,
    rebuild_vector_index,
)


def cmd_init(args):
    init_db()
    with session_scope() as s:
        collect_companies(s)
    ids = None
    if args.companies:
        ids = [int(x) for x in args.companies.split(",")]
    print(f"启动知识生成: companies={ids or 'ALL'} force={args.force}")
    summary = asyncio.run(generate_all(company_ids=ids, force=args.force))
    print("\n=== 生成完成 ===")
    for k, v in summary.items():
        if k != "failed":
            print(f"  {k}: {v}")
    if summary.get("failed"):
        print(f"  失败公司 ({len(summary['failed'])}):")
        for f in summary["failed"]:
            print(f"    - #{f['company_id']} {f['company_name']}: {f['issues'][:1]}")
    print("\n=== 知识库统计 ===")
    print_stats()


def cmd_generate(args):
    init_db()
    with session_scope() as s:
        collect_companies(s)
        c = get_company(s, args.company)
    if not c:
        print(f"公司 {args.company} 不存在")
        return
    res = asyncio.run(generate_for_company(c, force=True))
    print(f"完成: chunks={res['chunks']} products={res['products']} source={res['source']}")
    if res["issues"]:
        print("issues:", res["issues"])


def cmd_incremental(args):
    init_db()
    res = asyncio.run(incremental_update(args.company))
    print("增量更新结果:", res)


def cmd_rebuild(args):
    init_db()
    res = rebuild_vector_index(drop_first=args.drop)
    print("重建完成:", res)


def print_stats():
    s = knowledge_stats()
    for k, v in s.items():
        print(f"  {k}: {v}")


def cmd_stats(args):
    init_db()
    print("=== 知识库统计 ===")
    print_stats()


def cmd_status(args):
    init_db()
    print(company_knowledge_status(args.company))


def cmd_capabilities(args):
    print("=== 运行时能力 ===")
    for k, v in runtime_capabilities().items():
        print(f"  {k}: {v}")


def main():
    p = argparse.ArgumentParser(description="MatchForge 知识库 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="全部公司知识初始化")
    p_init.add_argument("--companies", help="逗号分隔的公司ID, 默认全部")
    p_init.add_argument("--force", action="store_true", help="强制重新生成")
    p_init.set_defaults(func=cmd_init)

    p_gen = sub.add_parser("generate", help="单公司生成")
    p_gen.add_argument("--company", type=int, required=True)
    p_gen.set_defaults(func=cmd_generate)

    p_inc = sub.add_parser("incremental", help="单公司增量更新")
    p_inc.add_argument("--company", type=int, required=True)
    p_inc.set_defaults(func=cmd_incremental)

    p_rb = sub.add_parser("rebuild-index", help="重建向量索引")
    p_rb.add_argument("--drop", action="store_true", help="先清空向量集合")
    p_rb.set_defaults(func=cmd_rebuild)

    sub.add_parser("stats", help="知识库统计").set_defaults(func=cmd_stats)
    p_st = sub.add_parser("status", help="单公司知识状态")
    p_st.add_argument("--company", type=int, required=True)
    p_st.set_defaults(func=cmd_status)

    sub.add_parser("capabilities", help="运行时能力").set_defaults(func=cmd_capabilities)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
