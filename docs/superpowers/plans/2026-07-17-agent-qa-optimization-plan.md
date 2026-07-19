# Agent 问答优化 · 双人执行计划

> 日期:2026-07-17 · 来源:全项目产业级审查(见当日审查记录)
> 目标:把 agent 问答从"一次性流水线"升级为市场级对话能力——**可追问、可信、可迭代、体验及格**

---

## 1. 分工原则

| 角色 | 定位 | 领地 | 边界 |
|---|---|---|---|
| **A · Agent/后端** | 精确性与可迭代 | `ai/`、`kb/`、`api/`、`tests/` | 不碰 `web/`,API 变更按契约走 |
| **B · 前端/体验** | 对话体验与引用呈现 | `web/` 全部 | 不碰 `ai/`,数据结构以契约为准 |

**第一原则:接口契约先行。** Day 1 上午两人开 30 分钟对齐会,冻结第 4 节的 4 个契约,之后各自开发,契约变更必须双方确认。

---

## 2. 工作项总表

### A 线:Agent/后端(精确性)

| ID | 工作项 | 预估 | 依赖 | 验收标准 |
|---|---|---|---|---|
| A1 | **alternatives 校验层(P0)**:输出型号必须 ∈ 工具返回集,verified 由代码赋值,电压/封装/EOL 红线代码复核,LLM 只负责解释 | 2 人日 | 无 | 构造 3 个幻觉输出(编造型号/自报 verified/红线违规)全部被拦截的单测通过 |
| A2 | 清除假精确信号:`rule_fallback` 改为显式"查询失败"态;`gen_rfq` 品名从 parsed_spec 取(删 MLCC 硬编码);confidence 语义定义(后端给真值或不给) | 1 人日 | 无 | 全链路无编造数据;非 MLCC 品类 RFQ 品名正确 |
| A3 | 测试止血:删 `test_kb_rag.py:235` 的 `or True` 并补拒答断言;`test_match.py` 对齐确定性实现 | 1 人日 | 无 | 防幻觉测试可以失败;`pytest tests/test_match.py` 全绿 |
| A4 | Prompt 清理:删死 prompt 文件(`ai/prompts/alternatives.py`);红线冲突二选一;parse 示例与"去单位"规则对齐;修 category 空校验(`parse.py:48-49`);修 match "未找到"子串判断(`match.py:176`);删 `MATCH_SYSTEM_PROMPT` 死代码;supervisor 补 `rag_enrich` 路由枚举、收敛双份 `get_supervisor_llm` | 1 人日 | 无 | 全仓无死 prompt;supervisor 单测覆盖 rag_enrich 路由 |
| A5 | **评测集 v1**:30 条真实采购问句 + 标准答案(JSONL),eval 脚本统计准确率/拒答正确率/幻觉拦截率 | 2 人日 | A1–A4 | `python scripts/eval_agent.py` 可跑,输出三项指标;此后每次改 prompt 必跑 |
| A6 | 真流式后端:chat agent `ainvoke`→`astream`,SSE 增加 token 事件,支持 abort | 1.5 人日 | 契约 C1 | curl 可观察到逐 token 事件;abort 后流终止 |
| A7 | 多轮上下文后端:state 携带已确认实体(当前 spec/替代料/供应商快照),支持"第 N 个/刚才那个"的引用解析 | 2 人日 | 契约 C4 | 追问"第二个的交期"能正确定位实体 |
| A8 | 引用透出 API:RAG 的 retrieved chunks、alternatives 真实 source 结构化进响应 | 0.5 人日 | 与 A1 同期 | API 响应含契约 C2 的 citation 字段 |

**A 线合计:11 人日**

### B 线:前端/体验(市场级体验)

| ID | 工作项 | 预估 | 依赖 | 验收标准 |
|---|---|---|---|---|
| B1 | **Markdown 渲染**:markdown-it + DOMPurify + 表格/代码块样式,接入 ChatMessage / CompanyAssistant / CompanyChat | 1 人日 | 无 | LLM 输出标题/列表/表格正确渲染;XSS 用例被过滤 |
| B2 | 消息级操作:复制按钮、时间戳渲染、错误气泡重试接通(删 `ChatView.vue:379` 空函数)、发送中 spinner 改"停止"键接 `store.abort` | 1 人日 | 无 | 每条助手消息有复制/时间;重试真实触发 |
| B3 | 错误与断线出口:SSE 解析失败不再静默(`sse.ts:57-59` 加告警事件)、断流提示 + 手动重连、失败状态可操作 | 0.5 人日 | 契约 C1 | 断网注入测试:用户可见明确错误并可重试 |
| B4 | **引用回显 UI**:RAG 答案引用角标可展开(文档名/chunk/得分);alternatives 来源徽章(区分 Neo4j 核验 / LLM 推测 / 规则兜底) | 1.5 人日 | A8、A1(B 可先用 mock 开发) | 每段 RAG 答案有点击可展开的出处 |
| B5 | **真多轮前端**:取消 `store.reset()`;结果卡片持久挂在各自消息下;AgentTimeline 可折叠并沉淀到消息;历史会话在 ChatView 内重建气泡(不再跳转向导页) | 2.5 人日 | A7 | 追问时上轮卡片不消失;刷新后可恢复 |
| B6 | 流式 UI:token 渲染、停止按钮、断流兜底 | 1 人日 | A6 | 与 A6 联调通过,生成中可随时停止 |
| B7 | 输入框状态统一:CompanyAssistant 发送中禁用;空状态示例文案对齐 | 0.5 人日 | 无 | 三处聊天入口行为一致 |

**B 线合计:8 人日**

### 共同

| ID | 事项 | 时间 |
|---|---|---|
| C0 | Day 1 上午:契约对齐会(30 min),冻结第 4 节契约 | 0.5h |
| C1 | Week 2 末:多轮 + 引用联调 | 0.5 人日 |
| C2 | Week 3 中:流式联调 + 总验收(见第 5 节) | 0.5 人日 |

---

## 3. 里程碑节奏(约 3 周)

```
Week 1  [M1 精确性止血]
  A: A1 → A2 → A3 → A4        B: B1 → B2 → B3 → B7
  出口:P0 幻觉敞口关闭;回答区 Markdown 化;错误有出口

Week 2  [M2 可信 + 可追问]
  A: A5 → A8 → A7             B: B4(mock 先行)→ B5
  出口:引用可展开;多轮追问可用;评测集首次回归跑通

Week 3  [M3 体验及格]
  A: A6 + 联调支持             B: B6 + 联调
  出口:真流式 + 可停止;总验收
```

---

## 4. Day 1 必须冻结的 4 个契约

**C1 · SSE 事件协议**
```
event: token    data: {"text": "..."}           # 增量文本
event: progress data: {"agent": "match", "status": "running|done|error", "elapsed_ms": n}
event: card     data: {"kind": "spec|alternatives|suppliers|rfq", "payload": {...}}
event: citation data: {"message_id": "...", "items": [{"doc": "...", "chunk_id": "...", "score": 0.0}]}
event: error    data: {"code": "...", "message": "对用户可见的文案", "retryable": true}
event: done     data: {"thread_id": "..."}
```
错误必须走 `error` 事件,**禁止静默吞**;无法解析的帧前端必须告警。

**C2 · Citation 字段**:RAG 答案响应带 `citations[]`,元素含 `doc / chunk_id / score / excerpt`;前端角标 [1][2] 可展开。

**C3 · confidence 语义**:0–1 浮点,后端给真值;**后端不给 = 前端不显示,任何人不得写死默认值**(废除 `stores/procure.ts:31-37` 的 0.9)。

**C4 · 多轮协议**:复用 `thread_id`;后端每轮返回 `entities` 快照(current_spec / alternatives / suppliers),前端随消息持久化。

---

## 5. 验收标准(Definition of Done)

M3 总验收必须全部通过:

1. **幻觉拦截**:向 alternatives 注入编造型号/自报 verified/红线违规各 1 例,全部被代码层拦截(A1 单测)
2. **评测回归**:`eval_agent.py` 三项指标不低于基线;改 prompt 的 PR 必须附 eval 前后对比
3. **引用可查**:任意 RAG 答案能在 UI 展开出处;alternatives 每个型号有来源徽章
4. **多轮走查**:完成"问料 → 追问第二个 → 追问交期 → 重新生成"全链路不丢上下文
5. **体验走查**:流式可见、可停止、可复制、断网有明确错误且可重试、Markdown 正常渲染
6. **测试纪律**:`pytest` 全绿,无 `or True` 式恒真断言(grep 检查)

---

## 6. 冲突文件归属(避免两人打架)

| 文件 | 归属 | 备注 |
|---|---|---|
| `ai/**`、`kb/**`、`tests/**` | A | B 需要后端改动时提需求,不动手 |
| `web/**` | B | A 需要前端配合时写进契约 |
| `api/routers/procure.py` | A | SSE 协议变更必须双方确认 |
| `web/src/api/*`、`web/src/stores/*` | B | 按契约实现 |
| 本计划文件 | 共同 | 变更当面说,不留暗改 |

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 评测集标注耗时卡进度 | 用 backend 日志/历史真实问句脱敏凑首批 30 条,不求全,边跑边补 |
| 多轮改动面大,B5+A7 耦合深 | 拆两半:前端"不 reset + 卡片持久"可独立先做;引用解析后补 |
| 两人进度不均 | 契约 + mock 先行,B4/B6 均可基于 mock 数据开发,不阻塞 |
| 改 prompt 无回归手段 | A5 完成后立门禁:无 eval 对比不许合并 prompt 变更 |
