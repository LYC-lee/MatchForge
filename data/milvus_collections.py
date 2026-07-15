#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
# MatchForge P4 数据层 - Milvus 集合创建 + 索引构建脚本
# ════════════════════════════════════════════════════════════════════════════
#
# 项目: MatchForge AI供需对接平台（电子元器件行业）
# 角色: P4 数据/知识库工程师
# 用途: 连接 Milvus 2.4，创建两个 Collection 及其向量索引，并插入少量示例数据
#
# 两个 Collection:
#   1. product_embeddings  - 供应商产品向量索引（语义搜索/替代料匹配）
#   2. knowledge_chunks     - 知识库文档分块向量索引（RAG 检索增强生成）
#
# 索引策略:
#   - product_embeddings  使用 HNSW（高召回率 + 低延迟，适合实时产品搜索）
#   - knowledge_chunks    使用 IVF_FLAT（精确匹配 + 省内存，适合知识库离线检索）
#
# 使用方式:
#   python data/milvus_collections.py                # 创建集合 + 索引 + 示例数据
#   python data/milvus_collections.py --drop         # 先删除已有集合再创建
#   python data/milvus_collections.py --no-sample    # 不插入示例数据
#
# 前置条件:
#   - Milvus 2.4 已启动（Docker: docker compose up -d milvus）
#   - .env 已配置 MILVUS_HOST / MILVUS_PORT
#   - pip install pymilvus python-dotenv
# ════════════════════════════════════════════════════════════════════════════

import argparse
import os
import sys
import time
from pathlib import Path

# ── 加载 .env 配置 ──────────────────────────────────────────────────────────
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── 配置常量 ────────────────────────────────────────────────────────────────
MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))  # bge-m3 默认 1024 维

# 集合名称
COLLECTION_PRODUCT = "product_embeddings"
COLLECTION_KNOWLEDGE = "knowledge_chunks"

# 字段最大长度（VARCHAR）
MAX_VARCHAR_LEN = 65535  # 知识库文本块可能较长


# ════════════════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════════════════

def connect_milvus(retries: int = 5, delay: float = 3.0):
    """
    连接 Milvus 服务器，支持重试。

    Milvus 容器启动后可能需要几秒钟才能接受连接，
    所以这里做有限次重试，避免首次初始化时连接失败。

    Args:
        retries: 最大重试次数
        delay:   每次重试间隔（秒）

    Returns:
        None（pymilvus 的连接是全局单例，无需返回连接对象）

    Raises:
        RuntimeError: 所有重试均失败时抛出
    """
    from pymilvus import connections

    alias = "default"
    for attempt in range(1, retries + 1):
        try:
            connections.connect(
                alias=alias,
                host=MILVUS_HOST,
                port=MILVUS_PORT,
            )
            print(f"  [Milvus] 连接成功: {MILVUS_HOST}:{MILVUS_PORT}")
            return
        except Exception as e:
            print(f"  [Milvus] 第 {attempt}/{retries} 次连接失败: {e}")
            if attempt < retries:
                print(f"           {delay} 秒后重试...")
                time.sleep(delay)

    raise RuntimeError(
        f"无法连接 Milvus ({MILVUS_HOST}:{MILVUS_PORT})，"
        f"请确认 Milvus 已启动。可用 docker compose up -d milvus 启动。"
    )


def collection_exists(name: str) -> bool:
    """检查指定名称的 Collection 是否已存在。"""
    from pymilvus import utility
    return utility.has_collection(name, using="default")


def drop_collection(name: str):
    """删除指定 Collection（如果存在）。"""
    from pymilvus import utility
    if utility.has_collection(name, using="default"):
        utility.drop_collection(name, using="default")
        print(f"  [Milvus] 已删除现有集合: {name}")


# ════════════════════════════════════════════════════════════════════════════
# 1. product_embeddings 集合
# ════════════════════════════════════════════════════════════════════════════

def create_product_embeddings_collection():
    """
    创建 product_embeddings 集合并构建 HNSW 索引。

    字段说明:
      - product_id   (INT64, 主键)        对应 MySQL products.id
      - embedding    (FLOAT_VECTOR, 1024维)  产品语义向量
      - category     (VARCHAR)            品类，如 MLCC/电阻/二极管
      - brand        (VARCHAR)            品牌，如 Murata/Yageo/TDK
      - part_number  (VARCHAR)            料号，如 GRM188R71H104KA93D

    索引:
      HNSW (Hierarchical Navigable Small World)
      - 适合实时产品搜索，查询延迟低
      - M=16, efConstruction=256（官方推荐参数）
      - 度量方式: COSINE（余弦相似度，适合语义匹配）
    """
    from pymilvus import (
        Collection, CollectionSchema, DataType, FieldSchema,
    )

    # ── 定义字段 ──
    fields = [
        FieldSchema(
            name="product_id",
            dtype=DataType.INT64,
            is_primary=True,
            description="产品ID，对应 MySQL products.id",
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIM,
            description=f"产品语义向量，{EMBEDDING_DIM}维（bge-m3）",
        ),
        FieldSchema(
            name="category",
            dtype=DataType.VARCHAR,
            max_length=100,
            description="品类: MLCC/电阻/二极管/连接器/MCU等",
        ),
        FieldSchema(
            name="brand",
            dtype=DataType.VARCHAR,
            max_length=200,
            description="品牌/厂商名称",
        ),
        FieldSchema(
            name="part_number",
            dtype=DataType.VARCHAR,
            max_length=200,
            description="完整料号，如 GRM188R71H104KA93D",
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description="供应商产品向量索引 - 用于产品语义搜索和替代料匹配",
        enable_dynamic_field=False,  # 固定 schema，不允许动态字段
    )

    # ── 创建集合 ──
    collection = Collection(
        name=COLLECTION_PRODUCT,
        schema=schema,
        using="default",
    )
    print(f"  [Milvus] 集合已创建: {COLLECTION_PRODUCT}")

    # ── 创建 HNSW 索引 ──
    # HNSW 参数说明:
    #   M              每个节点的最大连接数，影响图密度和内存，推荐 16~64
    #   efConstruction 构建时的搜索宽度，越大质量越高但构建越慢，推荐 200~500
    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {
            "M": 16,
            "efConstruction": 256,
        },
    }

    collection.create_index(
        field_name="embedding",
        index_params=index_params,
    )
    print(f"  [Milvus] HNSW 索引已创建 (M=16, efConstruction=256, metric=COSINE)")

    # ── 加载集合到内存 ──
    collection.load()
    print(f"  [Milvus] 集合已加载到内存: {COLLECTION_PRODUCT}")

    return collection


# ════════════════════════════════════════════════════════════════════════════
# 2. knowledge_chunks 集合
# ════════════════════════════════════════════════════════════════════════════

def create_knowledge_chunks_collection():
    """
    创建 knowledge_chunks 集合并构建 IVF_FLAT 索引。

    字段说明:
      - chunk_id     (INT64, 主键)      分块唯一ID
      - embedding    (FLOAT_VECTOR, 1024维) 文本块语义向量
      - source_type  (VARCHAR)          来源类型: mlcc_guide/resistor_spec/alt_criteria/faq
      - source_id    (INT64)            来源文档ID（同一文档的多个分块共享此ID）
      - text         (VARCHAR)          原始文本块内容

    索引:
      IVF_FLAT (倒排文件 + 精确距离计算)
      - 适合知识库离线检索，精度高、省内存
      - nlist=128（聚类中心数，数据量小时用 128 足够）
      - 度量方式: COSINE
    """
    from pymilvus import (
        Collection, CollectionSchema, DataType, FieldSchema,
    )

    fields = [
        FieldSchema(
            name="chunk_id",
            dtype=DataType.INT64,
            is_primary=True,
            description="分块唯一ID",
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIM,
            description=f"文本块语义向量，{EMBEDDING_DIM}维（bge-m3）",
        ),
        FieldSchema(
            name="source_type",
            dtype=DataType.VARCHAR,
            max_length=100,
            description="来源类型: mlcc_guide/resistor_spec/alt_criteria/faq",
        ),
        FieldSchema(
            name="source_id",
            dtype=DataType.INT64,
            description="来源文档ID（同一文档的多个分块共享此ID）",
        ),
        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=MAX_VARCHAR_LEN,
            description="原始文本块内容",
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description="知识库文档分块向量索引 - 用于RAG检索增强生成",
        enable_dynamic_field=False,
    )

    collection = Collection(
        name=COLLECTION_KNOWLEDGE,
        schema=schema,
        using="default",
    )
    print(f"  [Milvus] 集合已创建: {COLLECTION_KNOWLEDGE}")

    # ── 创建 IVF_FLAT 索引 ──
    # IVF_FLAT 参数说明:
    #   nlist  聚类中心数量，数据量 <10万 用 128；10万~100万 用 1024
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {
            "nlist": 128,
        },
    }

    collection.create_index(
        field_name="embedding",
        index_params=index_params,
    )
    print(f"  [Milvus] IVF_FLAT 索引已创建 (nlist=128, metric=COSINE)")

    collection.load()
    print(f"  [Milvus] 集合已加载到内存: {COLLECTION_KNOWLEDGE}")

    return collection


# ════════════════════════════════════════════════════════════════════════════
# 3. 示例数据插入
# ════════════════════════════════════════════════════════════════════════════

def insert_sample_products(collection):
    """
    向 product_embeddings 插入少量示例数据。

    注意: 这里的 embedding 是随机生成的占位向量，
    真实数据由 milvus_seed_data.py 从 embedding API 生成。
    示例数据仅用于验证集合 schema 和索引是否正常工作。
    """
    import random

    # 示例产品（料号 + 品牌 + 品类）
    sample_products = [
        # (product_id, category, brand, part_number, 描述用于生成embedding)
        (1, "MLCC", "Murata", "GRM188R71H104KA93D", "村田0603 0.1uF 50V X7R MLCC贴片电容"),
        (2, "MLCC", "TDK", "C1608X7R1H104K080AC", "TDK 0603 0.1uF 50V X7R贴片电容"),
        (3, "MLCC", "Yageo", "CC0603KRX7R9BB104", "国巨0603 0.1uF 50V X7R贴片电容"),
        (4, "电阻", "Yageo", "RC0603FR-0710KL", "国巨0603 10KΩ 1%贴片电阻"),
        (5, "电阻", "Panasonic", "ERJ-3EKF1002V", "松下0603 10KΩ 1%贴片电阻"),
        (6, "二极管", "NXP", "1N4148W", "NXP 1N4148W 开关二极管"),
    ]

    # 生成随机占位向量（真实数据由 seed 脚本生成）
    random.seed(42)
    data = [
        [p[0] for p in sample_products],                       # product_id
        [[random.uniform(-1, 1) for _ in range(EMBEDDING_DIM)]
         for _ in sample_products],                             # embedding
        [p[1] for p in sample_products],                       # category
        [p[2] for p in sample_products],                       # brand
        [p[3] for p in sample_products],                       # part_number
    ]

    collection.insert(data)
    collection.flush()  # 刷新到磁盘，确保数据可查
    print(f"  [Milvus] 已插入 {len(sample_products)} 条示例产品数据")


def insert_sample_knowledge(collection):
    """
    向 knowledge_chunks 插入少量示例数据。

    注意: embedding 为随机占位向量，真实数据由 embedding API 生成。
    文本内容来自 knowledge_base_docs.py 中的知识库文档分块。
    """
    import random

    # 示例知识库分块
    sample_chunks = [
        # (chunk_id, source_type, source_id, text)
        (1, "mlcc_guide", 1,
         "MLCC（多层陶瓷电容器）选型时需要考虑以下关键参数：标称容值、"
         "额定电压、温度系数（X7R/X5R/C0G等）、封装尺寸（0201/0402/0603/0805等）、"
         "精度等级和DC偏压特性。X7R材质适用于去耦和滤波电路，C0G材质适用于振荡电路。"),
        (2, "resistor_spec", 2,
         "贴片电阻规格说明：标准封装包括0201/0402/0603/0805/1206等，"
         "阻值范围0Ω~22MΩ，常见精度1%和5%，额定功率与封装相关。"
         "0603封装额定功率为1/10W，0805为1/8W，1206为1/4W。"),
        (3, "alt_criteria", 3,
         "替代料判断标准：1) 封装尺寸必须一致（pin-to-pin兼容）；"
         "2) 关键电气参数需匹配（容值/阻值/耐压/温度系数）；"
         "3) 温度范围需覆盖原型号规格；4) 认证要求需满足（AEC-Q200等）；"
         "5) DC偏压特性需评估。完全匹配为A级替代，参数微差异为B级。"),
        (4, "faq", 4,
         "常见问题：Q: MLCC电容容值随DC偏压下降怎么办？"
         "A: 选择更大容值的型号或使用C0G材质。"
         "Q: 0603和0805封装能否互换？A: 需要重新设计PCB焊盘，不建议直接替换。"),
    ]

    random.seed(42)
    data = [
        [c[0] for c in sample_chunks],                         # chunk_id
        [[random.uniform(-1, 1) for _ in range(EMBEDDING_DIM)]
         for _ in sample_chunks],                               # embedding
        [c[1] for c in sample_chunks],                         # source_type
        [c[2] for c in sample_chunks],                         # source_id
        [c[3] for c in sample_chunks],                         # text
    ]

    collection.insert(data)
    collection.flush()
    print(f"  [Milvus] 已插入 {len(sample_chunks)} 条示例知识库数据")


# ════════════════════════════════════════════════════════════════════════════
# 主函数
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MatchForge Milvus 集合创建 + 索引构建"
    )
    parser.add_argument(
        "--drop", action="store_true",
        help="先删除已有集合再创建（会清除所有数据）",
    )
    parser.add_argument(
        "--no-sample", action="store_true",
        help="不插入示例数据",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("MatchForge P4 - Milvus 集合创建 + 索引构建")
    print("=" * 70)
    print(f"  Milvus 地址: {MILVUS_HOST}:{MILVUS_PORT}")
    print(f"  向量维度:   {EMBEDDING_DIM}")
    print(f"  删除重建:   {args.drop}")
    print()

    # ── 连接 Milvus ──
    print("[1/4] 连接 Milvus ...")
    connect_milvus()

    # ── 删除已有集合（可选）──
    if args.drop:
        print("\n[2/4] 删除已有集合 ...")
        drop_collection(COLLECTION_PRODUCT)
        drop_collection(COLLECTION_KNOWLEDGE)
    else:
        print("\n[2/4] 检查已有集合 ...")
        if collection_exists(COLLECTION_PRODUCT):
            print(f"  [警告] 集合已存在: {COLLECTION_PRODUCT}（使用 --drop 可重建）")
        if collection_exists(COLLECTION_KNOWLEDGE):
            print(f"  [警告] 集合已存在: {COLLECTION_KNOWLEDGE}（使用 --drop 可重建）")

    # ── 创建集合 + 索引 ──
    print("\n[3/4] 创建集合 + 索引 ...")

    if collection_exists(COLLECTION_PRODUCT) and not args.drop:
        print(f"  [跳过] {COLLECTION_PRODUCT} 已存在")
        from pymilvus import Collection
        product_col = Collection(COLLECTION_PRODUCT)
        product_col.load()
    else:
        product_col = create_product_embeddings_collection()

    if collection_exists(COLLECTION_KNOWLEDGE) and not args.drop:
        print(f"  [跳过] {COLLECTION_KNOWLEDGE} 已存在")
        from pymilvus import Collection
        knowledge_col = Collection(COLLECTION_KNOWLEDGE)
        knowledge_col.load()
    else:
        knowledge_col = create_knowledge_chunks_collection()

    # ── 插入示例数据 ──
    if not args.no_sample:
        print("\n[4/4] 插入示例数据 ...")
        try:
            insert_sample_products(product_col)
        except Exception as e:
            print(f"  [警告] 产品示例数据插入失败: {e}")
        try:
            insert_sample_knowledge(knowledge_col)
        except Exception as e:
            print(f"  [警告] 知识库示例数据插入失败: {e}")
    else:
        print("\n[4/4] 跳过示例数据插入")

    # ── 完成 ──
    print("\n" + "=" * 70)
    print("Milvus 集合创建完成!")
    print("=" * 70)
    print(f"  集合: {COLLECTION_PRODUCT}  (HNSW, COSINE)")
    print(f"  集合: {COLLECTION_KNOWLEDGE} (IVF_FLAT, COSINE)")
    print()
    print("下一步:")
    print(f"  1. 运行种子数据脚本: python data/milvus_seed_data.py")
    print(f"  2. 验证数据:")
    print(f"     python -c \"from pymilvus import Collection; "
          f"c=Collection('{COLLECTION_PRODUCT}'); print(c.num_entities)\"")
    print()


if __name__ == "__main__":
    main()
