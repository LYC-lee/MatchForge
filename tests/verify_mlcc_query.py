"""验证真实数据库查询 filter_suppliers_raw('MLCC')"""
import sys, os
sys.path.insert(0, r"D:\Reference\LLM-Base\MatchForge")
os.chdir(r"D:\Reference\LLM-Base\MatchForge")

from ai.tools.mysql_client import filter_suppliers_raw

try:
    results = filter_suppliers_raw("MLCC")
    print(f"查询成功: 返回 {len(results)} 条供应商")
    for r in results[:5]:
        name = r.get("name", "?")
        cat = r.get("category_name", "?")
        brands = r.get("brand_names", "?")
        moq = r.get("moq", "?")
        lt = r.get("lead_time_days", "?")
        print(f"  - {name} | 品类={cat} | 品牌={brands} | MOQ={moq} | 交期={lt}天")
    if not results:
        print("  (无数据，但查询未报列不存在错误 - 通过)")
except Exception as e:
    print(f"查询失败: {type(e).__name__}: {e}")
