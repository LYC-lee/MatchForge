# MatchForge API 接口测试文档

> 版本：v1.0  
> 生成日期：2026-07-17  
> 基础地址：`http://localhost:8000/api/v1`  
> 适用范围：当前 MatchForge FastAPI 主应用 `api.main:create_app()` 注册的 `/api/v1/*` 接口。

---

## 目录

1. [测试环境准备](#1-测试环境准备)
2. [鉴权与安全测试 Auth](#2-鉴权与安全测试-auth)
3. [企业与上下文 Companies / Enterprise Context](#3-企业与上下文-companies--enterprise-context)
4. [上下游关系与协同问答 Relationships / Partner Chat](#4-上下游关系与协同问答-relationships--partner-chat)
5. [企业知识库问答 Chat / RAG](#5-企业知识库问答-chat--rag)
6. [经营驾驶舱 Dashboard](#6-经营驾驶舱-dashboard)
7. [RFQ 采购闭环](#7-rfq-采购闭环)
8. [供应商线索 Supplier Leads](#8-供应商线索-supplier-leads)
9. [审核队列 Audit](#9-审核队列-audit)
10. [知识库管理 Admin KB](#10-知识库管理-admin-kb)
11. [演示沙盘 Demo Scenario](#11-演示沙盘-demo-scenario)
12. [采购寻源 Procure](#12-采购寻源-procure)
13. [健康检查 Health](#13-健康检查-health)
14. [跨切面与边界测试](#14-跨切面与边界测试)
15. [自动化回归命令](#15-自动化回归命令)
16. [当前已知风险](#16-当前已知风险)

---

## 1. 测试环境准备

### 1.1 启动后端

```bash
uvicorn api.main:main --reload --host 0.0.0.0 --port 8000
```

### 1.2 启动前端

```bash
cd web
npm run dev
```

### 1.3 推荐环境变量

```bash
export BASE=http://localhost:8000/api/v1
export DEMO_TOKEN=kb-demo-user
export ADMIN_TOKEN=kb-admin-demo
```

PowerShell：

```powershell
$env:BASE = "http://localhost:8000/api/v1"
$env:DEMO_TOKEN = "kb-demo-user"
$env:ADMIN_TOKEN = "kb-admin-demo"
```

### 1.4 鉴权说明

多数业务接口需要：

```http
Authorization: Bearer <token>
```

当前项目存在两类 token：

| 类型 | 说明 |
|---|---|
| 登录 token | `/auth/login` 或 `/auth/register` 签发，存储于 `kb_sessions` |
| Demo/Admin token | 当前代码中使用 `KB_DEMO_TOKEN` / `KB_ADMIN_TOKEN`，默认值分别为 `kb-demo-user` / `kb-admin-demo` |

> 安全注意：当前 `kb/auth.py` 仍存在未知 token 兜底放行、静态 demo/admin token、SHA-256 密码哈希、import 自动种子账号等 P0 风险。本文档在第 2 节将其列为必须回归的安全用例。

---

## 2. 鉴权与安全测试 Auth

### 2.1 POST `/auth/login` 登录

请求：

```json
{
  "account": "demo@matchforge.ai",
  "password": "demo12345"
}
```

成功响应：

```json
{
  "token": "session-token",
  "name": "user",
  "role": "user",
  "account": "demo@matchforge.ai"
}
```

测试用例：

| ID | 场景 | 输入 | 预期 |
|---|---|---|---|
| AUTH-001 | 正确账号密码 | `demo@matchforge.ai/demo12345` | 200，返回 token |
| AUTH-002 | 错误密码 | `demo@matchforge.ai/wrong` | 401 |
| AUTH-003 | 不存在账号 | `nobody@test.com/x` | 401 |
| AUTH-004 | 缺少 account | JSON 缺字段 | 422 |
| AUTH-005 | 缺少 password | JSON 缺字段 | 422 |

curl：

```bash
curl -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"account":"demo@matchforge.ai","password":"demo12345"}'
```

### 2.2 POST `/auth/register` 注册

请求：

```json
{
  "name": "张三",
  "account": "zhangsan@example.com",
  "password": "Abc12345",
  "company": "测试制造企业",
  "role": "member"
}
```

成功响应：

```json
{
  "token": "session-token",
  "name": "张三",
  "role": "member",
  "account": "zhangsan@example.com"
}
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| AUTH-006 | 新用户注册 | 200，返回 token |
| AUTH-007 | 重复注册 | 400 |
| AUTH-008 | 缺少 name/account/password/company | 422 |
| AUTH-009 | role 传 `buyer/supplier` | 当前兼容；后续应改为 `member/enterprise_admin/platform_admin` |

### 2.3 GET `/auth/me` 当前用户

成功：

```bash
curl "$BASE/auth/me" -H "Authorization: Bearer $DEMO_TOKEN"
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| AUTH-010 | 有效登录 token | 200，返回 user |
| AUTH-011 | 无 Authorization | 401 |
| AUTH-012 | Authorization 非 Bearer | 401 |
| AUTH-013 | 随机未知 token | **安全期望：401** |
| AUTH-014 | demo token | 本地演示可 200；生产模式应拒绝 |
| AUTH-015 | admin token | 本地演示可 200/admin；生产模式应由安全配置控制 |

> 当前代码风险：`resolve_token()` 对未知 token 兜底返回 user。AUTH-013 当前可能失败，必须作为 P0 安全修复验收。

### 2.4 P0 安全回归测试

| ID | 风险 | 测试方式 | 安全期望 |
|---|---|---|---|
| SEC-001 | 任意 token 放行 | `Bearer totally-random` 调 `/auth/me` | 401 |
| SEC-002 | 硬编码 admin token | 未配置环境变量时用 `kb-admin-demo` 调 admin 接口 | 401/403 |
| SEC-003 | demo-token 字面量 | `Bearer demo-token` 调 `/auth/me` | 生产拒绝；本地需显式开启 |
| SEC-004 | SHA-256 密码 | 注册后检查 `kb_users.password_hash` | 应为 bcrypt/argon2 |
| SEC-005 | import 自动落库 | `python -c "import kb.auth"` | 不应创建 demo/admin 用户 |
| SEC-006 | 普通用户访问 admin | demo user 调 `/admin/audit-queue` | 403 |
| SEC-007 | 无 token 访问受保护接口 | `/companies/9003/dashboard` | 401 |

---

## 3. 企业与上下文 Companies / Enterprise Context

### 3.1 GET `/companies`

查询公司列表。

```bash
curl "$BASE/companies" -H "Authorization: Bearer $DEMO_TOKEN"
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| COM-001 | 查询公司列表 | 200，返回 `items` |
| COM-002 | 按 segment 过滤 | 200，返回符合条件数据 |
| COM-003 | 无 token | 401 |

### 3.2 GET `/companies/segments`

查询产业分段。

| ID | 场景 | 预期 |
|---|---|---|
| COM-004 | 查询分段 | 200 |

### 3.3 GET `/companies/{company_id}`

查询公司详情。

| ID | 场景 | 预期 |
|---|---|---|
| COM-005 | `9003` 鼎云整机 | 200 |
| COM-006 | 不存在公司 | 404 |
| COM-007 | 非数字 company_id | 422 |

### 3.4 GET `/companies/{company_id}/knowledge`

查询公司知识条目。

| ID | 场景 | 预期 |
|---|---|---|
| COM-008 | 有权限访问公司知识 | 200 |
| COM-009 | 无 token | 401 |
| COM-010 | 企业隔离白名单场景 | 未授权公司应 403 |

### 3.5 GET `/companies/{company_id}/products`

查询公司产品，返回知识库产品和生产产品。

| ID | 场景 | 预期 |
|---|---|---|
| COM-011 | 6 家演示企业产品非空 | 200，生产产品 `production_products` 非空 |
| COM-012 | 不存在公司 | 404 或空结果，按接口实现 |

### 3.6 Enterprise Context

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/enterprise-context/companies` | 企业上下文列表 |
| GET | `/enterprise-context/{company_id}` | 单企业上下文 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| CTX-001 | 查询上下文列表 | 200，包含 9001-9006 |
| CTX-002 | 查询 9003 | 200，含 profile/segment/chain_position |
| CTX-003 | 不存在企业 | 404 |

---

## 4. 上下游关系与协同问答 Relationships / Partner Chat

### 4.1 关系查询

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/companies/{company_id}/relationships` | 全部直接关系 |
| GET | `/companies/{company_id}/upstream` | 上游 |
| GET | `/companies/{company_id}/downstream` | 下游 |
| GET | `/companies/{company_id}/chat-partners` | 可协同问答伙伴 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| REL-001 | 9003 查询上游 | 200，包含 9002 |
| REL-002 | 9003 查询下游 | 200，包含 9005 |
| REL-003 | 9004 查询下游 | 200，物流服务下游非空 |
| REL-004 | 不存在企业 | 404 |

### 4.2 POST `/companies/{company_id}/partner-chat`

请求：

```json
{
  "partner_company_id": 9002,
  "query": "主板交期多久？",
  "scope": "product"
}
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| PCHAT-001 | 9003 与 9002 有直接关系 | 200，返回 answer/sources |
| PCHAT-002 | scope=business | 200 |
| PCHAT-003 | 无直接关系，如 9003->9001 | 403 |
| PCHAT-004 | partner 不存在 | 404 |
| PCHAT-005 | 无 token | 401 |

---

## 5. 企业知识库问答 Chat / RAG

### 5.1 POST `/chat/ask`

请求：

```json
{
  "company_id": 9003,
  "query": "当前有哪些关键缺件？",
  "language": "zh"
}
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| CHAT-001 | 企业内部问答 | 200，返回 answer |
| CHAT-002 | 无 token | 401 |
| CHAT-003 | 查询不存在企业 | 404 或受控错误 |
| CHAT-004 | 跨企业知识隔离 | 不应返回非授权企业知识 |

### 5.2 POST `/chat/compare`

请求：

```json
{
  "company_ids": [9001, 9002],
  "query": "比较两家企业的产品能力",
  "language": "zh"
}
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| CHAT-005 | 2-6 家公司对比 | 200 |
| CHAT-006 | 少于 2 家 | 422 |
| CHAT-007 | 超过限制 | 422 或受控错误 |

### 5.3 GET `/chat/trace/{request_id}`

| ID | 场景 | 预期 |
|---|---|---|
| CHAT-008 | 不存在 trace | 404 |
| CHAT-009 | 存在 trace | 200 |

---

## 6. 经营驾驶舱 Dashboard

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/companies/{company_id}/dashboard` | 聚合驾驶舱 |
| GET | `/companies/{company_id}/orders` | 订单 |
| GET | `/companies/{company_id}/forecasts` | 预测 |
| GET | `/companies/{company_id}/shortages` | 缺件 |
| POST | `/companies/{company_id}/shortages/recalculate` | 重算缺件 |
| GET | `/companies/{company_id}/recommended-actions` | 推荐动作 |
| GET | `/companies/{company_id}/bom-summary` | BOM 汇总 |
| GET | `/products/{product_id}/bom` | 产品 BOM |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| DASH-001 | 9003 dashboard | 200，含 company/products/orders/shortages |
| DASH-002 | 9001-9006 dashboard | 200，均有产品与订单/预测 |
| DASH-003 | 9004 物流服务 | 200，体现服务资源/履约风险 |
| DASH-004 | 重算缺件 | 200，返回 items |
| DASH-005 | 产品 BOM | 200，返回 BOM items |
| DASH-006 | 跨企业 BOM 越权 | 403 |
| DASH-007 | 不存在公司 | 404 |
| DASH-008 | 无 token | 401 |

---

## 7. RFQ 采购闭环

### 7.1 POST `/rfqs` 创建 RFQ

请求：

```json
{
  "buyer_company_id": 9003,
  "title": "DDR5 内存采购",
  "part_number": "DDR5-16GB",
  "part_name": "DDR5 16GB 内存条",
  "quantity": 1000,
  "unit": "条",
  "target_price": 120.0,
  "lead_time_days": 14,
  "accept_alternatives": true,
  "scenario": "shortage",
  "supplier_candidates": [9002]
}
```

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| RFQ-001 | 创建 RFQ | 200，返回 draft |
| RFQ-002 | 创建时带 Phase2 兼容字段 | 200 |
| RFQ-003 | buyer_company_id 不存在 | 404 |
| RFQ-004 | 无关企业越权 | 403 |

### 7.2 RFQ 查询与发送

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/rfqs` | RFQ 列表 |
| GET | `/rfqs/{rfq_id}` | RFQ 详情 |
| POST | `/rfqs/{rfq_id}/send` | 发送 RFQ |
| GET | `/companies/{company_id}/rfqs` | 企业 RFQ |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| RFQ-005 | 列表过滤 buyer/status | 200 |
| RFQ-006 | 详情存在 | 200 |
| RFQ-007 | 详情不存在 | 404 |
| RFQ-008 | 发送 RFQ | 200，生成 supplier leads 和 audit item |

### 7.3 报价

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/rfqs/{rfq_id}/quotations` | 提交报价 |
| GET | `/rfqs/{rfq_id}/quotations` | 报价列表 |
| GET | `/rfqs/{rfq_id}/quote-comparison` | 报价对比 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| RFQ-009 | 有线索供应商提交报价 | 200 |
| RFQ-010 | 无线索供应商报价 | 403 |
| RFQ-011 | 异常高价报价 | 200，并产生 audit anomaly |
| RFQ-012 | 报价对比排序 | 200，含 rank/is_lowest |

---

## 8. 供应商线索 Supplier Leads

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/suppliers/{company_id}/leads` | 供应商线索 |
| POST | `/supplier-leads/{lead_id}/view` | 标记查看 |
| POST | `/supplier-leads/{lead_id}/decline` | 拒绝线索 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| LEAD-001 | 按供应商查询线索 | 200 |
| LEAD-002 | 按 status 过滤 | 200 |
| LEAD-003 | view pending lead | 200，状态 viewed |
| LEAD-004 | decline lead | 200，状态 declined |
| LEAD-005 | 已 quoted 线索拒绝 | 400 |
| LEAD-006 | 无关企业访问 | 403 |

---

## 9. 审核队列 Audit

> 需要 admin 权限。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/audit-queue` | 审核队列 |
| POST | `/admin/audit-queue/{item_id}/approve` | 通过 |
| POST | `/admin/audit-queue/{item_id}/reject` | 驳回 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| AUD-001 | admin 查询 pending | 200 |
| AUD-002 | 普通用户查询 | 403 |
| AUD-003 | 无 token 查询 | 401 |
| AUD-004 | approve 存在项 | 200 |
| AUD-005 | reject 存在项 | 200 |
| AUD-006 | 操作不存在项 | 404 |

---

## 10. 知识库管理 Admin KB

> 需要 admin 权限。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/admin/kb/generate` | 生成知识库 |
| POST | `/admin/kb/incremental/{company_id}` | 单公司增量 |
| POST | `/admin/kb/rebuild-index` | 重建向量索引 |
| GET | `/admin/kb/tasks` | 任务列表 |
| GET | `/admin/kb/tasks/{task_id}` | 任务详情 |
| GET | `/admin/kb/tasks/{task_id}/failures` | 失败明细 |
| POST | `/admin/kb/tasks/{task_id}/cancel` | 取消任务 |
| GET | `/admin/kb/stats` | 统计 |
| GET | `/admin/kb/capabilities` | 能力说明 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| KB-001 | admin capabilities | 200 |
| KB-002 | admin stats | 200 |
| KB-003 | 普通用户访问 | 403 |
| KB-004 | 无 token 访问 | 401 |
| KB-005 | incremental 不存在 company | 404 或受控错误 |
| KB-006 | rebuild-index | 200 |

---

## 11. 演示沙盘 Demo Scenario

### 11.1 查询接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/demo/scenarios` | 场景列表 |
| GET | `/demo/state?company_id=9003` | 当前公司沙盘状态 |
| GET | `/demo/events?company_id=9003` | 事件日志 |
| GET | `/demo/rfqs?company_id=9003` | Demo RFQ |
| GET | `/demo/rfqs/{rfq_id}/quote-comparison?company_id=9003` | Demo 报价对比 |
| GET | `/demo/supplier-view?company_id=9002` | 供应商视角 |
| GET | `/demo/audit-queue` | Demo 审核队列 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| DEMO-001 | 查询默认场景 | 200 |
| DEMO-002 | 查询 9001-9006 state | 200，均有基线数据 |
| DEMO-003 | 查询不存在公司 state | 404 |
| DEMO-004 | 无 token | 401 |

### 11.2 动作接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/demo/scenarios/reset` | 重置场景 |
| POST | `/demo/actions/generate-orders` | 生成订单 |
| POST | `/demo/actions/consume-inventory` | 消耗库存 |
| POST | `/demo/actions/recalculate-shortages` | 重算缺件 |
| POST | `/demo/actions/generate-rfq` | 生成 RFQ |
| POST | `/demo/actions/simulate-quotes` | 模拟报价 |
| POST | `/demo/actions/execute-replenishment` | 执行补货 |
| POST | `/demo/actions/select-alternative` | 选择替代料 |

通用请求字段：

```json
{
  "company_id": 9003,
  "scenario_id": "default_mvp_demo"
}
```

完整链路测试：

| ID | 场景 | 步骤 | 预期 |
|---|---|---|---|
| DEMO-005 | 订单生成 | reset -> generate-orders -> state | demo_orders 增加 |
| DEMO-006 | 缺件重算 | generate-orders -> recalculate-shortages | shortage 增加或变化 |
| DEMO-007 | 直接供应商 RFQ | 9003 PCBA 缺件 -> generate-rfq | 有候选供应商 |
| DEMO-008 | 无直接供应商 | 9001/9006 原材料缺件 -> generate-rfq | `no_direct_supplier=true` |
| DEMO-009 | 模拟报价 | generate-rfq -> simulate-quotes | 生成报价，幂等 |
| DEMO-010 | 执行补货 | simulate-quotes -> execute-replenishment | 库存增加、缺件下降 |
| DEMO-011 | 供应商视角 | 买方生成 RFQ -> 供应商 view | 供应商可见相关 RFQ |
| DEMO-012 | 审核队列 | no_direct_supplier 或异常报价 | audit queue 非空 |
| DEMO-013 | reset | 完整链路后 reset | demo 数据恢复基线 |
| DEMO-014 | 基线不污染 | 操作 demo 后查业务表 | 无 `DEMO-ORD` 写入基线表 |

示例：

```bash
curl -X POST "$BASE/demo/actions/generate-orders" \
  -H "Authorization: Bearer $DEMO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company_id":9003,"quantity":100,"priority":"urgent"}'
```

---

## 12. 采购寻源 Procure

> 当前 `procure` 路由在 `langgraph` 缺失时会优雅降级不注册；若已注册，可测试以下接口。当前路由未强制使用 `get_current_user`，生产前应补鉴权。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/procure/health` | 健康检查 |
| POST | `/procure/stream` | SSE 流式寻源 |
| POST | `/procure/spec` | 规格解析 |
| POST | `/procure/match` | 替代料/供应商匹配 |
| GET | `/procure/sessions` | 会话列表 |
| GET | `/procure/sessions/{thread_id}` | 会话详情 |
| DELETE | `/procure/sessions/{thread_id}` | 删除会话 |

测试用例：

| ID | 场景 | 预期 |
|---|---|---|
| PROC-001 | health | 200 |
| PROC-002 | stream 正常输入 | SSE start/progress/result/end |
| PROC-003 | 空 raw_query | 受控错误或空结果 |
| PROC-004 | spec 解析 | 200，返回 parsed/normalized |
| PROC-005 | match | 200，返回 alternatives/suppliers |
| PROC-006 | sessions 不存在 | 404 |
| PROC-007 | 鉴权缺失风险 | 当前可能无需 token；生产应要求鉴权 |

---

## 13. 健康检查 Health

### GET `/health`

```bash
curl "$BASE/health"
```

预期：

```json
{
  "status": "ok"
}
```

---

## 14. 跨切面与边界测试

| ID | 场景 | 预期 |
|---|---|---|
| X-001 | CORS 允许 `http://localhost:5173` | 预检通过 |
| X-002 | 未注册路由 | 404 |
| X-003 | 请求体缺字段 | 422 |
| X-004 | company_id 非数字 | 422 |
| X-005 | company_id 不存在 | 404 |
| X-006 | 无 token 调受保护接口 | 401 |
| X-007 | 普通用户调 admin | 403 |
| X-008 | 6 家演示公司数据完整性 | dashboard/BOM/订单/预测均非空 |
| X-009 | reset 不污染基线表 | 基线订单/RFQ/库存不出现 demo 记录 |
| X-010 | 前端 build | `npm run build` 通过 |

---

## 15. 自动化回归命令

### 15.1 核心业务回归

```bash
pytest tests/test_enterprise_phase1.py \
       tests/test_enterprise_phase2.py \
       tests/test_rfq_supplier_loop.py \
       tests/test_demo_scenario.py
```

### 15.2 注册身份模型

```bash
pytest tests/test_register_identity.py
```

### 15.3 RAG / 知识库

```bash
pytest tests/test_kb_rag.py tests/test_kb_client.py
```

### 15.4 前端构建

```bash
cd web
npm run build
```

### 15.5 建议新增的安全测试

建议新增：

```bash
pytest tests/test_auth_security.py
```

覆盖：

- 未知 token 拒绝
- demo/admin token 配置化
- 生产模式拒绝 demo token
- bcrypt/argon2 密码
- import 不自动落库
- admin 接口权限

---

## 16. 当前已知风险

| 优先级 | 风险 | 说明 |
|---|---|---|
| P0 | 任意 token 可能被放行 | `kb/auth.py::resolve_token` 当前未知 token 兜底返回 user |
| P0 | 静态 admin/demo token | `KB_ADMIN_TOKEN` / `KB_DEMO_TOKEN` 有默认值，且兼容 `demo-token` |
| P0 | 密码哈希弱 | 当前 `_hash_password` 为单轮 SHA-256 |
| P0 | import 自动种子账号 | `kb.auth` import 时会调用 `_ensure_seed_users()` |
| P1 | 注册身份模型不合理 | 注册仍有 `role=buyer/supplier` 遗留语义 |
| P1 | procure 鉴权待确认 | `procure` 路由当前未强制 `get_current_user` |
| P1 | 浏览器端验收不足 | 多数验收依赖 pytest/TestClient，仍需 6 公司浏览器回归 |
| P2 | 旧 `api/routes/*` 与新 `api/routers/*` 并存 | 容易产生死代码/接口文档混淆 |

---

## 附录：建议的手工验收路径

1. 登录页选择 9003 鼎云演示账号。
2. 进入经营驾驶舱，确认订单、产品、缺件、关系非空。
3. 点击悬浮控制台“生成新订单”，确认订单数增加。
4. 点击“重新计算缺件”，确认缺件变化。
5. 进入缺件与采购，生成 RFQ。
6. 模拟报价。
7. 执行补货。
8. 切换/重新登录 9002 创捷，确认供应商工作台看到 RFQ。
9. 登录 9004 远达，确认展示物流/服务资源，而非硬套制造逻辑。
10. 打开审核页，确认 no_direct_supplier/异常项可见。
11. reset 场景，确认 demo 数据恢复基线。
