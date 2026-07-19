# MatchForge P0 清零五人任务清单

> 生成日期：2026-07-18  
> 来源：`audit/00-总报告.md`、`audit/04-后端架构与API.md`、`audit/05-安全.md`、`audit/08-测试与质量.md`  
> 目标：7 天内清零 P0，先做到“能启动、不泄露、不撒谎、AI 寻源闭环真实落库、演示路径无必现错误”。  
> GitHub 仓库：`LYC-lee/MatchForge`

## 分配总览

| 难度 | 负责人邮箱 | GitHub | 任务 |
|---|---|---|---|
| 最难 | 2108187858lyc@gmail.com | `LYC-lee` | P0-01 AI 寻源到真实 RFQ/线索闭环 |
| 第二难 | li17796895352@163.com | `Fqflmy` | P0-02 安全授权清零 |
| 第三难 | 584092727@qq.com | `littleZHL0038` | P0-03 CI/测试隔离/AI 观测/知识状态 |
| 第四难 | 2301285887@qq.com | `ccgt117` | P0-04 启动三连修 + mysql_client 真 schema |
| 最简单 | 13227860556@163.com | `fzy-710` | P0-05 UI 五连修 |

---

## Issue 1

### Title

P0-01｜打通 AI 寻源到真实 RFQ/线索闭环（C1/D1/D5）

### Assignee

`LYC-lee`

### Body

#### 背景

审计结论显示，项目宣称的“需求 → 替代 → 询价 → 线索推送 → 报价/比价”闭环中，AI 寻源链最后两环是断的：

- `ai/agents/gen_rfq.py` 生成的 `rfq_id` 只是内存文本，不写真实 RFQ 表。
- `grade.py` 只通过 SSE 返回分级结果，不落供应商线索。
- 前端“标记已发送”只改本地 flag，不调用真实 `/rfqs/{id}/send`。
- 真实 RFQ 闭环在 `api/routers/rfqs.py` / `supplier_leads.py` / `audit.py` 中可用，但与 AI 寻源链断开。

#### 目标

把 AI 寻源链生成的 RFQ 接到真实 `RfqRecord` / supplier leads / quotation loop，使用户从 AI 对话内完成需求输入后，数据库里能留下可追溯 RFQ，并能推送到上游供应商工作台。

#### 范围

- `ai/agents/gen_rfq.py`
- `ai/agents/grade.py`
- `api/routers/procure.py`
- `api/routers/rfqs.py`
- `api/routers/supplier_leads.py`
- `web/src/stores/procure.ts`
- `web/src/views/ChatView.vue`
- `web/src/components/procure/RfqEditor.vue`
- 相关 tests

#### 任务清单

- [ ] 梳理 AI 链路当前 RFQ payload：需求、规格、替代料、候选供应商、分级结果。
- [ ] 将 `gen_rfq` 生成结果映射为真实 `POST /rfqs` 所需字段。
- [ ] 在 SSE 结束前或显式发送动作时创建真实 RFQ 记录。
- [ ] 将候选供应商写入 `supplier_candidates`，并通过 `/rfqs/{id}/send` 生成 supplier leads。
- [ ] 将 `grade` 结果落到 supplier lead 的 `match_score/match_reason` 或兼容字段。
- [ ] 前端“发送/标记已发送”必须调用真实后端接口，不再只改本地 flag。
- [ ] 确保生成后的 RFQ 可在买方 RFQ 列表、供应商线索、报价对比中看到。
- [ ] 保持 demo 沙盘模式和正式 RFQ 模式边界清晰。
- [ ] 补充链路级测试：AI 生成 RFQ → DB 有 RFQ → supplier leads 可见。

#### 验收标准

- [ ] 从 AI 寻源输入开始，完整跑通一次“需求 → 替代料 → RFQ → 供应商线索”。
- [ ] 数据库中出现真实 `kb_rfqs` 记录，且不是内存 ID。
- [ ] 对应供应商能在 `/suppliers/{company_id}/leads` 查到线索。
- [ ] 前端不再只显示本地“已发送”状态。
- [ ] RFQ 详情页/报价对比页能读取该 RFQ。
- [ ] 失败时前端显示明确错误，不静默。
- [ ] 不破坏现有 `tests/test_rfq_supplier_loop.py`。

#### 必跑测试

```bash
pytest tests/test_rfq_supplier_loop.py tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py
pytest tests/test_supervisor.py tests/test_gen_and_grade.py
cd web && npm run build
```

#### 交付物

- 代码修改
- 新增/更新测试
- 更新 `docs/superpowers/plans/loop-mvp-industrialization-plan.md`
- 新增 summary：`docs/superpowers/summaries/YYYY-MM-DD-HHMM-p0-ai-rfq-loop.md`

---

## Issue 2

### Title

P0-02｜安全授权清零：注册提权、procure 鉴权、RFQ 越权、企业默认全通（B1/B2/B3/B4）

### Assignee

`Fqflmy`

### Body

#### 背景

审计确认以下 P0 安全问题：

- 注册可传 `role:"admin"` 直接获得管理员权限。
- `/procure/*` 全组无鉴权，`user_id` 由客户端自报，会话可枚举/删除。
- RFQ 读接口可横向越权读取他企 RFQ/报价/比价。
- `can_access_company` 默认全通，企业私域经营数据对任意登录用户可见。

#### 目标

清零 P0 授权风险：无 token 拒绝、普通用户不能提权、用户只能访问自己企业或被授权企业的私域数据。

#### 范围

- `api/routers/auth.py`
- `kb/auth.py`
- `api/deps.py`
- `api/routers/procure.py`
- `api/routers/rfqs.py`
- `api/routers/dashboard.py`
- `api/routers/enterprise_context.py`
- `api/routers/chat.py`
- `web/src/stores/procure.ts`
- SSE 请求工具
- 相关 tests

#### 任务清单

- [ ] 服务端注册强制普通用户角色，不接受客户端传入 admin。
- [ ] 明确用户权限角色：`user/member` 与 `admin` 的授予路径分离。
- [ ] `/procure/stream`、`/procure/spec`、`/procure/match` 加 `get_current_user`。
- [ ] procure 会话列表、详情、删除必须按 token 用户归属校验。
- [ ] 前端 SSE 请求带 Authorization，不再依赖 body 中自报 `user_id`。
- [ ] RFQ list/get/quotations/quote-comparison 加企业访问校验。
- [ ] 私域接口默认 deny：dashboard、BOM、订单、缺件、RFQ、报价必须校验企业归属。
- [ ] 保留必要公开知识接口，但与私域经营数据明确分层。
- [ ] 补充 auth/security 测试。

#### 验收标准

- [ ] 带 `role:"admin"` 注册后 `/auth/me` 仍为普通用户。
- [ ] 普通用户访问 admin 接口返回 403。
- [ ] 无 token 调 `/procure/stream` 返回 401。
- [ ] 用户 A 读/删用户 B 的 procure session 返回 403/404。
- [ ] 随机遍历他企 RFQ 详情/报价对比返回 403/404。
- [ ] 新用户访问未授权企业私域数据返回 403。
- [ ] demo 账号兼容策略清晰，演示可用但不绕过私域保护。

#### 必跑测试

```bash
pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py
pytest tests/test_demo_scenario.py
cd web && npm run build
```

建议新增：

```bash
pytest tests/test_auth_authorization_p0.py
```

#### 交付物

- 代码修改
- 安全测试
- 更新 loop plan
- 新增 summary：`docs/superpowers/summaries/YYYY-MM-DD-HHMM-p0-auth-authorization.md`

---

## Issue 3

### Title

P0-03｜CI 最小版 + 测试隔离 + AI 观测与知识状态真实化（G2/A6/G17/A5）

### Assignee

`littleZHL0038`

### Body

#### 背景

审计确认：

- 无 `.github/workflows`，291 个测试无门禁。
- `test_kb_rag` 在无 Key/有 Key 两种环境都不稳定，并可能写真实 dev 库。
- eval 门禁基线与当前值相等，无法拦截劣化。
- AI trace 空转，缺少 agent 明细、token/成本记录，429 无告警。
- 知识库生成失败时仍可能被标 ready。

#### 目标

建立最小工程门禁：PR 能自动跑核心测试和前端 build；离线测试不写 dev 库；AI 观测最小可用；知识生成状态真实。

#### 范围

- `.github/workflows/*`
- `tests/conftest.py`
- `tests/test_kb_rag.py`
- `scripts/eval_agent.py`
- `scripts/eval_*.json`
- `ai/graph.py`
- `ai/monitor.py`
- `kb/pipeline.py`
- `kb/generator.py`
- 相关 docs

#### 任务清单

- [ ] 新增 GitHub Actions 最小 workflow：安装冒烟、pytest 离线子集、web build。
- [ ] 固定 pytest 运行环境，避免写真实 dev DB。
- [ ] 修复 `test_kb_rag.py` 离线可跑，目标无 API Key、无 Docker 也能通过。
- [ ] 为慢/集成/外部依赖测试加 marker 或明确跳过条件。
- [ ] 修复 eval 基线门禁不能拦截劣化的问题。
- [ ] `ai/graph.py` 中确保 agent lifecycle 真正写 trace。
- [ ] `monitor.py` 记录 agent 名称、状态、耗时、错误、token/usage，如可得。
- [ ] 知识生成失败不得标 ready；失败进入 failures/partial 状态。
- [ ] 文档写清本地/CI 如何跑测试。

#### 验收标准

- [ ] 仓库出现 `.github/workflows/ci.yml`。
- [ ] PR/push 可触发 CI。
- [ ] 无 API Key、无 Docker 时离线核心测试可跑。
- [ ] `test_kb_rag.py` 不写真实 dev 库。
- [ ] eval 人为劣化时能失败。
- [ ] trace jsonl 含 agent 明细、耗时、错误；如可得含 token usage。
- [ ] 知识生成失败状态不是 ready。

#### 必跑测试

```bash
pytest tests/test_kb_rag.py tests/test_kb_client.py
pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py tests/test_demo_scenario.py
cd web && npm run build
```

#### 交付物

- CI workflow
- 测试隔离修复
- 观测/状态修复
- 更新 loop plan
- 新增 summary：`docs/superpowers/summaries/YYYY-MM-DD-HHMM-p0-ci-observability.md`

---

## Issue 4

### Title

P0-04｜启动三连修 + mysql_client 按真实 schema 重写（A1/A2/A3/A4）

### Assignee

`ccgt117`

### Body

#### 背景

审计确认：

- 启动文档命令错误：`cd api` + `uvicorn main:app` 与真实 `api.main:main` 不一致。
- 依赖缺失/位置错误会导致干净环境 import 失败。
- `.env.example` 中关键密码为空，照抄后基础服务认证失败。
- `ai/tools/mysql_client.py` 查询不存在列，并可能连错事实源，供应商匹配在真库中会失败。

#### 目标

让新环境 30 分钟内能按文档跑通；让供应商匹配工具按当前真实 schema 查询，MLCC 等核心查询返回非错误结果。

#### 范围

- `环境要求.txt`
- `README.md`
- `.env.example`
- `api/requirements.txt`
- `requirements-dev.txt`
- `ai/tools/mysql_client.py`
- `database/*`
- `data/mysql_schema.sql`
- 相关 tests

#### 任务清单

- [ ] 校准启动命令为根目录执行 `uvicorn api.main:main`。
- [ ] 补齐后端运行依赖，不把运行依赖只放在 dev requirements。
- [ ] `.env.example` 给出本地开发可用示例值，同时避免真实密钥。
- [ ] 写清 Docker/MySQL 启动顺序与健康检查方法。
- [ ] 审计当前真实供应商/产品/替代料数据表来源。
- [ ] 重写 `mysql_client.py` 查询字段，按当前真实 schema 查询。
- [ ] 参数化 SQL 保持不退化。
- [ ] 加真库或可控 fixture 测试，覆盖 `filter_suppliers_raw('MLCC')`。
- [ ] 标注死 schema/死 ORM 不应再作为事实源。

#### 验收标准

- [ ] 干净 venv 按文档启动，`/api/v1/health` 返回 200。
- [ ] `python -c \"import api.main\"` 通过。
- [ ] 本地 `.env.example` 复制后不会因空密码覆盖默认值导致基础服务失败。
- [ ] `filter_suppliers_raw('MLCC')` 在测试库返回非错误结果。
- [ ] 不再查询不存在列，如 `s.category/brand_coverage/moq/data_source` 等死字段。
- [ ] 相关文档与代码事实一致。

#### 必跑测试

```bash
pytest tests/test_tools.py tests/test_match.py
pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py
cd web && npm run build
```

#### 交付物

- 文档修订
- 依赖修订
- mysql_client 修复
- 测试
- 更新 loop plan
- 新增 summary：`docs/superpowers/summaries/YYYY-MM-DD-HHMM-p0-startup-mysql-client.md`

---

## Issue 5

### Title

P0-05｜UI 五连修：RFQ 编辑、demo 空白、危险操作确认、urgent 排序、中文 IME（E1/E2/E3/E5/E6）

### Assignee

`fzy-710`

### Body

#### 背景

审计确认存在 5 个演示路径上容易必现的前端问题：

- RFQ 编辑器字段改动会静默覆盖手工正文，品名硬编码 MLCC。
- demo 模式审核队列/供应商线索列表因 `v-if/v-else` 链 bug 整体消失。
- 删除会话、审核通过/驳回、知识库全量重建缺少确认与失败反馈。
- urgent 优先级排序沉底。
- 三处对话页未处理中文 IME，选词回车会误发送。

#### 目标

修掉演示路径必现 UI 问题，确保用户不会因为前端错误误发询价、看不到闭环页面、误触高危操作或中文输入被打断。

#### 范围

- `web/src/components/procure/RfqEditor.vue`
- `web/src/views/P7AdminAudit.vue`
- `web/src/views/supplier/SupplierLeads.vue`
- `web/src/composables/useDashboard.ts`
- `web/src/views/ChatView.vue`
- `web/src/views/CompanyChat.vue`
- `web/src/views/CompanyAssistant.vue`
- `web/src/components/history/SessionHistoryPanel.vue`
- `web/src/views/AdminKnowledge.vue`
- 相关共享组件，如需新增 ConfirmDialog

#### 任务清单

- [ ] RFQ 编辑器增加 dirty 标记：手工改正文后字段变化不得静默覆盖。
- [ ] RFQ 品名使用实际 `part_name`，不得硬编码 MLCC。
- [ ] 替代料选择应尊重用户勾选，不默认硬取前三个。
- [ ] 修复 P7AdminAudit demo 提示条与列表渲染互斥问题。
- [ ] 修复 SupplierLeads demo 模式列表空白问题。
- [ ] 删除会话、审核通过/驳回、全量重建增加确认与 loading/error 反馈。
- [ ] 驳回审核必须要求备注。
- [ ] `severityRank` 补 `urgent: 5`，urgent 排序在 critical/high 前或按业务约定置顶。
- [ ] 三个对话输入处理 `event.isComposing`，中文输入法选词回车不发送。
- [ ] 如改动涉及页面，做浏览器手工或自动化验收。

#### 验收标准

- [ ] 手改 RFQ 正文后再改字段，不会被静默覆盖；如需重建必须弹确认。
- [ ] 非 MLCC 场景品名正确。
- [ ] demo 账号下审核页和供应商线索页正常渲染。
- [ ] 删除/审核/全量重建均有确认，失败有可见提示。
- [ ] urgent 推荐动作排序置顶。
- [ ] 中文输入法选词 Enter 不发送消息。
- [ ] `npm run build` 通过。

#### 必跑测试

```bash
cd web && npm run build
pytest tests/test_demo_scenario.py tests/test_enterprise_phase2.py
```

建议补充 Playwright smoke：

- demo 登录
- 审核页非空
- 供应商线索页非空
- 中文 IME 不误发送（可做手工验收记录）

#### 交付物

- 前端修复
- 必要的测试或验收记录
- 更新 loop plan
- 新增 summary：`docs/superpowers/summaries/YYYY-MM-DD-HHMM-p0-ui-five-fixes.md`

---

## GitHub 创建命令参考

当前本机 `gh` token 失效，需要先重新登录：

```bash
gh auth login -h github.com
```

登录后可以用 `gh issue create` 手动创建并分配，或让 Codex 继续执行创建。

示例：

```bash
gh issue create \
  --repo LYC-lee/MatchForge \
  --title "P0-01｜打通 AI 寻源到真实 RFQ/线索闭环（C1/D1/D5）" \
  --assignee LYC-lee \
  --body-file issue-body.md
```

