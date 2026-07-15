"""
Embedding 客户端 -- 复用 ai/config.py 的 DashScope text-embedding-v3 配置。

- 真实模式: openai SDK 调用 EMBEDDING_API_KEY (1024 维)
- 降级模式: 无 API Key 时使用确定性 hash-bag-of-words 向量 (同样 1024 维)。
  特点: 同一文本恒定同一向量; 含相同关键词的文本余弦相似度更高 -> 满足检索测试。
  仅用于 dev/test/demo, 不会混入真实向量库 (vector_backend 标记区分)。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
from collections import Counter

from kb.config import EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_DIM, EMBEDDING_MODEL, KB_EMBED_BATCH, embedding_available

logger = logging.getLogger("kb.embedder")

_client = None
_DIM = int(EMBEDDING_DIM)


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL, timeout=60)
    return _client


# ============================================================
# 降级: 确定性 hash-bow 向量
# ============================================================
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")


def _tokenize(text: str) -> list[str]:
    """中英文混合分词: 英文按单词, 中文按单字 (再组 2-gram)。"""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        tokens.append(raw)
    # 中文 2-gram 增强语义
    chars = [c for c in text if "一" <= c <= "鿿"]
    for i in range(len(chars) - 1):
        tokens.append(chars[i] + chars[i + 1])
    return tokens


def _hashbow_vector(text: str) -> list[float]:
    """确定性 hash bag-of-words 向量, L2 归一化。"""
    vec = [0.0] * _DIM
    toks = _tokenize(text)
    if not toks:
        return vec
    counts = Counter(toks)
    for tok, cnt in counts.items():
        h = hashlib.md5(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "little") % _DIM
        sign = 1.0 if (h[4] & 1) else -1.0
        # token 长度加权: 长英文词权重更高
        w = sign * cnt * (1.0 + math.log2(len(tok) + 1))
        vec[idx] += w
    # L2 归一化
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


# ============================================================
# 统一接口
# ============================================================


def embed_text(text: str) -> list[float]:
    """单条文本 embedding (同步)。"""
    vecs = embed_batch([text])
    return vecs[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """批量 embedding。真实模式走 API, 否则降级。"""
    if not texts:
        return []
    if embedding_available():
        try:
            return _embed_api(texts)
        except Exception as e:
            logger.warning("Embedding API 失败, 降级 hashbow: %s", str(e)[:160])
    return [_hashbow_vector(t) for t in texts]


async def embed_batch_async(texts: list[str]) -> list[list[float]]:
    """异步批量 embedding, 分批 + 并发控制。"""
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), KB_EMBED_BATCH):
        batch = texts[i : i + KB_EMBED_BATCH]
        out.extend(await asyncio.to_thread(embed_batch, batch))
    return out


def _embed_api(texts: list[str]) -> list[list[float]]:
    client = _get_client()
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    # 按 index 排序确保顺序
    data = sorted(resp.data, key=lambda d: d.index)
    return [list(map(float, d.embedding)) for d in data]


def embedder_info() -> dict:
    return {
        "available": embedding_available(),
        "model": EMBEDDING_MODEL,
        "dim": _DIM,
        "base_url": EMBEDDING_BASE_URL,
    }
