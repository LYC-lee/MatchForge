# 演示场景集成计划 (demo-scenario-integration)

> 目标: 把 `codex/demo-scenario-backend` (沙盘后端) 与 `codex/demo-scenario-frontend` (悬浮控制台 + 演示登录) 合并为一个可运行 MVP。

## 1. 集成策略

| 项 | 决策 |
|---|---|
| 基线 | `main` (f9c9508) |
| 集成分支 | `codex/demo-scenario-integration` |
| worktree | `D:\Project\project mvp\MatchForge-demo-scenario-integration` |
| 合并顺序 | 先 backend (Python/DB), 后 frontend (web) |
| 冲突优先级 | 业务能力完整方 > 真实接口调用 > 非破坏式迁移 |
| 基线保护 | 不清库、不删接口、demo_* 表与基线业务表隔离 |

## 2. 来源分支

- 后端: `codex/demo-scenario-backend` @ d654778 (feat 沙盘后端 + docs 总结)
- 前端: `codex/demo-scenario-frontend` @ 68e2437 (悬浮控制台 + 演示登录 + 场景 API 接入)

两分支均从 `main` f9c9508 拉出, 文件无重叠 (后端只动 Python/SQL/docs, 前端只动 web/src/docs)。

## 3. 必须保留的核心能力 (验收对照)

1. ✅ 6 家演示公司可在登录页选择进入 (LoginView `<select>` + DEMO_COMPANIES)
2. ✅ 登录后固定当前企业 (useEnterpriseContext 绑定 auth.user.company_id, watch 强制同步)
3. ✅ 左侧删除企业选择框 (AppHeader 仅显示当前绑定企业 + "演示账号固定视角"徽章)
4. ✅ 其他 ~30 家企业真实参与 RFQ/报价/补货/替代料/因果联动 (demo_calc 联动直接上下游/支撑)
5. ✅ 悬浮控制台只在 demo 模式显示 (DemoConsole `v-if="isDemo"` = `auth.user.is_demo`)
6. ✅ 控制台操作当前登录企业, 后端联动上下游/支撑 (actions 传 currentEnterpriseId, demo_calc 写联动事件)
7. ✅ 事件日志可见 (GET /demo/events, 控制台内嵌事件列表)
8. ✅ 可重置整个演示场景 (POST /demo/scenarios/reset, 仅清 demo_* 表)
9. ✅ RFQ 主链路打通 (缺件→RFQ→报价→对比→补货→入库→重算缺件)
10. ✅ 问答页调用真实 RAG (CompanyAssistant/CompanyChat → chatAsk/partnerChat → kb.rag.answer)
11. ✅ demo token 兼容 + 真实 JWT/MySQL 登录不破坏 (resolve_token 接受 'demo-token' 与 'kb-demo-user')

## 4. 集成修复项

| 修复 | 文件 | 原因 |
|---|---|---|
| demo-token 显式兼容 | `kb/auth.py` | 前端用字面量 'demo-token', 后端 KB_DEMO_TOKEN 默认 'kb-demo-user'; 原靠 fallback 路径生效但不显式。改为 `token == KB_DEMO_TOKEN or token == "demo-token"` 映射同一 demo-user, 不破坏 JWT/MySQL 登录。 |

## 5. 验证清单

- [x] 后端核心测试: test_enterprise_phase1 + test_enterprise_phase2 + test_rfq_supplier_loop (45 passed)
- [x] 新增 demo scenario 测试: test_demo_scenario (23 passed)
- [ ] 认证 MySQL 测试: test_auth_mysql.py 不存在 → 未验证 (说明: 该文件在当前仓库未创建)
- [x] 前端 build: `npm run build` 通过 (vue-tsc + vite, 1.37s)
- [x] 冲突标记: 无
- [x] 固定回答回归: 无 (buildFallbackAnswer/本地降级回答/固定回答 均未命中)
- [x] 核心控制台 mock: 无 (DemoConsole/demo.ts 全走真实 API)
- [x] 登录页不被 AppHeader 包住: blankPaths 排除 / /login /register
- [x] 企业切换框已删除: AppHeader 无 select/dropdown
- [x] demo 控制台仅 demo 模式: v-if="isDemo"

## 6. 提交与推送

- 合并 commit: c46218b (backend) + 4e36ea9 (frontend)
- 集成修复 commit: 待提交 (kb/auth.py + 本计划 + 总结)
- 推送: `git push -u origin codex/demo-scenario-integration`
- 不直接合并 main, 输出 PR 建议
