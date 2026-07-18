# MatchForge 接口测试清单

> 基线: main `52d3a42`（含 P0 auth 安全修复 loop-007）。所有接口前缀 `/api/v1`，鉴权头 `Authorization: Bearer <token>`。
> 鉴权标记: 🔓 无需认证 | 🔑 需登录 (get_current_user) | 🛡️ 需 admin (require_admin) | 🏢 需企业访问 (check_company_access，命中白名单时强制隔离，默认 B2B 公开)。

## 0. 测试前置

- [ ] 后端启动: `uvicorn api.main:main`，`GET /api/v1/health` -> 200 `{"status":"ok"}`
- [ ] MySQL 容器 healthy；种子已写入（6 家企业 9001-9006 + Phase2 + RFQ 闭环 + demo 场景）
- [ ] 本地 demo 模式: `.env` 设 `KB_DEMO_MODE=true`、`KB_DEMO_TOKEN=kb-demo-user`、`KB_ADMIN_TOKEN=kb-admin-demo`、`APP_ENV=development`
- [ ] 显式种子账号（可选）: `DEMO_USER_PASSWORD=... DEMO_ADMIN_PASSWORD=... python scripts/seed_auth_users.py`
- [ ] 准备 4 类 token: 未知随机 token / demo 用户 token (kb-demo-user) / admin demo token (kb-admin-demo) / 真实登录 token

---

## 1. 认证与安全（P0 重点，必须全过）

### 1.1 登录 / 注册 / 当前用户
- [ ] 🔓 `POST /auth/login` 正确密码 -> 200，返回 token；错误密码 -> 401
- [ ] 🔓 `POST /auth/login` 不存在账号 -> 401
- [ ] 🔓 `POST /auth/register` 新邮箱 -> 200，返回 token；已注册邮箱 -> 400
- [ ] 🔓 `POST /auth/register` 密码 <8 位 / 无字母数字 -> 前端拦截（后端不强制，记录差异）
- [ ] 🔑 `GET /auth/me` 带真实 token -> 200，返回 user_id/name/role/account
- [ ] 🔑 `GET /auth/me` 不带 token -> 401
- [ ] 🔑 `GET /auth/me` 带未知随机 token -> **401**（P0-1: 不得兜底放行）

### 1.2 Demo 登录（受控）
- [ ] 🔓 `POST /auth/demo-login` body `{company_id:9003}` + demo 模式开 -> 200，返回 token + `is_demo:true` + company_name
- [ ] 用上一步 token 调 `GET /auth/me` -> 200（真实会话，非字面量 demo-token）
- [ ] 🔓 `POST /auth/demo-login` 不存在 company_id (999999) -> 404
- [ ] 🔓 `POST /auth/demo-login` demo 模式关 (`KB_DEMO_MODE=false`) -> 404
- [ ] 🔓 `POST /auth/demo-login` 生产模式 (`APP_ENV=production`) -> 404

### 1.3 Token 拒绝策略（P0-1 核心）
- [ ] 未知随机 Bearer token 调任意 🔑 接口（如 `/auth/me`、`/companies`）-> **401**
- [ ] `Bearer kb-admin-demo` 在未配 `KB_ADMIN_TOKEN` 时 -> **401**（P0-2: 不再有效）
- [ ] `Bearer kb-admin-demo` 在生产模式 -> 401
- [ ] `Bearer kb-demo-user` 在生产模式 -> 401
- [ ] `Bearer demo-token`（旧字面量）-> 401（已移除）
- [ ] 畸形头 `Authorization: demo-token`（无 Bearer 前缀）-> 401
- [ ] 空 token `Authorization: Bearer ` -> 401

### 1.4 密码哈希（P0-3）
- [ ] 注册用户 `kb_users.password_hash` 以 `$2` 开头（bcrypt），`salt` 为空
- [ ] 旧 sha256 用户（手动构造）首次登录成功后，`password_hash` 升级为 `$2`、`salt` 清空
- [ ] 错误密码登录 -> 401，哈希不变
- [ ] `import kb.auth` 不创建 demo/admin 用户（无 import 期写库）—— 查 `kb_users` 无 `demo@matchforge.ai`/`admin@matchforge.ai` 自动产生

### 1.5 Admin 鉴权（🛡️）
- [ ] 🛡️ `GET /admin/audit-queue` 用 admin demo token -> 200
- [ ] 🛡️ `GET /admin/audit-queue` 用 demo 用户 token (role=user) -> **403**
- [ ] 🛡️ `GET /admin/audit-queue` 无 token -> 401
- [ ] 🛡️ `GET /admin/kb/stats` 用 demo 用户 token -> 403
- [ ] 🛡️ `GET /admin/kb/capabilities` 用 admin token -> 200

---

## 2. 企业与上下文

- [ ] 🔑 `GET /companies` -> 200，含 items；支持 segment 过滤
- [ ] 🔑 `GET /companies/segments` -> 200
- [ ] 🔑 `GET /companies/{9003}` -> 200，公司详情
- [ ] 🔑 `GET /companies/{999999}` -> 404
- [ ] 🏢 `GET /companies/{id}/knowledge` 默认用户（无白名单）-> 200
- [ ] 🏢 `GET /companies/{id}/knowledge` 白名单用户访问未授权公司 -> 403
- [ ] 🏢 `GET /companies/{id}/products` -> 200，含 items + production_products
- [ ] 🔑 `GET /enterprise-context/companies` -> 200
- [ ] 🔑 `GET /enterprise-context/{9003}` -> 200

---

## 3. 上下游关系与协同问答

- [ ] 🏢 `GET /companies/{9003}/relationships` -> 200
- [ ] 🏢 `GET /companies/{9003}/upstream` -> 200，含创捷(9002)
- [ ] 🏢 `GET /companies/{9003}/downstream` -> 200，含星河(9005)
- [ ] 🏢 `GET /companies/{9003}/chat-partners` -> 200
- [ ] 🏢 `POST /companies/{9003}/partner-chat` body `{partner_company_id:9002, query:"...", scope:"product"}` 有关系 -> 200
- [ ] 🏢 `POST /companies/{9003}/partner-chat` 无关系伙伴 -> 403
- [ ] 🏢 `POST /companies/{999999}/partner-chat` -> 404
- [ ] 🔑 `POST /chat/ask` body `{company_id:9003, query:"村田MLCC价格"}` -> 200，含 intent/answer
- [ ] 🔑 `POST /chat/ask` 无 token -> 401；未授权 company_id -> 403
- [ ] 🔑 `POST /chat/compare` 多公司 -> 200；含未授权公司 -> 403
- [ ] 🔑 `GET /chat/trace/{不存在id}` -> 404（证明路由注册）

---

## 4. 经营驾驶舱（Phase2）

- [ ] 🏢 `GET /companies/{9003}/dashboard` -> 200，含 products/orders/forecast/shortages/recommended_actions/upstream/downstream
- [ ] 🏢 `GET /companies/{9003}/orders` -> 200
- [ ] 🏢 `GET /companies/{9003}/forecasts` -> 200
- [ ] 🏢 `GET /companies/{9003}/shortages` -> 200，缺件含 shortage_qty/severity
- [ ] 🏢 `POST /companies/{9003}/shortages/recalculate` -> 200
- [ ] 🏢 `GET /companies/{9003}/recommended-actions` -> 200
- [ ] 🏢 `GET /companies/{9003}/bom-summary` -> 200
- [ ] 🏢 `GET /products/{9101}/bom?company_id=9003` -> 200，含 items/critical_count
- [ ] 🏢 `GET /products/{9101}/bom` 越权（不属于该企业）-> 403
- [ ] 🏢 `GET /companies/{999999}/dashboard` -> 404

---

## 5. RFQ 采购闭环

### 5.1 RFQ
- [ ] 🔑 `POST /rfqs` body 含 buyer_company_id=9003 + supplier_candidates=[9002] -> 200，返回 rfq_id
- [ ] 🔑 `POST /rfqs` 未授权 buyer_company_id -> 403
- [ ] 🔑 `GET /rfqs?buyer_company_id=9003` -> 200
- [ ] 🔑 `GET /rfqs/{id}` -> 200；不存在 -> 404
- [ ] 🔑 `POST /rfqs/{id}/send` -> 200，生成供应商线索 + 审核项
- [ ] 🔑 `GET /companies/{9003}/rfqs` -> 200

### 5.2 报价
- [ ] 🔑 `POST /rfqs/{id}/quotations` body 含 supplier_company_id -> 200；未授权供应商 -> 403
- [ ] 🔑 `GET /rfqs/{id}/quotations` -> 200
- [ ] 🔑 `GET /rfqs/{id}/quote-comparison` -> 200，含 rank/is_lowest/meets_target

### 5.3 供应商线索
- [ ] 🏢 `GET /suppliers/{9002}/leads` -> 200；可按 status 过滤
- [ ] 🏢 `GET /suppliers/{9002}/leads` 白名单用户访问其他供应商 -> 403
- [ ] 🔑 `POST /supplier-leads/{id}/view` -> 200，更新 viewed_at
- [ ] 🔑 `POST /supplier-leads/{id}/decline` body `{note}` -> 200

### 5.4 审核闭环（🛡️ admin）
- [ ] 🛡️ `GET /admin/audit-queue?status=pending` -> 200
- [ ] 🛡️ `POST /admin/audit-queue/{id}/approve` body `{note}` -> 200，status=approved
- [ ] 🛡️ `POST /admin/audit-queue/{id}/reject` -> 200，status=rejected
- [ ] 🛡️ `POST /admin/audit-queue/{999999}/approve` -> 404
- [ ] 🛡️ 上述用 demo 用户 token -> 403

---

## 6. 演示场景沙盘（demo）

> 主视角鼎云 9003；所有 action 仅写 demo_* 表，不污染基线。

- [ ] 🔑 `GET /demo/scenarios` -> 200
- [ ] 🔑 `GET /demo/state?scenario_id=default_mvp_demo` -> 200
- [ ] 🔑 `GET /demo/events` -> 200
- [ ] 🔑 `GET /demo/rfqs` -> 200
- [ ] 🔑 `GET /demo/rfqs/{id}/quote-comparison` -> 200
- [ ] 🔑 `GET /demo/supplier-view?company_id=9002` -> 200
- [ ] 🔑 `GET /demo/audit-queue` -> 200（demo 派生，只读）
- [ ] 🔑 `POST /demo/scenarios/reset` -> 200，演示数据清零、基线不变
- [ ] 🔑 `POST /demo/actions/generate-orders` -> 200，联动上下游/支撑事件
- [ ] 🔑 `POST /demo/actions/consume-inventory` -> 200，写 demo override
- [ ] 🔑 `POST /demo/actions/recalculate-shortages` -> 200，缺口=基线需求+demo订单-demo库存
- [ ] 🔑 `POST /demo/actions/generate-rfq` -> 200，候选仅直接关系
- [ ] 🔑 `POST /demo/actions/generate-rfq` 无直接供应商场景 -> 提示 no_direct_supplier
- [ ] 🔑 `POST /demo/actions/simulate-quotes` -> 200，合理价格/交期；幂等（重复调用不重复生成）
- [ ] 🔑 `POST /demo/actions/execute-replenishment` -> 200，补货入库 + 关闭 RFQ
- [ ] 🔑 `POST /demo/actions/select-alternative` -> 200，仅直接关系替代料
- [ ] 🔑 action 传非主视角企业 -> 400
- [ ] reset 后再查 demo state -> 恢复基线；查基线业务表（如 kb_shortages）-> 未被污染

---

## 7. 寻源流式（procure，SSE）

> ⚠️ procure 路由当前**无鉴权依赖**（get_current_user 未挂载）—— 记录为待确认安全项。

- [ ] 🔓 `GET /procure/health` -> 200
- [ ] 🔓 `POST /procure/stream` body `{query:"TMK212BJ105KG-T 缺货"}` -> 200，SSE 流式输出多 agent 进度
- [ ] 🔓 `POST /procure/spec` -> 200，解析规格
- [ ] 🔓 `POST /procure/match` -> 200，匹配供应商
- [ ] 🔓 `GET /procure/sessions` -> 200
- [ ] 🔓 `GET /procure/sessions/{thread_id}` -> 200；不存在 -> 404
- [ ] 🔓 `DELETE /procure/sessions/{thread_id}` -> 200
- [ ] 【安全待办】确认 procure 是否应加 🔑 鉴权；当前任意访问

---

## 8. KB 管理（🛡️ admin）

- [ ] 🛡️ `GET /admin/kb/capabilities` -> 200
- [ ] 🛡️ `GET /admin/kb/stats` -> 200
- [ ] 🛡️ `GET /admin/kb/tasks` -> 200
- [ ] 🛡️ `GET /admin/kb/tasks/{id}` -> 200；不存在 -> 404
- [ ] 🛡️ `GET /admin/kb/tasks/{id}/failures` -> 200
- [ ] 🛡️ `POST /admin/kb/generate` -> 200/202，启动生成任务
- [ ] 🛡️ `POST /admin/kb/incremental/{company_id}` -> 200
- [ ] 🛡️ `POST /admin/kb/rebuild-index` -> 200
- [ ] 🛡️ `POST /admin/kb/tasks/{id}/cancel` -> 200
- [ ] 🛡️ 上述用 demo 用户 token -> 403；无 token -> 401

---

## 9. 跨切面 / 边界

- [ ] CORS: 来自 `http://localhost:5173` 的预检 OPTIONS 通过；非允许源被拒
- [ ] 路由未注册路径 -> 404
- [ ] 请求体字段缺失/类型错误 -> 422
- [ ] company_id 为负数/非整数 -> 422 或 404
- [ ] demo 用户 token 与真实 token 行为一致（除 admin 接口 403）
- [ ] token 复用：同一 token 多次请求均通过；注销/过期后失效（当前无 logout/过期接口，记录）
- [ ] 企业隔离: 白名单用户 A 只能访问授权公司，访问其他 -> 403；非白名单用户默认全公开

---

## 10. 已知待办 / 风险项（非阻断，记录）

- `procure/*` 无鉴权（§7）—— 建议补 `get_current_user`。
- `POST /auth/login` 返回固定 `name/role="user"`（非真实用户信息）—— 前端显示不准，后端鉴权以会话 role 为准。
- `api/auth.py`（JWT/bcrypt）/`api/dependencies.py`/`api/routes/auth.py` 为死代码（未注册），建议清理或统一。
- 无 token 过期 / refresh / logout 接口（会话 token 长期有效）。
- 浏览器端到端验收（demo 登录 / admin 登录审核页 / 生产模式 demo 拒绝）尚未做。

---

## 附: 快速回归命令

```bash
# 后端核心安全 + 业务回归
python -m pytest tests/test_auth_security.py tests/test_enterprise_phase1.py \
  tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py \
  tests/test_demo_scenario.py tests/test_register_identity.py -q

# 前端构建
cd web && npm run build
```
