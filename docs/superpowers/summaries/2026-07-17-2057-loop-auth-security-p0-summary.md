# MatchForge Loop - P0 认证安全修复 Summary

- **Time:** 2026-07-17 20:57 +08:00
- **Role:** Development Loop AI (P0 Auth Security Loop)
- **Goal:** 修复认证系统三个 P0 致命安全问题 (认证形同虚设 / 硬编码后门 token / 密码存储不安全且文档不一致)
- **Branch:** `codex/loop-security-auth-p0`
- **Commit:** `558ce73`
- **Base:** `origin/main` (`df2f959`)
- **Ready 状态:** ready (三 P0 全修 + 测试/build 通过 + 未知 token 不再登录 + 源码无硬编码 admin token + 真实密码用 bcrypt + import 不写库 + branch 已 push)

## 0. 审计结论 (动手前)

实际在用的认证链路: `kb/auth.py` (`resolve_token`) -> `api/deps.py` (`get_current_user` / `require_admin`) -> 各 router 依赖。`api/routers/auth.py` (login/register) 与 `api/routers/audit.py` (require_admin) 均走此链路。

`api/auth.py` (JWT/bcrypt)、`api/dependencies.py`、`api/routes/auth.py` 为**死代码** (未在 `api/main.py` 注册, 无 router include)。本轮**未删除** (避免无关重构), 仅在审计中确认; 其 bcrypt 实现可作未来统一认证的参考。

前端 demo 登录原硬编码字面量 `demo-token`; admin 审核页 (`web/src/api/enterprise.ts`) 原硬编码 `kb-admin-demo` (或 `VITE_ADMIN_TOKEN`)。

## 1. 修改文件清单

**后端 (核心安全修复):**
- `kb/auth.py` — 重写: 移除未知 token 兜底放行; 移除硬编码 token 默认值; demo/admin demo token 改环境变量 + `KB_DEMO_MODE` + 非生产门控; 密码改 bcrypt (兼容旧 sha256 渐进迁移); 移除 import 期 `Base.metadata.create_all` 与 `_ensure_seed_users` 副作用; 新增 `seed_demo_users()` / `demo_tokens_enabled()` / `is_production()`; docstring 修正。
- `api/routers/auth.py` — 新增受控 `POST /auth/demo-login` 接口 (demo 模式 + 非生产才可用, 签发 role=user 真实会话, 绑定公司)。
- `api/routers/audit.py` — 修正 docstring 注释, 移除暴露的 `kb-admin-demo` 字样。

**前端:**
- `web/src/stores/auth.ts` — `loginDemoCompany` 改调 `/auth/demo-login` (不再硬编码 `demo-token`); `validateSession` 移除 `token === 'demo-token'` 判断, 依赖 `is_demo`。
- `web/src/api/index.ts` — 401 拦截器移除 `token === 'demo-token'` 判断, 依赖 `is_demo`。
- `web/src/api/enterprise.ts` — 删除硬编码 `ADMIN_TOKEN`/`adminApi` 实例; 审核接口改用共享 `api` (当前会话 token, 管理员须真实登录)。

**种子 / 配置:**
- `scripts/seed_auth_users.py` (新增) — 显式种子脚本, 创建 demo/admin 账号 (bcrypt), 密码来自 `DEMO_USER_PASSWORD`/`DEMO_ADMIN_PASSWORD` 环境变量。
- `.env.example` (新增) — 文档化所有环境变量, 含 `APP_ENV`/`KB_DEMO_MODE`/`KB_DEMO_TOKEN`/`KB_ADMIN_TOKEN`/`DEMO_*_PASSWORD`, 不含真实值。
- `requirements-dev.txt` — 补 `bcrypt>=4.0` (运行时认证依赖, 已安装 5.0.0)。

**测试:**
- `tests/conftest.py` — 在 `kb.auth` 首次 import 前显式设置 `KB_DEMO_MODE=true`/`KB_DEMO_TOKEN=kb-demo-user`/`KB_ADMIN_TOKEN=kb-admin-demo`/`APP_ENV=development` (测试显式开启 demo, 不再依赖源码硬编码默认值)。
- `tests/test_rfq_supplier_loop.py` — `RESTRICTED_TOKEN` 由任意字面量改为 `_ensure_data` 中 `issue_token()` 真实签发 (不再依赖未知 token 兜底放行漏洞); `client` fixture 显式依赖 `_ensure_data` 保证顺序。
- `tests/test_auth_security.py` (新增) — 12 用例覆盖 9 类安全要求。

**顺带修复 (origin/main 预存 build 阻断, 非安全相关):**
- `web/src/types/procure.ts` — `AgentName` 补 `'chat'` 成员 (代码已使用但类型缺失)。
- `web/src/stores/procure.ts` — 移除未用 `saveToLocal` 导入。
- `web/src/components/procure/SessionHistoryPanel.vue` / `web/src/views/HistoryView.vue` — 移除未用 `sessions` 解构。
- `web/src/components/layout/StepNav.vue` / `web/src/components/procure/AgentTimeline.vue` — `Record<AgentName, string>` 补 `chat` 条目 (LABELS/DESC/ICONS)。

## 2. 修复了哪些 P0

- **P0-1 (认证形同虚设):** `resolve_token` 原对未知 token 兜底返回合法 user (`u-{token[:8]}`); 现一律返回 `None` -> `get_current_user` 401。受保护接口未知 token 不再放行。
- **P0-2 (硬编码后门 token):** 删除 `KB_ADMIN_TOKEN`/`KB_DEMO_TOKEN` 默认值 (`kb-admin-demo`/`kb-demo-user`) 与字面量 `demo-token`; 删除前端 `ADMIN_TOKEN='kb-admin-demo'` 与 `persistSession('demo-token', ...)`; 删除 audit.py 注释暴露的 admin token。demo/admin demo token 改环境变量 + 门控 (见 §4)。
- **P0-3 (密码存储不安全 + 文档不一致):** 密码哈希由单轮 `sha256(salt:password)` 迁移到 bcrypt; 修正 module docstring (原声称 bcrypt 实为 sha256); 删除 import 期 `_ensure_seed_users()` 自动写库; 种子账号改显式脚本; 旧 sha256 用户登录时渐进升级 (见 §5)。

## 3. 新认证行为说明

- 未知/未携带 token -> `resolve_token` 返回 `None` -> `get_current_user` 401。
- 真实会话 token (kb_sessions 表) -> 正常解析。
- demo/admin demo 静态 token -> 仅在 `demo_tokens_enabled()` 时解析 (见 §4)。
- `require_admin`: role != admin -> 403 (行为不变)。
- `/auth/demo-login` (新): 签发 role=user 真实会话 token, 绑定指定公司; 仅 demo 模式 + 非生产可用, 否则 404。
- 管理员审核接口 (`/admin/audit-queue*`) 复用当前会话 token; 非管理员 403。

## 4. demo token / admin token 新策略

- 源码**不硬编码任何 token**。`KB_DEMO_TOKEN` / `KB_ADMIN_TOKEN` 必须来自环境变量, 未配置时为 `None` -> 对应通道关闭。
- `demo_tokens_enabled()` = `not is_production() and KB_DEMO_MODE == 'true'`。
  - `is_production()` = `APP_ENV in {production, prod}`。
  - 生产环境 (APP_ENV=production) 一律拒绝 demo/admin demo token, 无论 `KB_DEMO_MODE`。
- 未配置 `KB_ADMIN_TOKEN` 时, `kb-admin-demo` 不再有效 (resolve_token 跳过 demo 分支, 落到会话查表 -> 未命中 -> None)。
- 前端 demo 登录改走 `/auth/demo-login` (后端签发真实会话), 不再把 token 写死在源码。
- 本地开发: 在 `.env` 配 `KB_DEMO_MODE=true` (+ 可选 `KB_DEMO_TOKEN`/`KB_ADMIN_TOKEN`) 启用 demo; 运行 `scripts/seed_auth_users.py` (配 `DEMO_USER_PASSWORD`/`DEMO_ADMIN_PASSWORD`) 创建演示账号。
- 生产: `APP_ENV=production`, 不配 demo token, 不运行 seed 脚本。

## 5. 密码哈希迁移策略

- 新注册 / seed: `_hash_password` 用 `bcrypt.hashpw` (salt 内嵌, salt 列置空 `""`)。
- `_verify_password`: bcrypt 哈希 (以 `$2` 开头) 走 `bcrypt.checkpw`; 历史 sha256 (`salt:password`) 走旧逻辑 (仅用于登录期兼容)。
- **渐进迁移:** `login()` 检测到旧 sha256 用户验证成功后, 自动重哈希为 bcrypt 并清空 `salt` 列 (`user.salt = ""`)。用户无感升级。
- 旧 sha256 用户也可继续用原密码登录 (兼容期), 直到首次登录后被升级。
- 不再产生新的 sha256 哈希; 无明文密码、无固定盐、无单轮 sha256 用于真实账号。
- `KbUser.salt` 列保留 (兼容旧数据 + 渐进迁移), 不需要 DB schema 迁移 (列已存在, 仅 Python 侧 default 改 `""`)。

## 6. 是否删除 import 期写库副作用

**是, 已删除。**
- 移除 `kb/auth.py` 模块级 `Base.metadata.create_all(get_engine())` (表由 `init_db()` 显式创建, `create_app`/seed 脚本会调用)。
- 移除模块级 `_ensure_seed_users()` 调用 (demo/admin 账号改由 `scripts/seed_auth_users.py` 显式创建)。
- `import kb.auth` 不再产生任何数据库连接或写操作 (子进程 + 全新 SQLite 库验证: import + init_db 后 kb_users 计数 = 0)。

## 7. 测试结果

| 命令 | 结果 |
|---|---|
| `pytest tests/test_enterprise_phase1.py tests/test_enterprise_phase2.py tests/test_rfq_supplier_loop.py tests/test_demo_scenario.py -q` | **88 passed** (159.71s) |
| `pytest tests/test_auth_security.py -q` (新增) | **12 passed** (77.33s) |
| `pytest tests/test_register_identity.py -q` (回归) | **6 passed** (11.77s) |
| `pytest tests/test_kb_rag.py::TestCompanyAccessControl -q` (回归) | **3 passed** (41.53s) |

`test_auth_security.py` 12 用例覆盖任务要求的 9 类:
1. 未携带 token -> 401 ✓
2. 随机未知 Bearer token -> 401 + `resolve_token` 返回 None ✓
3. 非 admin token 访问 admin audit -> 403 ✓
4. 未配置 admin demo token 时 `kb-admin-demo` 无效 ✓ (monkeypatch KB_ADMIN_TOKEN=None)
5. 配置 demo token 时 demo-login 可用 ✓ (+ 未知公司 404)
6. 生产模式 (APP_ENV=production) 拒绝 demo token + demo-login 404 ✓ (+ KB_DEMO_MODE=false 拒绝)
7. 密码哈希为 bcrypt + 注册/登录用 bcrypt ✓
8. 旧 sha256 用户登录后升级 bcrypt + salt 清空 ✓
9. import kb.auth 不自动创建 demo/admin 账号 (子进程 + 全新 SQLite 库, COUNT=0) ✓

## 8. 前端 build 结果

`cd web && npm run build` -> **✓ built in 7.91s** (vue-tsc + vite 均通过)。

注: origin/main (`df2f959`) 的 build 原本**预存失败** (5 个 TS 错误, 均在 procure 相关文件, 与安全无关, 已用 stash 验证为 pre-existing)。本轮顺带最小化修复 (补 `AgentName` 的 `'chat'` 成员 + 移除未用变量 + 补 `Record` 的 `chat` 条目) 以满足 build ready 条件。这些修复与 P0 安全无关, 已在 §1 单独标注。

## 9. 未验证项

- **浏览器运行时未验证:** demo 登录端到端 (/login 选公司 -> /auth/demo-login -> 会话生效)、admin 真实登录后审核页可用性、生产模式 demo 拒绝的运行时表现, 均未做浏览器验收 (本轮聚焦后端安全逻辑 + 单元/接口测试)。建议 Codex QA 浏览器复验。
- **Docker/MySQL:** 使用本机已 healthy 的 `matchforge-mysql` 容器跑测试; 未清库/drop/truncate。未在全新 MySQL 上验证 init_db 建表 (子进程用 SQLite 验证了 import 无副作用)。
- **旧 sha256 兼容:** 渐进迁移逻辑有单元测试覆盖; 但未在真实历史库 (若存在旧 sha256 用户) 上端到端验证首次登录升级。
- **test_kb_rag.py 全量**未跑 (仅跑访问控制 3 用例); 历史 ai/kb 模块预存失败 (与本轮无关) 未重跑。
- `api/auth.py` 等死代码未删除 (留待后续统一认证重构)。

## 10. 风险

- **demo-login 接口在 demo 模式下无需密码签发会话:** 这是 demo 通道的固有特性 (本地演示用), 已用 `KB_DEMO_MODE` + 非生产门控; 生产环境强制关闭。但若误在生产开启 `KB_DEMO_MODE`, demo-login 会开放 -- 已用 `is_production()` 双重门控缓解 (生产下即使 `KB_DEMO_MODE=true` 也拒绝)。
- **/login 接口返回固定 `name/role="user"`** (预存, 未改): 前端显示角色可能不准, 但后端鉴权以会话 token 的 role 为准 (KbUser.role), 不影响安全。建议后续修 /login 返回真实用户信息。
- **admin 审核页非 demo 模式需真实 admin 登录:** 原 demo UX (任意访问审核页) 改为需 admin 会话; demo 模式审核页仍走 useDemo 只读数据, 不受影响。可能影响非 demo 演示路径, 需 QA 确认。
- **顺带 build 修复触及 procure 相关文件:** 非本轮安全范畴, 但为满足 ready 必需; 若后续 feat/25-26-message-actions 分支合入, 需注意 `AgentName`/`procure.ts` 的合并冲突。
- **conftest 全局开启 demo 模式:** 测试套件显式配置 demo token; 这是测试语义 (显式 opt-in), 非漏洞。生产环境不受影响 (不读 conftest)。

## 11. 下一步建议

1. **Codex QA 浏览器验收:** /login demo 选公司 -> /auth/demo-login -> 受保护接口可用; 未知 token -> 401/重定向; admin 真实登录 -> 审核页可用; 生产模式 (APP_ENV=production) demo 拒绝。
2. **integration 合并** 本分支到 main (P0 安全, 建议优先)。
3. 后续: 统一认证 (删除 `api/auth.py` 等死代码, 或迁移到 JWT); 修 /login 返回真实用户信息; 为 admin 登录提供 UI 流程。
4. 历史 ai/kb 预存测试失败与本轮无关, 可独立排期。

## 12. branch / commit / ready 状态

- **branch:** `codex/loop-security-auth-p0` (从 `origin/main` `df2f959` 创建, 已 push)
- **commit:** `558ce73`
- **worktree:** `D:/Project/project mvp/MatchForge-loop-auth-security-p0`
- **ready:** yes

ready 条件核对:
1. 三 P0 均修复 ✓
2. 任意未知 token 不再登录 (resolve_token 返回 None, 测试覆盖) ✓
3. 源码无硬编码 admin 万能 token (grep 确认, 仅注释提及) ✓
4. 真实密码不再用单轮 sha256 (bcrypt, 测试覆盖) ✓
5. import 不自动写 demo/admin 用户 (子进程验证 COUNT=0) ✓
6. 后端相关测试通过 (88+12+6+3) ✓
7. 前端 build 通过 ✓
8. summary 已写 ✓
9. loop plan 已更新 ✓
10. branch 已 push ✓
