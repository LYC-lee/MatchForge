#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
# MatchForge P4 数据层 - Milvus 种子数据生成脚本
# ════════════════════════════════════════════════════════════════════════════
#
# 项目: MatchForge AI供需对接平台（电子元器件行业）
# 角色: P4 数据/知识库工程师
# 用途: 从 MySQL 读取供应商产品数据，调用 Embedding API 生成向量，写入 Milvus；
#       同时将知识库文档分块（knowledge_base_docs.py）也向量化写入 Milvus。
#
# 数据流:
#   MySQL products 表 ──→ 构建 embedding 文本 ──→ Embedding API ──→ product_embeddings
#   knowledge_base_docs.py ──→ 文本分块 ──→ Embedding API ──→ knowledge_chunks
#
# Embedding 模型: BAAI/bge-m3 (1024维)，通过 OpenAI 兼容接口调用
# .env 配置项:
#   EMBEDDING_API_KEY   - Embedding API 密钥
#   EMBEDDING_BASE_URL  - Embedding API 地址 (如 https://api.siliconflow.cn/v1)
#   EMBEDDING_MODEL     - 模型名称 (如 BAAI/bge-m3)
#   EMBEDDING_DIM       - 向量维度 (1024)
#
# 使用方式:
#   python data/milvus_seed_data.py                     # 同步产品+知识库
#   python data/milvus_seed_data.py --products-only     # 仅同步产品数据
#   python data/milvus_seed_data.py --knowledge-only     # 仅同步知识库
#   python data/milvus_seed_data.py --batch-size 20      # 自定义批次大小
#
# 前置条件:
#   1. Milvus 已启动且集合已创建 (先运行 milvus_collections.py)
#   2. MySQL 已启动且有产品数据 (先运行 init_all.py --step mysql)
#   3. .env 已配置 EMBEDDING_API_KEY / EMBEDDING_BASE_URL / EMBEDDING_MODEL
#   4. pip install pymilvus pymysql openai python-dotenv
# ════════════════════════════════════════════════════════════════════════════

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

# ── 加载 .env 配置 ──────────────────────────────────────────────────────────
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# 将 data/ 目录加入 sys.path，以便 import knowledge_base_docs
sys.path.insert(0, str(DATA_DIR))

# ── 配置常量 ────────────────────────────────────────────────────────────────

# Milvus 配置
MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")

# MySQL 配置
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "matchforge")

# Embedding API 配置
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# 集合名称（与 milvus_collections.py 一致）
COLLECTION_PRODUCT = "product_embeddings"
COLLECTION_KNOWLEDGE = "knowledge_chunks"

# 默认批次大小（embedding API 通常限制单次请求的文本数量）
DEFAULT_BATCH_SIZE = 20

# API 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # 秒


# ════════════════════════════════════════════════════════════════════════════
# 1. Embedding 客户端 - 调用 OpenAI 兼容接口生成向量
# ════════════════════════════════════════════════════════════════════════════

class EmbeddingClient:
    """
    Embedding 向量生成客户端。

    通过 OpenAI 兼容接口调用 Embedding API（如硅基流动 BAAI/bge-m3），
    将文本转换为 1024 维向量。支持批量请求和自动重试。
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        """
        初始化 Embedding 客户端。

        Args:
            api_key:  API 密钥
            base_url: API 基础地址（如 https://api.siliconflow.cn/v1）
            model:    模型名称（如 BAAI/bge-m3）
        """
        from openai import OpenAI

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        print(f"  [Embedding] 客户端已初始化: {base_url} / {model}")

    def embed(self, texts: List[str], batch_size: int = DEFAULT_BATCH_SIZE) -> List[List[float]]:
        """
        批量生成文本向量，支持自动分批和重试。

        Args:
            texts:       待向量化的文本列表
            batch_size:  每次 API 请求的最大文本数

        Returns:
            向量列表，顺序与输入文本一一对应

        Raises:
            RuntimeError: 重试次数耗尽后仍然失败
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size

            embeddings = self._embed_batch_with_retry(batch, batch_num, total_batches)
            all_embeddings.extend(embeddings)

            # 简短的批次间延迟，避免触发 API 限流
            if i + batch_size < len(texts):
                time.sleep(0.3)

        return all_embeddings

    def _embed_batch_with_retry(
        self, batch: List[str], batch_num: int, total_batches: int
    ) -> List[List[float]]:
        """
        对单个批次调用 Embedding API，失败时自动重试。

        重试策略：指数退避，每次延迟加倍（2s -> 4s -> 8s）。
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                # 按 index 排序确保顺序正确
                sorted_data = sorted(response.data, key=lambda x: x.index)
                embeddings = [item.embedding for item in sorted_data]

                print(
                    f"  [Embedding] 批次 {batch_num}/{total_batches} 成功: "
                    f"{len(batch)} 条文本 -> {len(embeddings)} 个向量"
                )
                return embeddings

            except Exception as e:
                delay = RETRY_DELAY * (2 ** (attempt - 1))  # 指数退避
                print(
                    f"  [Embedding] 批次 {batch_num}/{total_batches} "
                    f"第 {attempt}/{MAX_RETRIES} 次失败: {e}"
                )
                if attempt < MAX_RETRIES:
                    print(f"           {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"Embedding API 调用失败（已重试 {MAX_RETRIES} 次）: {e}"
                    ) from e

        return []  # 不会到达，仅为类型检查


# ════════════════════════════════════════════════════════════════════════════
# 2. MySQL 数据读取 - 从 products 表读取供应商产品数据
# ════════════════════════════════════════════════════════════════════════════

def fetch_products_from_mysql() -> List[Dict]:
    """
    从 MySQL 的 products 表读取所有产品数据。

    返回字段: id, supplier_id, category, part_number, specs, brand（从suppliers关联）
    将产品的品类、料号、规格参数组合成一段描述文本，用于生成 embedding。

    Returns:
        产品字典列表，每个字典包含:
        - product_id (int)
        - category (str)
        - brand (str)        - 从 suppliers 表关联获取
        - part_number (str)
        - embed_text (str)   - 用于生成 embedding 的组合文本

    Raises:
        RuntimeError: 数据库连接或查询失败
    """
    import pymysql

    print(f"  [MySQL] 连接 {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE} ...")

    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception as e:
        raise RuntimeError(
            f"MySQL 连接失败: {e}。请确认 MySQL 已启动且 .env 配置正确。"
        ) from e

    try:
        with conn.cursor() as cursor:
            # 关联 suppliers 表获取品牌/供应商名称
            sql = """
                SELECT p.id, p.category, p.part_number, p.specs,
                       s.name AS supplier_name
                FROM products p
                LEFT JOIN suppliers s ON p.supplier_id = s.id
                ORDER BY p.id
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
        conn.close()
        print(f"  [MySQL] 读取到 {len(rows)} 条产品数据")

    except Exception as e:
        conn.close()
        raise RuntimeError(f"MySQL 查询失败: {e}") from e

    # 构建 embedding 文本
    products = []
    for row in rows:
        # 解析 specs JSON
        specs_text = ""
        if row.get("specs"):
            try:
                specs = json.loads(row["specs"]) if isinstance(row["specs"], str) else row["specs"]
                # 将规格参数拼接为可读文本
                specs_text = "，".join(f"{k}:{v}" for k, v in specs.items())
            except (json.JSONDecodeError, TypeError):
                specs_text = str(row["specs"])

        # 组合文本: 品类 + 料号 + 品牌 + 规格
        embed_text = " ".join(filter(None, [
            row["category"],
            row["part_number"],
            row.get("supplier_name", ""),
            specs_text,
        ]))

        products.append({
            "product_id": row["id"],
            "category": row["category"] or "",
            "brand": row.get("supplier_name") or "",
            "part_number": row["part_number"] or "",
            "embed_text": embed_text,
        })

    return products


# ════════════════════════════════════════════════════════════════════════════
# 3. Milvus 数据写入
# ════════════════════════════════════════════════════════════════════════════

def connect_milvus(retries: int = 5, delay: float = 3.0):
    """连接 Milvus 服务器（带重试）。"""
    from pymilvus import connections

    for attempt in range(1, retries + 1):
        try:
            connections.connect(
                alias="default",
                host=MILVUS_HOST,
                port=MILVUS_PORT,
            )
            print(f"  [Milvus] 连接成功: {MILVUS_HOST}:{MILVUS_PORT}")
            return
        except Exception as e:
            print(f"  [Milvus] 第 {attempt}/{retries} 次连接失败: {e}")
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(
        f"无法连接 Milvus ({MILVUS_HOST}:{MILVUS_PORT})，"
        f"请先运行 python data/milvus_collections.py 创建集合。"
    )


def upsert_product_embeddings(
    embedding_client: EmbeddingClient,
    products: List[Dict],
    batch_size: int = DEFAULT_BATCH_SIZE,
):
    """
    将产品数据向量化并写入 product_embeddings 集合。

    如果 product_id 已存在则先删除再插入（实现 upsert 语义）。

    Args:
        embedding_client: Embedding 客户端
        products:         产品数据列表（来自 MySQL）
        batch_size:       embedding API 批次大小
    """
    from pymilvus import Collection, utility

    if not products:
        print("  [Milvus] 没有产品数据需要同步")
        return

    if not utility.has_collection(COLLECTION_PRODUCT, using="default"):
        raise RuntimeError(
            f"集合 {COLLECTION_PRODUCT} 不存在，请先运行 milvus_collections.py"
        )

    collection = Collection(COLLECTION_PRODUCT)
    collection.load()

    # 获取已有数据的 product_id 集合（用于去重判断）
    existing_ids = set()
    try:
        results = collection.query(
            expr="product_id >= 0",
            output_fields=["product_id"],
            limit=16384,  # Milvus 单次查询上限
        )
        existing_ids = {r["product_id"] for r in results}
    except Exception:
        pass  # 集合为空时查询可能报错，忽略

    # 删除即将更新的记录
    ids_to_update = [p["product_id"] for p in products if p["product_id"] in existing_ids]
    if ids_to_update:
        id_list_str = ",".join(str(i) for i in ids_to_update)
        collection.delete(expr=f"product_id in [{id_list_str}]")
        print(f"  [Milvus] 删除 {len(ids_to_update)} 条已有记录（待更新）")

    # 批量生成 embedding
    texts = [p["embed_text"] for p in products]
    print(f"  [Milvus] 开始生成 {len(texts)} 条产品的 embedding ...")
    embeddings = embedding_client.embed(texts, batch_size=batch_size)

    # 写入 Milvus
    data = [
        [p["product_id"] for p in products],    # product_id
        embeddings,                               # embedding
        [p["category"] for p in products],       # category
        [p["brand"] for p in products],          # brand
        [p["part_number"] for p in products],    # part_number
    ]

    collection.insert(data)
    collection.flush()

    print(f"  [Milvus] product_embeddings 写入完成: {len(products)} 条")


def upsert_knowledge_chunks(
    embedding_client: EmbeddingClient,
    batch_size: int = DEFAULT_BATCH_SIZE,
):
    """
    将知识库文档分块向量化并写入 knowledge_chunks 集合。

    数据来源: knowledge_base_docs.py 中的 KNOWLEDGE_CHUNKS 列表。
    每次运行会清空旧数据后重新写入（知识库全量重建）。

    Args:
        embedding_client: Embedding 客户端
        batch_size:       embedding API 批次大小
    """
    from pymilvus import Collection, utility

    # 导入知识库文档
    from knowledge_base_docs import KNOWLEDGE_CHUNKS

    if not KNOWLEDGE_CHUNKS:
        print("  [Milvus] 没有知识库数据需要同步")
        return

    if not utility.has_collection(COLLECTION_KNOWLEDGE, using="default"):
        raise RuntimeError(
            f"集合 {COLLECTION_KNOWLEDGE} 不存在，请先运行 milvus_collections.py"
        )

    collection = Collection(COLLECTION_KNOWLEDGE)
    collection.load()

    # 清空旧数据（知识库全量重建）
    try:
        collection.delete(expr="chunk_id >= 0")
        collection.flush()
        print(f"  [Milvus] 已清空 knowledge_chunks 旧数据")
    except Exception:
        pass  # 集合为空时删除可能报错，忽略

    # 生成 chunk_id（从1开始递增）
    chunks_with_id = []
    for idx, chunk in enumerate(KNOWLEDGE_CHUNKS, 1):
        chunks_with_id.append({
            "chunk_id": idx,
            "source_type": chunk["source_type"],
            "source_id": chunk["source_id"],
            "text": chunk["text"],
        })

    # 批量生成 embedding
    texts = [c["text"] for c in chunks_with_id]
    print(f"  [Milvus] 开始生成 {len(texts)} 条知识库分块的 embedding ...")
    embeddings = embedding_client.embed(texts, batch_size=batch_size)

    # 写入 Milvus
    data = [
        [c["chunk_id"] for c in chunks_with_id],           # chunk_id
        embeddings,                                          # embedding
        [c["source_type"] for c in chunks_with_id],         # source_type
        [c["source_id"] for c in chunks_with_id],           # source_id
        [c["text"] for c in chunks_with_id],                # text
    ]

    collection.insert(data)
    collection.flush()

    print(f"  [Milvus] knowledge_chunks 写入完成: {len(chunks_with_id)} 条")


# ════════════════════════════════════════════════════════════════════════════
# 4. 主函数
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MatchForge Milvus 种子数据生成"
    )
    parser.add_argument(
        "--products-only", action="store_true",
        help="仅同步产品数据到 product_embeddings",
    )
    parser.add_argument(
        "--knowledge-only", action="store_true",
        help="仅同步知识库到 knowledge_chunks",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Embedding API 批次大小（默认 {DEFAULT_BATCH_SIZE}）",
    )
    args = parser.parse_args()

    # 确定执行范围
    sync_products = not args.knowledge_only
    sync_knowledge = not args.products_only

    print("=" * 70)
    print("MatchForge P4 - Milvus 种子数据生成")
    print("=" * 70)
    print(f"  Milvus:     {MILVUS_HOST}:{MILVUS_PORT}")
    print(f"  MySQL:      {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    print(f"  Embedding:  {EMBEDDING_BASE_URL} / {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  批次大小:   {args.batch_size}")
    print(f"  同步产品:   {sync_products}")
    print(f"  同步知识库: {sync_knowledge}")
    print()

    # ── 校验 Embedding API 配置 ──
    if not EMBEDDING_API_KEY:
        print("[错误] EMBEDDING_API_KEY 未配置，请在 .env 中设置。")
        print(f"  参考配置: EMBEDDING_API_KEY=your-api-key")
        sys.exit(1)

    # ── 初始化 Embedding 客户端 ──
    print("[1/4] 初始化 Embedding 客户端 ...")
    try:
        embedding_client = EmbeddingClient(
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_BASE_URL,
            model=EMBEDDING_MODEL,
        )
    except Exception as e:
        print(f"[错误] Embedding 客户端初始化失败: {e}")
        sys.exit(1)

    # ── 连接 Milvus ──
    print("\n[2/4] 连接 Milvus ...")
    try:
        connect_milvus()
    except RuntimeError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    # ── 同步产品数据 ──
    if sync_products:
        print("\n[3/4] 同步产品数据 (MySQL → product_embeddings) ...")
        try:
            products = fetch_products_from_mysql()
            if products:
                upsert_product_embeddings(embedding_client, products, args.batch_size)
            else:
                print("  [提示] MySQL 中没有产品数据，请先运行 init_all.py --step mysql")
        except RuntimeError as e:
            print(f"  [错误] 产品数据同步失败: {e}")
            # 不退出，继续执行知识库同步
    else:
        print("\n[3/4] 跳过产品数据同步")

    # ── 同步知识库数据 ──
    if sync_knowledge:
        print("\n[4/4] 同步知识库 (knowledge_base_docs → knowledge_chunks) ...")
        try:
            upsert_knowledge_chunks(embedding_client, args.batch_size)
        except RuntimeError as e:
            print(f"  [错误] 知识库数据同步失败: {e}")
    else:
        print("\n[4/4] 跳过知识库数据同步")

    # ── 完成 ──
    print("\n" + "=" * 70)
    print("Milvus 种子数据生成完成!")
    print("=" * 70)
    print()
    print("验证数据:")
    print(f"  python -c \"from pymilvus import Collection, connections; "
          f"connections.connect(host='{MILVUS_HOST}', port='{MILVUS_PORT}'); "
          f"print('products:', Collection('{COLLECTION_PRODUCT}').num_entities); "
          f"print('knowledge:', Collection('{COLLECTION_KNOWLEDGE}').num_entities)\"")
    print()


if __name__ == "__main__":
    main()
