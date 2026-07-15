"""查看所有P4数据 - 在Windows下直接运行 python view_all_data.py"""
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print()
print("=" * 50)
print("  MatchForge P4 数据查看工具")
print("=" * 50)

# ---- 1. 种子供应商 ----
print()
print("========== 1. 种子供应商 suppliers.json ==========")
with open("suppliers/suppliers.json", "r", encoding="utf-8") as f:
    data = json.load(f)
product_count = sum(len(s["products"]) for s in data)
print(f"供应商总数: {len(data)} 家")
print(f"产品总数: {product_count} 条")
print()
print("--- 地区分布 ---")
loc = {}
for s in data:
    loc[s["location"]] = loc.get(s["location"], 0) + 1
for k, v in sorted(loc.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}家")
print()
print("--- 品类分布 ---")
cat = {}
for s in data:
    for p in s["products"]:
        cat[p["category"]] = cat.get(p["category"], 0) + 1
for k, v in sorted(cat.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}条")
print()
print("--- 前5家供应商 ---")
for s in data[:5]:
    print(f"  {s['id']}. {s['name']} ({s['location']}) 主营:{s['main_category']} 评分:{s['rating']} 产品:{len(s['products'])}条")
    for p in s["products"][:2]:
        print(f"      {p['part_number']} ({p['brand']}) {p['category']}")

# ---- 2. 替代料交叉引用 ----
print()
print("========== 2. 替代料交叉引用 alternatives.json ==========")
with open("alternatives/alternatives.json", "r", encoding="utf-8") as f:
    adata = json.load(f)
groups = adata["groups"]
eq_count = sum(len(g["equivalences"]) for g in groups)
print(f"替代料组数: {len(groups)} 组")
print(f"替代关系数: {eq_count} 条")
print()
print("--- 品类分布 ---")
acat = {}
for g in groups:
    acat[g["category"]] = acat.get(g["category"], 0) + 1
for k, v in sorted(acat.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}组")
print()
print("--- 前5组示例 ---")
for g in groups[:5]:
    print(f"  组{g['group_id']}: {g['category']} - {g['spec']} ({len(g['parts'])}个料号, {len(g['equivalences'])}条关系)")
    for p in g["parts"][:3]:
        print(f"      {p['part_number']} ({p['brand']})")

# ---- 3. 标准字典 ----
print()
print("========== 3. 标准字典 dictionary.json ==========")
with open("dictionary/dictionary.json", "r", encoding="utf-8") as f:
    ddata = json.load(f)
items = ddata["items"]
print(f"字典条目数: {len(items)} 条")
print()
print("--- 品类分布 ---")
dcat = {}
for x in items:
    dcat[x["category"]] = dcat.get(x["category"], 0) + 1
for k, v in sorted(dcat.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}条")
print()
print("--- 前5条示例 ---")
for x in items[:5]:
    print(f"  {x['std_code']}")
    print(f"    品类: {x['category']}")
    print(f"    标准: {x['standard']}")
    print(f"    描述: {x['description']}")

# ---- 4. 其他文件 ----
print()
print("========== 4. 其他文件 ==========")
for fn in ["mysql_schema.sql", "init_all.py", "milvus_collections.py", "milvus_seed_data.py", "knowledge_base_docs.py"]:
    if os.path.exists(fn):
        with open(fn, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(f"  {fn}: {len(lines)} 行")

print()
print("=" * 50)
print("  数据查看完毕!")
print("=" * 50)
