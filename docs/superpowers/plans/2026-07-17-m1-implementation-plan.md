# M1 四件套实现计划(#16 #17 #18 #19)

范围:仅 M1 的 4 个无依赖任务。M2/M3 后续。前端不动(web/ 归 B 线)。
契约:本计划附 C1-C4 契约草案(M1 不直接需要,为 M2/M3 铺路 + #19 路由触及)。

执行顺序:#18(测试止血)→ #19(prompt/路由清理)→ #16(校验层,P0)→ #17(假精确清除)。
理由:#18 先建立"测试真的会失败"的防护网;#19 清理死代码/路由让 #16 在干净基底上做;#16 是 P0 核心;#17 收尾。

---

## 任务 1:#18 测试止血

### 问题
1. `tests/test_kb_rag.py:235` `assert ... or True` 恒真 → `TestFactualHallucination` 永不失败
2. `tests/test_match.py` mock `run_direct_agent` 并断言 LLM 输出,但 `match.py` 已是确定性代码(阶段4直接计算评分,**从不调用 `run_direct_agent`**)→ 测试虽绿但测的是假东西,回归无防护

### 改动

**A. `tests/test_kb_rag.py:228-235` `TestFactualHallucination.test_no_fabrication_for_nonexistent`**
- 删除 `or True`
- 改为真实断言:注入幻觉场景下必须失败。现有断言 `"暂无" in answer or "可支持" in answer or "不会编造" in answer or len(retrieved)==0` 已经是合理的"拒答"判定,删掉 `or True` 后即生效
- 补一个反向测试 `test_fabrication_assertion_actually_fails`:用一个**会编造**的 mock answer 验证断言确实能抓到(证明测试不是恒真)

**B. `tests/test_match.py` 按确定性实现重写**
现状:`match.py` 阶段4 直接程序化计算 `match_score = brand_score*0.7 + location_score + rag_score + 0.1`,不调 LLM。测试却全程 mock `run_direct_agent`。

重写为测确定性逻辑:
- `test_match_agent_empty_spec`:保留(已正确)
- `test_match_agent_no_suppliers_from_db`:保留(已正确)
- `test_match_agent_rag_called_for_each_supplier`:保留,但去掉 `run_direct_agent` mock(实现里没有这个调用),改为断言 RAG 被每个供应商调用一次
- `test_match_agent_score_calculation`(新):mock `filter_suppliers_raw` 返回 2 个供应商(品牌覆盖不同),mock RAG 返回固定文本,断言 `match_score` 按公式正确计算、按降序排列、品牌全覆盖者分更高
- `test_match_agent_rag_failure_graceful`:改为断言单个供应商 RAG 异常时该供应商 `rag_insights` 含异常提示但流程不中断、仍输出结果
- `test_match_agent_confirmed_flags`:断言所有供应商 `confirmed_stock/confirmed_lead/confirmed_price` 均为 False(红线)
- `test_match_agent_empty_rag_no_score_boost`(新):RAG 返回"未在知识库中找到"时,`rag_score` 应为 0(对应 #19 修的 bug)
- 删除 `test_match_agent_enriched_data_passed_to_llm`(测的是不存在的 LLM 调用)

**C. 全仓 grep 检查同类恒真断言**
`grep -rn "or True" tests/` → 逐一审查,删除非预期的。

### 验收
- `pytest tests/test_match.py tests/test_kb_rag.py -v` 全绿
- 注入幻觉时 `test_no_fabrication_for_nonexistent` 确实失败(用反向测试证明)

---

## 任务 2:#19 Prompt 清理与 supervisor 路由修复

### 问题清单(逐条)

**1. 死 prompt 文件** `ai/prompts/alternatives.py` 与活文件 `ai/agents/alternatives.py:35-101` 冲突:
- 死文件:电压降级→`risk`、置信度阈值 0.7
- 活文件:电压降级→不推荐、阈值 0.5
- 方案:**删 `ai/prompts/alternatives.py`**,红线统一用活文件版本(电压降级→不推荐,阈值 0.5)。先 grep 确认无 import。

**2. parse prompt few-shot 矛盾** `ai/prompts/parse.py`:
- 规则说"数值去掉单位存储"(`:27`)
- few-shot 却输出 `"rated_voltage": "10V"`/`"50V"` 带单位(`:42,51,64`)
- 方案:规则与示例对齐。**保留带单位**(示例更实用,前端展示需要单位),改规则为"额定电压/容值等保留单位字符串存储"。同步检查 `parse.py:_validate_spec` 无强制转数字逻辑(确认现状兼容)。

**3. category 校验空操作** `ai/agents/parse.py:48-49`:
```python
cat = str(val).strip()
cleaned[key] = cat if cat in VALID_CATEGORIES else cat  # 两分支相同
```
- 方案:改为 `cleaned[key] = cat if cat in VALID_CATEGORIES else ""`(不在白名单则丢弃),或保留原值但记 warning。选**丢弃**(宁缺毋假,与 #17 精神一致)。

**4. match rag 加分判断失效** `ai/agents/match.py:176`:
```python
rag_score = 0.05 if rag and rag != "知识库检索异常" and "未找到" not in rag else 0.0
```
而 `kb_client.py:117` 实际返回 `"未在知识库中找到企业..."` → `"未找到" not in rag` 为 True → 未命中也加分。
- 方案:抽取一个 `_rag_is_empty(text)` 辅助函数,匹配所有"无结果"文案:`"未在知识库中找到"`、`"暂未收录"`、`"知识库系统当前不可用"`、`"检索异常"`、空串。rag_score 仅在有真实内容时给。

**5. 死代码** `ai/agents/match.py:26-78` `MATCH_SYSTEM_PROMPT` 定义后从未使用(实现已确定性化,不调 LLM)。
- 方案:删除该常量。grep 确认无外部引用。

**6. 路由残废**:
- `ai/supervisor.py:118` `RouteDecision.agent` 枚举缺 `rag_enrich` → LLM 永远无法合法选中,只能靠 `ROUTING_ORDER` 顺序兜底(`:268`)。但 `ROUTING_ORDER:80` 已含 `rag_enrich`,且 `_AGENT_MAP` 已注册。问题是 LLM 结构化输出无法返回 `rag_enrich`(枚举校验会拒)。
  - 方案:`RouteDecision.agent` 的 `Literal` 加入 `"rag_enrich"`。同步更新 `test_supervisor_route.py` 的 `VALID_AGENTS`(`:15`)。
- `get_supervisor_llm` 双份定义:`supervisor.py:125-145`(max_tokens=1024, timeout=20)vs `base_agent.py:81-99`(max_tokens=64, timeout=10),参数漂移。
  - 方案:**删 `base_agent.py:81-99` 的 `get_supervisor_llm`**,统一用 `supervisor.py` 版本(参数更合理:glm-5.2 是推理模型,需要思考预算,注释已说明)。grep 确认所有调用方 import 自 `ai.supervisor` 或 `ai.base_agent`,统一改为 `from ai.supervisor import get_supervisor_llm`。注意 `conftest.py:54` 同时 patch 了两个,改为只 patch `ai.supervisor.get_supervisor_llm`。

### 验收
- 全仓无 `ai/prompts/alternatives.py`;无 `MATCH_SYSTEM_PROMPT` 死代码
- `RouteDecision` 枚举含 `rag_enrich`;新增 supervisor 单测覆盖 `rag_enrich` 路由
- `get_supervisor_llm` 全仓仅一份定义
- `pytest tests/test_supervisor*.py tests/test_parse.py tests/test_match.py` 全绿
- match 未命中场景不再加分(新测试覆盖)

---

## 任务 3:#16 alternatives 输出校验层(P0)

### 核心问题
`ai/agents/alternatives.py`:替代型号/等级/置信度/verified/source 全由 LLM 自报;`base_agent.parse_json_from_llm` 仅正则提取 JSON,无 schema 校验、无与工具返回交叉核对。LLM 可编造型号并自报 `verified=true, source="Neo4j:direct"` 直达用户。安全红线纯靠 prompt。

### 设计:校验层放在 `alternatives_agent` 内,LLM 输出后、`_format_for_frontend` 前

**关键挑战**:LLM 在 `run_tool_agent` 里自主调工具,工具返回进了 LLM 上下文,但 `alternatives_agent` 拿不到工具返回的型号集合。需要改造 `run_tool_agent` 支持回传工具调用记录,或在 `alternatives_agent` 层 hook。

**方案:给 `run_tool_agent` 增加可选的 `tool_call_sink` 回调**(最小侵入):
- `run_tool_agent(state, system_prompt, tools, ..., tool_call_sink=None)`:每次工具执行后,若 `tool_call_sink` 非 None,调用 `tool_call_sink(tool_name, tool_args, output)`。
- `alternatives_agent` 传入一个 sink,收集所有 Neo4j/search_knowledge_base 工具返回的型号集合 `tool_returned_parts: set[str]`。
- 从 `query_*` 工具返回的 dict 里提取型号(字段名:`part`/`part_number`/`alt_part`/`equivalent` 等,做容错);从 `search_knowledge_base` 返回的文本里正则提取型号。

**校验逻辑 `_validate_alternatives(alts, tool_parts, spec) -> list[dict]`**(新函数,在 `alternatives.py`):

1. **型号拦截**:每个 alt 的 `part` 必须在 `tool_parts` 集合内,否则丢弃(记 warning)。例外:`rule_fallback` 来源的型号(走 `_rule_based_fallback`,已知是代码生成的,允许通过,但 source 标 `rule_fallback`)。
   - 若 LLM 全部幻觉(无任何型号命中)→ 返回空列表 + errors 记录,宁缺毋假。

2. **verified/source 代码赋值**:
   - `verified`:若型号 ∈ Neo4j 工具返回且工具返回里有该型号 → True;否则 False。**不接受 LLM 填报**。
   - `source`:根据工具来源赋值。Neo4j 工具返回的标 `"Neo4j:direct/transitive/cross_ref/all"`;search_knowledge_base 验证过的追加 `"+RAG"`;LLM 推理(型号在工具集合但非 Neo4j 来源)标 `"llm_inferred"`;rule_fallback 标 `"rule_fallback"`。**不接受 LLM 填报**。

3. **红线代码复核** `_check_safety(alt, spec) -> bool`(不推荐则返回 False 并记录原因):
   - 电压降级:解析 alt.rated_voltage 与 spec.rated_voltage 的数值,alt < original → 不推荐
   - 封装不同:alt.package != spec.package 且无桥接 → 不推荐(L4 降级为不推荐?需斟酌:封装不同是 L4,issue 说"封装不同不推荐"。按 issue:封装不同→不推荐,从输出移除)
   - EOL:alt.lifecycle 含"停产"/"EOL"/"Obsolete" → 不推荐
   - 温度系数跨级(C0G→Y5V)→ 不推荐
   - 按 issue:红线违规的从 alternatives 移除(不是标 risk,是不推荐=移除)

4. **confidence 代码复核**:LLM 自报的 confidence 保留作为 `llm_confidence`,但代码计算一个 `verified_confidence`:verified=True 给 0.8+,否则 ≤0.5。前端用哪个?契约 C3:后端不给=前端不显示。M1 阶段保留 LLM confidence 但标注 verified 状态,#17 配合。

5. **LLM 只负责解释文案**:`reason`/`diff_items` 的文字描述保留 LLM 输出,但 diff_items 的 `type`(match/diff/risk)由代码根据参数比对重新判定(不信任 LLM 标的 risk)。

### 改动文件
- `ai/base_agent.py`:`run_tool_agent` 加 `tool_call_sink` 参数
- `ai/agents/alternatives.py`:
  - 新增 `_collect_tool_parts(sink)` 机制
  - 新增 `_validate_alternatives(alts, tool_parts, spec)` 
  - 新增 `_check_safety(alt, spec)`
  - 新增 `_recompute_diff_types(alt, spec)`(diff_items type 代码复核)
  - `alternatives_agent` 主流程:工具调用带 sink → 解析 LLM 输出 → `_validate_alternatives` → `_format_for_frontend`
- `tests/test_alternatives.py`:新增 3 个幻觉拦截单测(issue 验收要求):
  - `test_hallucinated_part_intercepted`:LLM 返回编造型号(不在工具集合)→ 被拦截,结果为空或仅含合法型号
  - `test_self_reported_verified_overridden`:LLM 自报 `verified=true, source="Neo4j:direct"` 但型号不在 Neo4j 返回里 → 代码改写为 verified=false
  - `test_redline_violation_intercepted`:LLM 返回电压降级/EOL 型号 → 代码移除
  - 重写现有 `test_alternatives_agent_neograph_hit` 等:mock 工具返回而非仅 mock `run_tool_agent` 整体(因为现在要校验工具返回)。用 `tool_call_sink` 或直接 mock `run_tool_agent` 返回 + 手动构造 tool_parts。

### 验收(issue 原文)
构造 3 个幻觉输出(编造型号 / 自报 verified / 红线违规)的单测,全部被代码层拦截。

---

## 任务 4:#17 清除三处"假精确"信号

### 问题
1. 前端 `web/src/stores/procure.ts:31-37` 写死 `confidence: 0.9` —— **前端不动**,A 线负责后端语义定义。后端 `parsed_spec`/`normalized_spec` 当前是裸键值对,不携带 confidence。契约 C3:后端不给 confidence=前端不显示。M1 阶段:后端保持不输出 confidence(现状),在 `ai/state.py` 或契约文档明确"spec 字段不含 confidence,前端不得写死"。代码侧无需改动后端,但需在契约文档写清,并在 `parse.py`/`normalize.py` 注释标注。
2. `ai/agents/alternatives.py:230-317` `_rule_based_fallback` 硬编码"已知替代料"照常进正式输出流,且 `:239` reason 自相矛盾("参数兼容(容值不同:1uF->10uF)")。
   - 方案:`_rule_based_fallback` 改为显式"查询失败"态:返回的 alt 加 `source="rule_fallback:query_failed"`,且 `confidence` 降为 ≤0.3,`verified=False`,reason 修正为"系统查询失败,以下为规则兜底建议,仅供参考,需人工核验"。修复 `:239` 矛盾 reason(容值不同不应说"参数兼容",改为"容值不同,需工程确认")。
   - 进一步:issue 说"宁缺毋假"。考虑 `_rule_based_fallback` 的硬编码 `_KNOWN_ALTERNATIVES` 是否还应进正式输出?决策:**保留但明确降级标注**(完全不输出会让 LLM/Neo4j 双挂时前端空白,体验更差;明确标"兜底未核验"更诚实)。`_format_for_frontend` 对 `rule_fallback` 来源统一加 `note`。
3. `ai/agents/gen_rfq.py:31` RFQ 品名硬编码"多层陶瓷贴片电容(MLCC)"。
   - 方案:从 `parsed_spec` 取 `category`,映射到中文品名(`MLCC`→"多层陶瓷贴片电容(MLCC)"、`钽电容`→"钽电容"、`电阻`/`贴片电阻`→"贴片电阻"、`电感`→"电感"、`连接器`→"连接器"、`IC`→"集成电路(IC)"、`二极管`→"二极管"、`晶振`→"晶振"、`MOSFET`→"MOSFET"),无 category 时用"电子元器件"。

### 改动文件
- `ai/agents/alternatives.py`:`_rule_based_fallback` 降级标注 + reason 修正;`_format_for_frontend` 对 rule_fallback 加 note
- `ai/agents/gen_rfq.py`:`build_rfq_template` 品名从 spec 取,加 `_category_to_name` 映射
- `tests/test_gen_and_grade.py`:新增非 MLCC 品类 RFQ 品名正确测试
- `tests/test_alternatives.py`:新增 rule_fallback 降级标注测试

### 验收
- 全链路无编造数据(rule_fallback 明确标注未核验)
- 非 MLCC 品类生成的 RFQ 品名正确(单测覆盖)

---

## 附:契约草案(C1-C4)— 写入 `docs/superpowers/plans/2026-07-17-contracts.md`

为 M2/M3 铺路,#19 路由修复时同步落契约文档。

**C1 - SSE 事件协议**(供 #24):
```
data: {"type":"start","thread_id":"...","phase":"spec|match"}
data: {"type":"progress","agent":"parse|normalize|alternatives|match|gen_rfq|grade|chat|rag_enrich","status":"running|done|error","result":<agent输出>}
data: {"type":"token","agent":"chat|rag_enrich","text":"..."}      // 逐 token(M3 改为真流式)
data: {"type":"citation","agent":"alternatives|rag_enrich","citations":[...]}  // C2
data: {"type":"result","state":{...完整 state...}}
data: {"type":"end","thread_id":"..."}
abort: 客户端断连 → 后端取消未完成的 LLM astream(M3)
```

**C2 - citation 字段**(供 #22):
```json
// RAG 答案响应内
"citations": [{"doc":"manual_type","chunk_id":"...","chunk_uid":"...","score":0.87,"excerpt":"...","company_id":1}]
// alternatives 每项内
"source":"Neo4j:direct|Neo4j:direct+RAG|llm_inferred|rule_fallback:query_failed"  // #16 已实现
```

**C3 - confidence 语义**(供 #17 前端):
```
后端 spec 字段(parsed_spec/normalized_spec)不携带 confidence。
后端不输出 = 前端不得显示(禁止写死 0.9)。
alternatives.confidence 保留(LLM 自评 + 代码 verified 标注),前端可显示但须配合 verified 徽章。
```

**C4 - 多轮 entities 快照**(供 #23):
```json
// 每轮响应 state 内
"entities_snapshot": {
  "current_spec": {...},
  "alternatives": [...],     // 上一轮替代料列表(供"第二个"引用解析)
  "matched_suppliers": [...]
}
// 引用解析:"第N个/刚才那个/它" → 定位到 entities_snapshot.alternatives[N-1]
// 复用 thread_id,不重建会话
```

---

## 验证策略

每个任务完成即跑相关测试:
- #18:`pytest tests/test_match.py tests/test_kb_rag.py -v`
- #19:`pytest tests/test_supervisor.py tests/test_supervisor_route.py tests/test_supervisor_advanced.py tests/test_parse.py tests/test_match.py -v`
- #16:`pytest tests/test_alternatives.py -v`(重点新幻觉拦截测试)
- #17:`pytest tests/test_alternatives.py tests/test_gen_and_grade.py -v`

全量回归:`pytest tests/ -v`(排除需外部依赖的 kb_rag/enterprise 等若环境不全)

## 风险与备注
- #16 的 `tool_call_sink` 改造 `run_tool_agent` 是公共函数,需确认不影响 normalize/match 等其它调用方(它们不传 sink,行为不变)。
- #16 工具返回型号提取需容错多种字段名,可能漏提取导致误拦截 → 提取逻辑要宽松,拦截要保守(宁可放过也不误杀合法型号?不,issue 要求严格拦截幻觉 → 拦截优先,但提取要尽量全)。
- #19 删 `base_agent.get_supervisor_llm` 需确认 `ai.config.SUPERVISOR_MODEL` 在 supervisor.py 已 import(已确认 `:29`)。
- 前端 0.9 写死(#17)本次不动,契约 C3 文档 + 代码注释标注,留给 B 线。
- 不动 `web/`、不动 `api/routers/procure.py` 的 SSE 协议(契约变更需双方确认,#30)。
