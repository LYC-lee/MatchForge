"""
LLM 客户端 -- 复用 ai/config.py 的 DashScope (Qwen, OpenAI 兼容) 配置。

- 真实模式: 通过 openai SDK 调用 (复用现有 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL)
- 降级模式: 当前环境 DASHSCOPE_API_KEY 为空时, 不调用外部 API,
  由 generator.py 的模板生成器保证知识产出 (业务边界内, 可控、可复现)

不新增 AI 供应商; 不硬编码密钥。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from kb.config import (
    KB_LLM_CONCURRENCY,
    KB_LLM_MAX_RETRIES,
    KB_LLM_MAX_TOKENS,
    KB_LLM_TIMEOUT,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_MODEL_LIGHT,
    llm_available,
)

logger = logging.getLogger("kb.llm")

_client = None
_sem = asyncio.Semaphore(KB_LLM_CONCURRENCY)


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=KB_LLM_TIMEOUT)
    return _client


def _backoff(attempt: int) -> float:
    return min(2.0 ** attempt, 16.0)


async def chat_json(
    system: str,
    user: str,
    *,
    heavy: bool = True,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> dict | None:
    """调用 LLM 并解析 JSON。失败返回 None (由调用方降级)。"""
    if not llm_available():
        return None
    model = LLM_MODEL if heavy else LLM_MODEL_LIGHT
    max_t = max_tokens or KB_LLM_MAX_TOKENS
    last_err = None
    for attempt in range(1, KB_LLM_MAX_RETRIES + 1):
        try:
            async with _sem:
                resp = await asyncio.to_thread(
                    _call_chat,
                    model,
                    system,
                    user,
                    temperature,
                    max_t,
                    timeout or KB_LLM_TIMEOUT,
                )
            if resp is None:
                raise RuntimeError("empty response")
            return _parse_json(resp)
        except Exception as e:
            last_err = e
            logger.warning("LLM 调用失败 (attempt %d/%d): %s", attempt, KB_LLM_MAX_RETRIES, str(e)[:160])
            if attempt < KB_LLM_MAX_RETRIES:
                await asyncio.sleep(_backoff(attempt))
    logger.error("LLM 最终失败: %s", str(last_err)[:200])
    return None


async def chat_text(
    system: str,
    user: str,
    *,
    heavy: bool = False,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> str | None:
    """调用 LLM 返回纯文本。失败返回 None。"""
    if not llm_available():
        return None
    model = LLM_MODEL if heavy else LLM_MODEL_LIGHT
    max_t = max_tokens or KB_LLM_MAX_TOKENS
    last_err = None
    for attempt in range(1, KB_LLM_MAX_RETRIES + 1):
        try:
            async with _sem:
                resp = await asyncio.to_thread(
                    _call_chat,
                    model,
                    system,
                    user,
                    temperature,
                    max_t,
                    timeout or KB_LLM_TIMEOUT,
                )
            return resp or ""
        except Exception as e:
            last_err = e
            if attempt < KB_LLM_MAX_RETRIES:
                await asyncio.sleep(_backoff(attempt))
    logger.error("LLM chat_text 最终失败: %s", str(last_err)[:200])
    return None


def _call_chat(model, system, user, temperature, max_tokens, timeout) -> str | None:
    client = _get_client()
    # 推理模型 (如 glm-5.2) 将思考放在 reasoning_content, 最终答案在 content;
    # 需要更大 max_tokens 让模型完成推理后输出 content。
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    msg = resp.choices[0].message
    content = msg.content or ""
    # 推理模型可能因 max_tokens 不足导致 content 为空 (finish_reason=length);
    # 兜底: 若 content 为空但有 reasoning_content, 取 reasoning_content 末段作为答案
    if not content.strip():
        rc = getattr(msg, "reasoning_content", None)
        if rc:
            # reasoning_content 含思考过程, 取最后一段非步骤文本作为兜底
            lines = [l.strip() for l in rc.split("\n") if l.strip()]
            content = lines[-1] if lines else rc
        # 若仍空且因 length 截断, 重新请求更大 max_tokens
        if not content.strip() and resp.choices[0].finish_reason == "length":
            bigger = min(max_tokens * 3, 16000)
            resp2 = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=bigger,
                timeout=timeout,
            )
            content = resp2.choices[0].message.content or ""
            if not content.strip():
                rc2 = getattr(resp2.choices[0].message, "reasoning_content", None)
                if rc2:
                    lines = [l.strip() for l in rc2.split("\n") if l.strip()]
                    content = lines[-1] if lines else rc2
    return content or None


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    # 去除 ```json 围栏
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    raw = m.group(1) if m else text
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        # 尝试找第一个 { 到最后一个 }
        s = raw.find("{")
        e = raw.rfind("}")
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(raw[s : e + 1])
            except Exception:
                return None
    return None


def llm_info() -> dict:
    return {
        "available": llm_available(),
        "model_heavy": LLM_MODEL,
        "model_light": LLM_MODEL_LIGHT,
        "base_url": LLM_BASE_URL,
    }
