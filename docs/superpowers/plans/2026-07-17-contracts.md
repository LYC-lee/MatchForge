# MatchForge Agent QA 优化 - 契约冻结 (C1-C4)

> 对应 issue #30 的 C0 检查点:契约对齐会。本文件冻结 4 个契约,供 A 线(后端 ai/kb/tests/api)与 B 线(前端 web)对接。
> **契约变更必须双方确认。** 任何单方改动协议字段/事件类型均视为破坏性变更。

状态:🌱 A 线代拟草案 (M1 阶段) | ⏳ 待 B 线会签

---

## C1 - SSE 事件协议

适用于 `POST /api/v1/procure/stream` 的 Server-Sent Events 流。每个事件一行 `data: <json>\n\n`。

| 事件类型 | 载荷 | 时机 |
|---|---|---|
| `start` | `{thread_id, phase}` | 流开始 |
| `progress` | `{agent, status, result}` | Agent 执行进度。`agent` ∈ `chat\|parse\|normalize\|alternatives\|match\|rag_enrich\|gen_rfq\|grade`;`status` ∈ `running\|done\|error`;`result` 为该 Agent 的输出(类型随 agent 变) |
| `token` | `{agent, text}` | 逐 token 流式文本。`agent` ∈ `chat\|rag_enrich`(M3 后扩展到所有文本 Agent) |
| `citation` | `{agent, citations[]}` | 引用透出(见 C2)。`agent` ∈ `alternatives\|rag_enrich` |
| `result` | `{state}` | 最终完整 state 快照 |
| `end` | `{thread_id}` | 流结束 |

**abort**: 客户端断连(Connection: close / AbortController)后,后端应取消未完成的 LLM astream(M3 #24 实现)。M1 阶段 abort 仅停止前端接收,后端流仍跑完(已知限制)。

**当前实现状态**(M1):
- `token` 事件目前是"伪流式":后端拿到完整文本后切片 4 字符发(`ai/graph.py:336-340`)。M3 #24 改为真 astream。
- `citation` 事件 M1 未发,M2 #22 实现。

---

## C2 - citation 字段

RAG 答案与替代料必须透出真实来源,信任链不断在最后一厘米。

### RAG 问答响应内
```json
"citations": [
  {
    "doc": "product|business",        // manual_type
    "chunk_id": "...",
    "chunk_uid": "...",
    "score": 0.87,
    "excerpt": "...",                  // 命中片段
    "company_id": 1,
    "language": "zh|en"
  }
]
```
数据源:`kb/rag.py` 的 `retrieved` (已含 chunk_id/chunk_uid/score/language,见 `_trace_chunk`)。M2 #22 在 alternatives/rag_enrich 响应中透出。

### alternatives 每项内
```json
"source": "Neo4j:direct|Neo4j:direct+RAG|Neo4j:transitive|Neo4j:cross_ref|Neo4j:all|llm_inferred|llm_inferred+RAG|rule_fallback:query_failed"
```
**已在 M1 #16 实现**:`source` 由代码赋值(不信任 LLM),前端据此渲染来源徽章:
- `Neo4j:*` -> 图谱核验(绿)
- `llm_inferred*` -> LLM 推测(黄)
- `rule_fallback:query_failed` -> 查询失败兜底(红,须人工核验)

---

## C3 - confidence 语义

**核心规则:后端不输出 = 前端不得显示。禁止写死。**

| 字段 | 后端是否输出 | 前端行为 |
|---|---|---|
| `parsed_spec.*.confidence` | ❌ 不输出 | ❌ 不显示(禁止写死 0.9) |
| `normalized_spec.*.confidence` | ❌ 不输出 | ❌ 不显示 |
| `alternatives[].confidence` | ✅ 输出(LLM 自评 + 代码 verified 约束) | ✅ 可显示,须配合 `verified` 徽章 |
| `matched_suppliers[].match_score` | ✅ 输出(程序化计算) | ✅ 可显示 |

**M1 #17 当前状态**:
- 后端 `parsed_spec`/`normalized_spec` 保持裸键值对,不携带 confidence(现状正确)。
- ⚠️ **待 B 线修复**:`web/src/stores/procure.ts:31-37` `toSpecFieldFormat` 给每个规格字段写死 `confidence: 0.9`。B 线需移除该写死逻辑,改为后端不提供则不显示(字段缺失/置空)。
- `alternatives[].confidence` 已在 #16 加约束:未核验(verified=false)上限 0.5。

---

## C4 - 多轮 entities 快照

多轮上下文:实体快照跨轮保留 + 轻量引用解析。复用 `thread_id`,不重建会话。

### 每轮响应 state 内新增
```json
"entities_snapshot": {
  "current_spec": { /* normalized_spec */ },
  "alternatives": [ /* 上一轮替代料列表, 供"第二个"引用解析 */ ],
  "matched_suppliers": [ /* 上一轮供应商列表 */ ]
}
```

### 引用解析
- "第 N 个" / "刚才那个" / "它" / "第二个的交期" -> 定位到 `entities_snapshot.alternatives[N-1]`
- 解析失败 -> 引导用户明确指代,不编造

### 当前实现状态
- M1 未实现(假多轮:前端 `store.reset()` 每轮清空)。M2 #23 实现。
- `ProcureState` 已有 `alternatives`/`matched_suppliers` 字段(append reducer),跨轮保留仅需前端不在每轮 reset + 后端按 thread_id 恢复快照。

---

## 冲突文件归属 (来自 #30)

| 路径 | 归属 |
|---|---|
| `ai/**` `kb/**` `tests/**` | A 线 |
| `web/**` | B 线 |
| `api/routers/procure.py` | A 线,但 **SSE 协议(C1)变更需双方确认** |
| `web/src/api/*` `web/src/stores/*` | B 线 |

---

## M1 交付状态 (本次)

| 契约 | M1 状态 | 备注 |
|---|---|---|
| C1 | 部分实现 | 事件类型已就位;`token` 伪流式(M3 改真流式);`citation` 未发(M2) |
| C2 | 部分实现 | alternatives.source 已代码赋值(#16);RAG citations 未透出(M2 #22) |
| C3 | 后端就绪 | 后端不输出 spec confidence;⚠️ 前端 0.9 写死待 B 线移除 |
| C4 | 未开始 | M2 #23 |
