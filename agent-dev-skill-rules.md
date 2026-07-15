---
name: agent-dev-skill-rules
description: When writing AI agent code (LangGraph/LangChain), must invoke relevant skills first
metadata:
  type: feedback
---

每次涉及以下任务时，**必须先调用对应 Skill** 再写代码，不得跳过：

| 任务 | 必调 Skill |
|---|---|
| LangGraph 图编排 (supervisor.py, state.py) | `langgraph-persistence`, `langgraph-human-in-the-loop` |
| LLM 调用 / Prompt 设计 (agents/parse.py, alternatives.py) | `langchain-fundamentals` |
| LLM 中间件 / 可观测 (trace/日志) | `langchain-middleware` |
| RAG / 向量检索 (tools/milvus_client.py) | `langchain-rag` |
| FastAPI 路由 / SSE | `fastapi-python` |

**Why:** 之前写前端和 AI Agent 时两次跳过了该调用的 Skill，代码风格和最佳实践有提升空间。
**How to apply:** 在上述任务的文件创建/修改前，先调 Skill 加载指南，再动手写代码。Skill 的 Base directory 包含领域知识文档，需要先读取再实践。
