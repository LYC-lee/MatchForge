# MatchForge Loop-003 Summary - P1 修复 auth login/me 路由 (User 补 name/company 列)

- **Time:** 2026-07-17 04:14 +08:00
- **Role:** Development Loop AI (loop-003)
- **Goal:** loop-001 发现的预存 P1 -- `api/routes/auth.py` 的 login/refresh/me 响应引用 `user.name`/`user.company`, 但 live `User` 模型无此二列(运行时 AttributeError); `api/database.py` 演示种子 `User(name=, company=)` 全新库 TypeError。补列后 auth 全链路可用。
- **Branch:** `codex/loop-003-auth-user-name-company`
- **Commit:** `067333f`
- **Base:** `origin/codex/loop-002-frontend-runtime-fixes` (`46626fc`) -- **stacked**(栈现在 3 层: loop-01→loop-02→loop-03)
- **Ready 状态:** ready (浏览器验收移交 Codex QA; 路由端到端需 DB, 以模型/schema 测试 + build 为回归)

## 1. 修改文件清单

- `api/models/__init__.py` - `User` 模型新增 `name` / `company` 列
- `api/routes/auth.py` - 注册路由恢复 `name=req.name`/`company=req.company` 持久化, 响应用 `user.name`/`user.company`
- `database/migrations/07_user_name_company.sql` (新增) - 非破坏式 ALTER TABLE users ADD name/company
- `tests/test_register_identity.py` - 扩展 2 个防回归测试(共 6 个)

## 2. 修改说明

**根因:** live `User` 模型(由 `Base.metadata.create_all` 建表)有 `username`/`enterprise_id`/`role`/`enterprise_type`/`email` 等, 但**无 `name`/`company` 列**(被遮蔽的 `api/models.py` 有, 包版本没有)。而 `login`/`refresh`/`me` 路由响应与 `database.py` 种子均引用 `user.name`/`user.company` -> 缺列 AttributeError / 构造 TypeError。系统经 demo-token 流程运行, 真实 login 路由未触发, 故未暴露。

**修复:**
- `User` 模型新增 `name`(VARCHAR 100, default '') 与 `company`(VARCHAR 200, default '')。`enterprise_id`(关联企业 FK, 可空)保留不变 -- `company` 为注册时展示用字符串, `enterprise_id` 为后续绑定企业。
- 注册路由: loop-001 因缺列临时把 `name`/`company` 从构造器移除并从 req 回显; 现恢复 `name=req.name`/`company=req.company` 持久化, 响应改用 `user.name`/`user.company`(持久值)。
- `login`/`refresh`/`me` 路由: **无需改动** -- 列存在后 `user.name`/`user.company` 自动可用。
- `database.py` 演示种子: **无需改动** -- `User(name="Demo Buyer", company="MatchForge Demo", ...)` 现为合法 kwargs。
- 与被遮蔽的 `api/models.py` 定义对齐(该文件有 name/company, 但被包遮蔽为死代码 -- 见风险)。

## 3. 数据变更说明

- **改了哪些数据:** `users` 表新增 `name VARCHAR(100) NOT NULL DEFAULT ''` 与 `company VARCHAR(200) NOT NULL DEFAULT ''` 两列(模型 + 迁移 07)。
- **为什么改:** auth 路由全链路(login/refresh/me/register 持久化 + 种子)依赖此二列。
- **是否影响真实业务表:** 是, `users` 表新增列。**非破坏式**(仅 ADD COLUMN, 不删/不改现有列, 不回写历史数据; 历史用户 name/company 留空默认 '')。
- **是否可重复执行:** 全新库由 `Base.metadata.create_all` 自动建表已含此二列, 无需迁移; 已存在的 `users` 表需手动执行 `07_user_name_company.sql`(MySQL ADD COLUMN 不支持 IF NOT EXISTS, 首次执行前确认列不存在)。

## 4. 测试与 Build 结果

- **防回归测试:** `tests/test_register_identity.py` 扩展至 6 个, 全过(46.28s):
  - 原 4 个(loop-001): role 默认 member / 接受 enterprise_type / User 含 enterprise_type 列 / 默认角色非 buyer-supplier
  - 新增 2 个: User 含 name/company 列 / RegisterRequest 携带 name/company
- **前端 build:** `npm run build` 通过(✓ 3.30s)。本轮无前端改动, 确认 stacked base 绿。
- **全量后端 pytest:** 未重跑(本轮仅改 auth 模型/路由 + 测试; loop-001 已验证 229 过/16 预存失败 ai-kb 无重叠; 新增 2 测试过)。

## 5. 浏览器验收结果

**未做浏览器运行时验收, 明确移交 Codex QA 验收。**

模型/schema 测试覆盖列存在性(防回归: 若有人移除 name/company 列, 测试即失败, login/me 路由会再次坏)。路由端到端(register->login->/me)需真实 DB, 测试环境 mock 了 mysql_client 无法覆盖。建议 QA 重点验收:
- `/register` 真实注册 -> 返回 name/company/enterprise_type 持久化
- `/login` 真实登录 -> 不再 AttributeError, 返回 name/company
- `/me` -> 返回 name/company/role
- demo 登录(demo-token)流程无回归

## 6. 未验证项

- 路由端到端 register/login/refresh/me(需真实 DB; 测试环境 mock)。
- 迁移 `07_user_name_company.sql` 在真实 Docker MySQL 执行(无 DB 访问环境)。
- 浏览器运行时(移交 QA)。
- 历史 users 行 name/company 为空(默认 ''), 未回填 -- 不影响登录(返回空串), 但展示为空。

## 7. 风险

1. **栈增长至 3 层(紧急):** loop-01→loop-02→loop-003 全部 ready 但**未合并**(integration loop 未调度, origin/main 仍 916baed + P0 build 失败)。每轮 dev loop 只能继续 stack。**integration 必须尽快跑**, 合并顺序: loop-001 → loop-002 → loop-003(每个是前者超集 + 增量)。合并后 main 解除 P0 build + 3 P1(register identity / products-bom+audit / auth login-me)。**建议用户立即手动触发 integration loop 或合并这 3 个分支。**
2. **路由级无单测:** auth 路由端到端依赖真实 DB, 测试环境 mock 之, 无路由级回归测试。仅模型列存在性测试防回归。引入 DB 测试基建属过度工程化, 留待后续。
3. **`api/models.py` 死文件仍存在:** 与 `api/models/` 包重复(loop-001 发现), 包优先, 文件被遮蔽。两者 User 定义现已更接近(都有 name/company), 但仍不一致(文件有 company 无 enterprise_id; 包有 enterprise_id + 现补 name/company)。建议后续清理死文件。
4. **历史用户 name/company 空:** 不回写, 展示为空串。如需补, 手动 UPDATE。

## 8. 下一步建议

1. **Codex QA 浏览器验收**本轮真实 register/login/me 链路。
2. **【最紧急】integration loop 合并 loop-001 + loop-002 + loop-003 到 main** -- 栈已 3 层, 不合并 dev loop 无法持续。合并前需先把 plan/summary/qa-findings 未跟踪文档提交到 main。
3. **下一轮 dev loop** 候选(择一, QA 01:24 余 2 P1):
   - QA P1-4 / 待办 #3: 9004 远达物流语义(按 company_segment 切换服务能力/运力/履约标签, 跨多视图, 可能拆 2 轮)。
   - QA P1-3 / 待办 #6: 供应商工作台"正在拉取"空状态语义。
   - QA P2: 9006 demo 公司名统一(毅诚被动元件)。
4. 若 integration 仍未跑, 下一轮 stack on loop-003, 并再次强调 integration 优先。

## 9. 元信息

- **branch:** `codex/loop-003-auth-user-name-company`
- **commit:** `067333f`
- **base:** `codex/loop-002-frontend-runtime-fixes` (`46626fc`), stacked (3 层)
- **worktree:** `D:/Project/project mvp/MatchForge-loop-003-auth-user-name-company`
- **ready:** yes(目标完成 + 6/6 测试过 + build 过 + 浏览器验收移交 QA; 解除 loop-001 发现的 auth login/me 路由 P1)
