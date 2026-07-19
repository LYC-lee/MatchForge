# MatchForge Loop-001 Summary - P1 注册身份模型

- **Time:** 2026-07-17 01:40 +08:00
- **Role:** Development Loop AI (loop-001)
- **Goal:** P1 - 注册身份模型修复: 删除注册时"采购方/供应商"固化身份, 改为"企业类型 + 用户权限角色"; 供需角色由业务关系动态派生。
- **Branch:** `codex/loop-001-register-identity`
- **Commit:** `3c023a8`
- **Base:** `origin/main` (`916baed`)
- **Ready 状态:** ready (浏览器验收移交 Codex QA; 预存 login 路由 P1 已记录待下一轮)

## 1. 修改文件清单

**前端:**
- `web/src/views/RegisterView.vue` - 移除 buyer/supplier role-tabs, 改企业类型 `<select>`; 文案中性化; 移除 role ref 与 role-tabs CSS
- `web/src/stores/auth.ts` - `AuthUser` 新增 `enterprise_type`, `role` 类型扩展 (member/enterprise_admin/platform_admin); `register()` 发送 `role:'member'` + `enterprise_type`
- `web/src/components/procure/SuppliersMatch.vue` - 修复预存 build 错误: 移除未用 `watch` import
- `web/src/types/procure.ts` - 修复预存 build 错误: `confirmed_spec` 类型 `Record<string, SpecField>` → `Record<string, SpecField | string>` (与 parsed_spec/normalized_spec 一致)
- `web/src/views/ProcureView.vue` - 修复预存 build 错误: 移除未用 `isStreaming` 解构
- `web/src/mock/sse.ts` - 配合类型变更: buildRfqStream 调用处加 narrowing cast

**后端:**
- `api/schemas.py` - `RegisterRequest` 新增 `enterprise_type: str = "other"`, `role` 默认 `buyer` → `member`
- `api/models/__init__.py` - `User` 模型新增 `enterprise_type` 列; `role` 默认 `member` + 注释更新
- `api/routes/auth.py` - 注册路由: 移除无效 `name=`/`company=` kwargs (live 模型无此列, 原会 TypeError), 新增 `enterprise_type=` 存储, 响应回显 name/company

**数据/测试:**
- `database/migrations/06_enterprise_type.sql` (新增) - 非破坏式 ALTER TABLE users ADD enterprise_type
- `tests/test_register_identity.py` (新增) - 4 个防回归测试

## 2. 修改说明

注册流程不再要求用户在"采购方/供应商"间二选一。改为收集**企业类型**(7 类: manufacturer / component_material / oem_brand / channel_customer / logistics_service / government_park / other), 自注册用户默认**权限角色**为 `member`。供需角色(谁是采购方/谁是供应商)由订单、RFQ、BOM、服务关系动态派生, 不在注册时固化——这与产业链平台模型一致。

前端 `RegisterView` 用企业类型下拉替换了角色 tabs; `auth` store 自注册发送 `role:'member'` + `enterprise_type`; 后端 `RegisterRequest` 接受 `enterprise_type`, `User` 模型新增列存储, 注册路由实际写入。

附带修复 3 个**预存**前端 build 错误(详见第 8 节), 否则 `npm run build` 在全新 checkout 上失败(主仓增量 `vue-tsc -b` 缓存掩盖了这些错误)。

## 3. 数据变更说明

- **改了哪些数据:** `users` 表新增 `enterprise_type VARCHAR(40) NOT NULL DEFAULT 'other'` 列 (模型 + 迁移 06)。
- **为什么改:** 存储注册时收集的企业类型, 支撑"企业类型 + 权限角色"身份模型。
- **是否影响真实业务表:** 是, `users` 表新增列。**非破坏式**(仅 ADD COLUMN, 不删/不改现有列, 不改写历史数据)。
- **是否可重复执行:** 全新库由 `Base.metadata.create_all` 自动建表已含此列, 无需迁移; 已存在的 `users` 表需手动执行 `06_enterprise_type.sql` (MySQL ADD COLUMN 不支持 IF NOT EXISTS, 首次执行前确认列不存在)。`users.role` 历史数据不自动改写(避免影响 demo 种子 `role="buyer"`)。

## 4. 测试与 Build 结果

- **新增防回归测试:** `tests/test_register_identity.py` 4/4 通过 (RegisterRequest 默认 role=member / 接受 enterprise_type / User 模型含 enterprise_type 列 / 默认角色非 buyer/supplier)。
- **全量后端 pytest:** 229 通过 / 16 失败 / 105.91s。16 个失败**全部**在 ai/agent + kb_rag 模块 (test_alternatives / test_kb_rag / test_match / test_supervisor_advanced / test_supervisor_route), 与本轮改动**零重叠** (grep 确认这些测试不引用 RegisterRequest / enterprise_type / api.models.User / auth 路由)。属预存失败(async mock 警告 + KB 数据依赖), 见 [[matchforge-demo-procurement-loop]] 等历史记录。
- **前端 build:** `npm run build` 通过 (`vue-tsc -b && vite build`, ✓ built in 4.26s, RegisterView bundle 19.31 kB)。

## 5. 浏览器验收结果

**未做浏览器运行时验收, 明确移交 Codex QA 验收。**

build 通过(类型检查 + 打包)保证编译正确, 但注册页端到端交互(填写企业类型 → 提交 → 后端写入 → 进入工作台)未在浏览器实测。建议 QA 重点验收:
- RegisterView 企业类型下拉渲染与提交
- /api/v1/auth/register 返回 enterprise_type
- demo 登录流程不受影响(仍走 demo-token, role=buyer)

## 6. 未验证项

- 注册端到端浏览器交互(移交 QA)。
- `06_enterprise_type.sql` 在真实 Docker MySQL 上的执行(无 DB 访问环境)。
- 登录路由 `/api/v1/auth/login` 与 `/me` 仍引用 `user.name`/`user.company`(live 模型无此列)——预存 P1, 未修(超出本轮 1-2 目标范围)。

## 7. 风险

1. **预存 P1 - auth 路由 name/company 缺列:** `api/routes/auth.py` 的 login(行 62)/refresh(行 89)/me(行 101) 响应仍引用 `user.name`/`user.company`, 但 live `User` 模型(由 `Base.metadata.create_all` 建表)无此二列 → 运行时 AttributeError。系统当前经 demo-token 流程运行, 未触发真实 login 路由, 故未暴露。本轮仅修了 register 路由; login/me 未修。
2. **预存 P1 - `api/database.py` 演示种子:** 第 44-49 行 `User(name="Demo Buyer", company="MatchForge Demo", role="buyer")` 同样使用无效 kwargs → 全新库 seed 时 TypeError。现有库因 demo 用户已存在而跳过, 未暴露。
3. **模型文件重复:** `api/models.py`(文件) 与 `api/models/`(包) 并存, Python 包优先, 文件被遮蔽为死代码。两者 `User` 定义不一致(文件有 name/company, 包有 enterprise_id)。潜在混淆源。
4. **plan/summary 文档未纳入 git:** 本轮 plan 与 summary 仍以未跟踪文件存在于主工作区 main(延续 01:09 integration loop 状态), 阻碍 integration loop 合并(working tree not clean)。建议 integration loop 优先把这批文档提交到 main。
5. **16 个预存后端测试失败**未被本轮触及, 仍待后续轮次处理(async mock + KB 数据)。

## 8. 预存 Build 错误修复说明(本轮附带)

`origin/main` 全新 checkout 上 `npm run build` 失败于 3 处(主仓增量缓存掩盖):
1. `SuppliersMatch.vue:2` - `watch` 导入未使用 → 移除
2. `types/procure.ts:123` - `confirmed_spec: Record<string, SpecField>` 与 store 实际发送 `Record<string, string>` 不兼容 → 改为 `Record<string, SpecField | string>`(与同文件 parsed_spec/normalized_spec 一致); mock/sse.ts buildRfqStream 调用处加 narrowing cast
3. `ProcureView.vue:36` - `isStreaming` 解构未使用 → 移除

均不改变运行时行为, 仅消除类型错误, 使 build 在全新环境通过。

## 9. 下一步建议

1. **Codex QA 浏览器验收**本轮注册页(企业类型下拉 + 提交 + demo 登录无回归)。
2. **下一轮 dev loop 修预存 P1 auth 路由:** login/refresh/me 移除 `user.name`/`user.company` 引用(live 模型无此列), 决定 name/company 来源(新增列 or 用 username/enterprise.name)。同步修 `api/database.py` 种子。
3. **integration loop 优先提交** plan/summary/qa-findings 文档到 main, 解锁后续合并。
4. 清理 `api/models.py` 死文件 or 与 `api/models/` 包合并(消除重复)。
5. 推进待办 #2: 6 家公司浏览器端验收; #3: 远达物流视图。

## 10. 元信息

- **branch:** `codex/loop-001-register-identity`
- **commit:** `3c023a8`
- **worktree:** `D:/Project/project mvp/MatchForge-loop-001-register-identity`
- **ready:** yes(目标完成 + 4/4 新测试过 + build 过 + 浏览器验收移交 QA; 预存 login 路由 P1 记录待下一轮, 非本轮引入)
