# 演示场景集成总结 (demo-scenario-integration)

**生成时间**: 2026-07-16 17:36
**集成 AI**: Claude Code (glm-5-2-260617)

---

## 1. 集成分支名

`codex/demo-scenario-integration`

worktree: `D:\Project\project mvp\MatchForge-demo-scenario-integration`

## 2. 合并的来源分支和 commit

| 来源分支 | commit | 说明 |
|---|---|---|
| `codex/demo-scenario-backend` | d654778 | 演示场景沙盘后端 (scenario engine + demo router + migration + tests + docs) |
| `codex/demo-scenario-frontend` | 68e2437 | 演示登录 + 悬浮控制台 + 场景 API 接入 |

两分支均以 `main` f9c9508 为 merge-base, 文件无重叠, 合并无冲突。

## 3. 最终 commit hash

| commit | 类型 | 说明 |
|---|---|---|
| c46218b | merge | integrate demo-scenario-backend (scenario engine + demo router + migration + tests) |
| 4e36ea9 | merge | integrate demo-scenario-frontend (floating console + demo login + scenario API wiring) |
| (本次) | fix+docs | demo-token 显式兼容 + 集成计划 + 本总结 |

> 最终 commit hash 在提交后由 git 生成, 见 `git log -1`。

## 4. 冲突文件清单

**无 git 冲突**。两分支文件集互斥:
- 后端分支仅修改: `api/main.py`, `api/routers/demo.py`, `database/migrations/05_demo_scenario.sql`, `kb/demo_calc.py`, `kb/models.py`, `scripts/seed_demo_scenario.py`, `tests/test_demo_scenario.py`, docs
- 前端分支仅修改: `web/src/**`, docs

## 5. 冲突解决策略

无冲突需解决。但发现一处**逻辑级集成缺口**并修复:

| 缺口 | 策略 |
|---|---|
| 前端 `auth.ts` 用字面量 `'demo-token'`, 后端 `KB_DEMO_TOKEN` 默认 `'kb-demo-user'` | 优先保留前端真实接口调用与悬浮控制台 (合并策略 #2), 在后端 `kb/auth.py:resolve_token` 显式接受 `'demo-token'`, 与 `'kb-demo-user'` 映射同一 demo-user。非破坏式, 不影响 JWT/MySQL 真实登录, 不删接口。 |

## 6. 修改文件清单 (集成层修复 + 新增文档)

| 文件 | 类型 | 改动 |
|---|---|---|
| `kb/auth.py` | 修改 | `resolve_token` 增加 `or token == "demo-token"` 分支, 显式兼容前端演示 token |
| `docs/superpowers/plans/2026-07-16-demo-scenario-integration-plan.md` | 新增 | 集成计划 |
| `docs/superpowers/summaries/2026-07-16-1736-demo-scenario-integration-summary.md` | 新增 | 本总结 |

(合并带入的 27 个业务文件见各来源分支总结, 此处只列集成层改动。)

## 7. 接口清单 (demo scenario router, 挂 /api/v1)

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /demo/scenarios | 场景列表 |
| GET | /demo/state?company_id= | 当前企业演示状态 (基线 + 演示增量) |
| GET | /demo/events?company_id=&phase= | 事件日志 (因果链) |
| GET | /demo/rfqs?company_id=&status= | 演示 RFQ 列表 |
| GET | /demo/rfqs/{rfq_id}/quote-comparison?company_id= | 报价对比 |
| POST | /demo/scenarios/reset | 重置场景 (仅清 demo_* 表) |
| POST | /demo/actions/generate-orders | 生成演示订单 (+联动上下游/支撑) |
| POST | /demo/actions/consume-inventory | 消耗库存 (写 demo override) |
| POST | /demo/actions/recalculate-shortages | 重算演示缺件 |
| POST | /demo/actions/generate-rfq | 从缺件生成 RFQ (仅直接关系候选) |
| POST | /demo/actions/simulate-quotes | 模拟候选供应商报价 |
| POST | /demo/actions/execute-replenishment | 选择报价并补货入库 |
| POST | /demo/actions/select-alternative | 选用替代料来源 (仅直接关系) |

约束: 动作接口仅操作 6 家主视角企业 (9001-9006); RFQ 候选仅限直接上下游/支撑; 无直接供应商返回 `no_direct_supplier` 提示, 不自动建立关系。

## 8. 页面清单

| 页面 | 路由 | 集成点 |
|---|---|---|
| LoginView | /login | 6 家演示公司 `<select>` + "进入演示" 按钮 (loginDemoCompany) |
| HomeView (经营驾驶舱) | /app | 真实 dashboard API + demo 降级 |
| ProductsBomView | /products-bom | 真实 BOM API |
| ShortageProcurementView | /shortage-procurement | 缺件与采购 |
| CompanyChat | /company-chat | 真实 RAG (partnerChat) |
| CompanyAssistant | /company-assistant | 真实 RAG (chatAsk) |
| AdminKnowledge | /admin/knowledge | 知识库管理 |
| SupplierDashboard/Leads | /supplier, /supplier/leads | 供应商工作台 |
| 悬浮控制台 DemoConsole | (全局, 认证页) | v-if="isDemo", 7 动作 + 重置 + 事件日志, 可拖拽 |

## 9. 测试结果

### 后端核心测试
```
pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py
=> 45 passed, 244 warnings in 41.53s
```

### 新增 demo scenario 测试
```
pytest tests/test_demo_scenario.py
=> 23 passed, 567 warnings in 34.78s
```
覆盖: 场景查询 / 事件日志 / 重置 / 生成订单(+联动) / 消耗库存 / 重算缺件 / 生成 RFQ(直接关系限制 + 无直接供应商提示) / 模拟报价 / 执行补货 / 替代料 / 全链路 / 非主视角企业拒绝 / 基线表未污染。

### 认证 MySQL 测试
`tests/test_auth_mysql.py` **不存在** -> 未验证。
原因: 当前仓库未创建该文件。auth 能力由 `kb/auth.py` (register/login/resolve_token) + `api/routers/auth.py` 承担, 已被 test_enterprise_phase1 间接覆盖 (路由注册校验)。如需独立 MySQL auth 测试, 建议后续补建。

## 10. 前端 build 结果

```
cd web && npm run build
> vue-tsc -b && vite build
✓ built in 1.37s
```
TypeScript 类型检查 + Vite 打包均通过, 产物输出到 `web/dist/`。

## 11. 未验证项

| 项 | 原因 |
|---|---|
| `tests/test_auth_mysql.py` | 文件不存在 |
| 端到端浏览器运行时验证 (登录->控制台->事件日志可见) | 未启动前后端联调服务器, 仅 build + 单元/接口测试验证 |
| 真实 LLM RAG 问答效果 | 测试走离线降级 (LLM 关闭 + Local 向量库); 运行时需 .env 配置 DASHSCOPE_API_KEY |
| Milvus/Neo4j 运行时 | 测试 mock; deploy/docker-compose 未在本 worktree 启动 |

## 12. 已知风险

1. **demo-token 兼容靠显式分支**: 已修复, 但前端 'demo-token' 与后端 KB_DEMO_TOKEN ('kb-demo-user') 仍是两个字面量; 若后续环境变量覆盖 KB_DEMO_TOKEN, 'demo-token' 仍生效 (硬编码兼容)。建议后续统一为单一常量。
2. **resetDemoScenario 前端传 company_id, 后端 ResetReq 只有 scenario_id**: Pydantic 忽略多余字段, 重置按默认场景执行, 功能正常但 company_id 被丢弃。可接受 (重置是场景级, 非企业级)。
3. **~30 家非演示企业不出现在登录入口**: 由 demo_calc 联动写入事件, 但前端未提供查看非主视角企业事件的入口 (需带 company_id 查 /demo/events)。演示时只能看主视角 + 联动事件。
4. **MySQL 依赖**: 测试与运行时均需 matchforge-mysql 容器 (localhost:3306); .env 已从主 worktree 复制 (gitignored, 不入库)。
5. **datetime.utcnow() 弃用警告**: kb/models.py, demo_calc.py, 多 router 使用 `datetime.utcnow()`, Python 3.13 已弃用。功能不受影响, 建议后续迁移 `datetime.now(UTC)`。
6. **concurrent backend branch 更新**: 集成期间 codex/demo-scenario-backend 从 604f11d 更新到 d654778 (追加 docs commit), 合并已取最新。

## 13. 下一步建议

1. **PR**: 从 `codex/demo-scenario-integration` 向 `main` 发起 PR, 标题 "feat: 演示场景沙盘 MVP 集成 (后端+前端+悬浮控制台)"。
2. **端到端联调**: 启动后端 (`uvicorn api.main:main`) + 前端 dev server, 用演示账号 demo@matchforge.ai/demo12345 登录, 逐项验证 11 条核心能力。
3. **补建 test_auth_mysql.py**: 独立覆盖 register/login/me/refresh 的 MySQL 路径。
4. **统一 demo token 常量**: 前后端共享一个 demo token 字面量, 消除硬编码分歧。
5. **非主视角企业事件入口**: 可选, 在控制台或独立页查看联动企业的演示事件。
6. **datetime.utcnow 迁移**: 批量替换为 `datetime.now(timezone.utc)`。
7. **演示脚本**: 结合 `docs/superpowers/plans/matchforge-mvp-demo-script.md` 走一遍完整 RFQ 闭环演示。
