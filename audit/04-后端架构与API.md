# 后端架构与 API 审计报告

> 审计范围：`api/` 全部（main.py、routers/、routes/、models.py、models/、schemas.py、auth.py、config.py、database.py、db/、dependencies.py、deps.py、db_init.py），并追踪其直接依赖的 `kb/auth.py`、`kb/db.py`、`kb/models.py` 中与会话/鉴权/RFQ 相关的部分。
> 审计方式：只读静态审计 + 导入行为验证（`python -c "import api.models"`）。未启动服务、未做任何写操作。
> 代码体量：活代码 `api/routers/` 12 个文件 72 个端点装饰器；死代码 `api/routes/` 8 个文件 19 个端点装饰器。

---

## 1. 领域概述

### 1.1 真实运行的后端是什么

【已确认事实】`api/main.py:56-93` 只注册了 `api/routers/` 下的 12 个路由模块（auth、companies、relationships、chat、kb_admin、enterprise_context、dashboard、rfqs、supplier_leads、audit、demo，procure 以 try/except ImportError 可选挂载，`api/main.py:73-78`）。所有活路由的鉴权、会话、业务数据全部落在 `kb/` 层：

- 鉴权：`api/deps.py:12-29`（`get_current_user`/`require_admin`）→ `kb/auth.py`（`resolve_token`/`KbUser`/`KbSession`，bcrypt，会话表无过期字段）；
- 数据访问：`kb/db.py:49-60` 的同步 `session_scope()`（自动 commit/rollback/close），ORM 模型在 `kb/models.py`（`RfqRecord`/`RfqSupplierLink`/`QuotationRecord`/`AuditQueueItem` 等，`kb/models.py:500-608`）；
- 公司级访问控制：`api/deps.py:32-52` `check_company_access` → `kb/auth.py:227-241` `can_access_company`。

【已确认事实】核心闭环（RFQ 创建→发送→供应商查看/报价→报价对比→审核队列）在 `api/routers/rfqs.py`（470 行）、`api/routers/supplier_leads.py`（124 行）、`api/routers/audit.py`（103 行）中真实实现，且单据落库（`kb_rfqs`/`kb_rfq_suppliers`/`kb_quotations`/`kb_audit_queue`）。

### 1.2 并存的另一套死代码

【已确认事实】`api/routes/`（8 文件、19 端点）+ `api/auth.py` + `api/dependencies.py` + `api/database.py` + `api/models.py` + `api/schemas.py` + `api/base.py` + `api/config.py` + `api/db/session.py` + `api/models/__init__.py` 构成第二套"async SQLAlchemy + JWT + 双库"体系，**未被 `api/main.py` 引用**，全项目引用方只有它们自身、`api/routes/*` 和 `tests/test_register_identity.py`。即死代码，约 1000+ 行。项目内文档（`docs/api-test-checklist.md:469`、`docs/superpowers/summaries/2026-07-17-2057-loop-auth-security-p0-summary.md:15`）也已确认其死代码属性。

### 1.3 分层与依赖方向

【已确认事实】依赖方向为 `api/routers → api/deps → kb/*`、`api/routers/procure → ai/*`，反向引用不存在（`kb/`、`ai/` 中 grep `import api`/`from api` 无任何匹配），**当前无循环依赖**。

【已确认事实】分层不一致：dashboard/demo 路由薄、计算委托 `kb/dashboard_calc.py`/`kb/demo_calc.py`（良好）；而 rfqs/supplier_leads/audit 路由把状态机推进、审核规则（1.5 倍目标价）、审核项生成等业务规则直接写在 router 函数体内（如 `api/routers/rfqs.py:285-315、391-415`）。同时存在三套互不相干的 ORM Base：`kb/db.py:15`、`api/base.py:8`、`api/models/__init__.py:22-23`（双 Base）。

### 1.4 REST 设计现状

【已确认事实】列表响应主流为 `{items, total}` 裸 dict，但存在多种形状（`{rfq: ...}`、`{quotation: ...}`、`{sessions: ...}`、SSE 事件流），全项目无任何 `response_model` 声明、无全局异常处理器、无统一错误码（仅 HTTPException `{detail}`）、列表接口基本无分页参数。

---

## 2. 问题清单

### 问题 1：注册接口可自选角色，自助提权为 admin（致命）

- **所属模块**：认证（api/routers/auth.py + kb/auth.py）
- **严重程度**：致命
- **影响范围**：全部 `/admin/*` 接口（知识库重建、审核队列审批）、全部依赖 `role` 的鉴权决策
- **发现依据**：`api/routers/auth.py:21-27`（`RegisterRequest.role: str = "buyer"` 自由文本字段）、`api/routers/auth.py:45`（`register(..., req.role)` 透传）、`kb/auth.py:140-160`（`KbUser(role=role)` 原样落库，无白名单校验）、`kb/auth.py:158/181`（会话写入 `user.role`）、`api/deps.py:23-29`（`require_admin` 仅判断 `role == "admin"`）
- **问题描述**：`POST /api/v1/auth/register` 请求体传 `{"role": "admin"}` 即可注册出管理员账号；签发的会话 token 携带 `role=admin`，随后可调用 `POST /api/v1/admin/kb/generate`、`POST /api/v1/admin/audit-queue/{id}/approve` 等全部管理接口。
- **可能后果**：任何匿名访问者一键提权为平台管理员，可重建/清空向量索引、审批通过异常报价与供应商匹配审核项，整个审核闭环失效。
- **推荐解决方案**：服务端注册路径强制 `role="user"`（忽略或拒绝请求体中的 role）；管理员角色只能由管理员接口或 seed 脚本（已有 `scripts/seed_auth_users.py`）授予；如确需保留字段，对 `role` 加 `Literal["user"]` 校验。
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：携带 `role="admin"` 注册后，`GET /api/v1/auth/me` 返回 `role="user"`，且该 token 调 `GET /api/v1/admin/kb/tasks` 返回 403；新增 pytest 覆盖该用例。

### 问题 2：RFQ 读接口组横向越权（严重）

- **所属模块**：api/routers/rfqs.py
- **严重程度**：严重
- **影响范围**：所有买方企业的询价单、供应商报价、报价对比数据（商业敏感）
- **发现依据**：`api/routers/rfqs.py:238-252`（`list_rfqs` 无 `check_company_access`，不传过滤条件时返回全表）、`rfqs.py:255-266`（`get_rfq` 无校验）、`rfqs.py:421-436`（`list_quotations` 无校验）、`rfqs.py:439-470`（`quote_comparison` 无校验）。对比同文件 `rfqs.py:274`（`send_rfq` 有校验）与 `rfqs.py:332`（`list_company_rfqs` 有校验），属漏写而非设计。
- **问题描述**：任何登录用户（含 demo token）遍历 `rfq_id` 即可读取任意企业的 RFQ 详情、全部供应商报价与最低价对比。
- **可能后果**：采购底价、目标价、供应商报价等企业核心商业机密跨企业泄露。
- **推荐解决方案**：在 4 个端点加载 RFQ 后调用 `check_company_access(user, r.buyer_company_id)`；`list_rfqs` 强制要求 `buyer_company_id` 并校验，或按当前用户可见公司集合过滤。
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：用户 A 的 token 请求用户 B 企业的 `GET /rfqs/{id}`、`GET /rfqs/{id}/quotations`、`GET /rfqs/{id}/quote-comparison` 均返回 403/404；`GET /rfqs?buyer_company_id=B` 返回 403。

### 问题 3：procure 路由组完全无鉴权，会话可被任意读删（严重）

- **所属模块**：api/routers/procure.py
- **严重程度**：严重
- **影响范围**：LLM 调用成本、用户寻源会话隐私
- **发现依据**：`api/routers/procure.py:68-71`（`procure_stream` 无 `Depends(get_current_user)`）、`procure.py:47`（`user_id` 为请求体自由字段）、`procure.py:82`（`user_id = req.user_id or "anonymous"`）、`procure.py:201-232`（`list_user_sessions` 以 query 参数 `user_id` 查询、`get_session_detail`/`delete_user_session` 仅凭 `thread_id`，均无鉴权与归属校验）
- **问题描述**：匿名用户可直接调用 SSE 寻源流（消耗通义千问额度）；任何人可枚举任意 `user_id` 的会话列表、读取/删除任意 `thread_id` 的会话快照（含采购需求与匹配结果）。
- **可能后果**：LLM 费用被恶意刷量；用户寻源意图与供应商信息泄露；会话被恶意删除。
- **推荐解决方案**：全组加 `Depends(get_current_user)`，`user_id` 一律取 `user["user_id"]` 忽略客户端传值；会话读删接口校验 `session.user_id == user["user_id"]`。
- **修改成本**：低
- **优先级**：P0
- **是否影响当前上线**：是
- **是否需要重构**：否
- **验收标准**：无 token 调 `POST /procure/stream` 返回 401；用户 A 的 token 读/删用户 B 的 `thread_id` 返回 403/404；请求体伪造 `user_id` 不生效。

### 问题 4：双路由目录并存，约半数 api/ 代码为死代码且仍在被测试（严重）

- **所属模块**：api/routes/*、api/auth.py、api/dependencies.py、api/database.py、api/models.py、api/schemas.py、api/base.py、api/config.py、api/db/、api/models/
- **严重程度**：严重
- **影响范围**：代码可维护性、测试可信度、新人理解成本
- **发现依据**：`api/main.py:56-93`（只 include `api.routers`）；死代码互相引用闭环（如 `api/routes/auth.py:11-15`）；`tests/test_register_identity.py:16,41,58`（测试 `api.schemas.RegisterRequest` 与 `api.models.User`——全是死代码对象）；历史文档显示曾为死代码 `api/routes/auth.py` 修过 P1 bug（`docs/superpowers/summaries/2026-07-17-0414-loop-003-auth-user-name-company.md:14`）
- **问题描述**：两套同名职责文件并存（`api/routes/auth.py` vs `api/routers/auth.py`、`api/routes/procure.py` vs `api/routers/procure.py`、`api/routes/rfq.py` vs `api/routers/rfqs.py`、`api/dependencies.py` vs `api/deps.py`），且接口路径重叠（`/api/v1/auth/login`、`/api/v1/rfqs` 两版实现）。测试文件断言的是死代码的行为，绿测试不等于活系统正确；团队已出现"给死代码修 bug"的无效投入。
- **可能后果**：后续维护者误改死代码；路由注册时一旦发生误 import 会出现同路径双实现、行为不确定；测试报告失真。
- **推荐解决方案**：删除或整体移入 `legacy/`（并加 `__init__` 防导入）：`api/routes/`、`api/auth.py`、`api/dependencies.py`、`api/database.py`、`api/models.py`、`api/schemas.py`、`api/base.py`、`api/config.py`、`api/db/`、`api/models/`；同步删除/改写 `tests/test_register_identity.py` 使其针对活路由 `api/routers/auth.py`；若确需保留 JWT 实现作参考，在 README 明确标注。
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：否（运行时无影响，属工程健康）
- **是否需要重构**：是（删除式重构）
- **验收标准**：`grep -rn "api.routes\|api.dependencies\|api.database" --include="*.py" .` 无引用；`pytest` 全绿；`api/` 下只存在一套 auth/deps/models。

### 问题 5：`api/models.py` 与 `api/models/` 包同名冲突，包遮蔽模块（严重）

- **所属模块**：api/models.py、api/models/__init__.py、api/database.py
- **严重程度**：严重
- **影响范围**：任何 `from api.models import ...` 的代码路径
- **发现依据**：`api/models.py` 与 `api/models/__init__.py` 同目录同名共存；实测 `python -c "import api.models"` 加载的是 `api\models\__init__.py`（包优先，traceback 文件路径可证）；`api/models/__init__.py` 中无 `AuditRecord`，而 `api/database.py:30` 写 `from api.models import User, Supplier, RFQ, Lead, AuditRecord`——该导入必然 `ImportError`；`api/routes/auth.py:37` 使用 `enterprise_type`（只存在于包内模型，`api/models/__init__.py:50`），`api/database.py:43-49` 使用 `name=`/`company=`（只存在于模块内模型，`api/models.py:30-31`）——两份代码分别依赖两个不同模型，必有一方运行时崩溃
- **问题描述**：同名模块/包遮蔽导致 `api.models` 的真实指向依赖 Python 导入规则而非开发者意图，死代码内部已互相矛盾、无法同时成立。
- **可能后果**：若未来有人启用这套体系，`init_db()` 直接 ImportError；排障时极易误判。
- **推荐解决方案**：随问题 4 一并删除；删除前至少在包/模块二者之一改名消除遮蔽。
- **修改成本**：低（并入问题 4）
- **优先级**：P1
- **是否影响当前上线**：否
- **是否需要重构**：是
- **验收标准**：`api/` 下不存在 `models.py` 与 `models/` 并存；`python -c "from api.models import *"` 行为唯一可预期（或模块整体不存在）。

### 问题 6：关键写接口无幂等设计，重复提交产生脏数据（严重）

- **所属模块**：api/routers/rfqs.py、kb/models.py
- **严重程度**：严重
- **影响范围**：RFQ、报价、报价对比与审核队列的数据正确性
- **发现依据**：`api/routers/rfqs.py:183-235`（`create_rfq` 无幂等键/防重）；`rfqs.py:349-418`（`create_quotation` 每次调用都新增一条 `QuotationRecord`）；`kb/models.py:580-582`（`kb_quotations` 只有普通联合索引，无 `(rfq_id, supplier_company_id)` 唯一约束）；`rfqs.py:224-230`（`supplier_candidates` 未去重，重复 id 触发 `uq_rfq_supplier` 唯一约束 → IntegrityError → 500）
- **问题描述**：双击/重试 `POST /rfqs` 生成两张相同询价单；供应商重复提交报价会留下多条报价，`quote_comparison`（`rfqs.py:450-452` 按单价排序全量参与排名）可被恶意刷榜；前端传重复候选供应商直接 500。
- **可能后果**：买方看到重复询价单；报价对比被最低价刷榜污染；异常 500 暴露内部错误。
- **推荐解决方案**：①`create_rfq` 入参去重 `set(candidates)`；②`kb_quotations` 若业务语义为"一供应商一报价"，加唯一约束并改为 upsert（已存在则更新价格），或保留多报价但接口层面幂等（`Idempotency-Key` header 或 `(rfq_id, supplier_id, client_quote_id)` 去重）；③前端提交后禁用按钮（前端域，仅提示）。
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：是（演示双击即可复现）
- **是否需要重构**：否
- **验收标准**：同一请求体重试两次 `POST /rfqs` 只产生一张单（或第二张明确 409）；同一供应商对同一 RFQ 重复报价不产生重复行参与排名；候选列表含重复 id 返回 200 且只建一条线索。

### 问题 7：RFQ 编号生成存在并发竞态与全表扫描（严重）

- **所属模块**：api/routers/rfqs.py
- **严重程度**：严重
- **影响范围**：RFQ 创建成功率、数据库压力
- **发现依据**：`api/routers/rfqs.py:100-111`（`SELECT ... LIKE 'RFQ-YYYY-%'` 全量捞出后在 Python 里求 max，再 +1）；`kb/models.py:504`（`rfq_number` 有 unique 约束）
- **问题描述**：读 max → 加一 → 插入三步不在任何锁/序列保护内，两个并发请求拿到相同 `max_seq` 时后者撞唯一约束，`session_scope` 回滚并抛 500；且每年 RFQ 全行加载进内存，数据量增长后单次创建成本 O(N)。
- **可能后果**：并发创建 RFQ 随机 500；年度数据量大后接口明显变慢。
- **推荐解决方案**：MVP 阶段即可用的轻量方案——`INSERT` 失败后捕获 IntegrityError 重算重试（≤3 次）；或改用 `rfq_number = f"RFQ-{year}-{uuid4().hex[:6].upper()}"` 类不可猜测编号；如需连续序号，建 `rfq_seq` 计数表行锁（`SELECT ... FOR UPDATE`）。
- **修改成本**：低
- **优先级**：P1
- **是否影响当前上线**：否（当前并发量低，属隐患）
- **是否需要重构**：否
- **验收标准**：并发 10 个 `POST /rfqs` 全部成功且编号唯一；单测模拟 IntegrityError 能自动重试成功。

### 问题 8：询价单/线索/审核状态机不严谨，存在跳态、死态与无守卫流转（严重）

- **所属模块**：api/routers/rfqs.py、api/routers/supplier_leads.py、api/routers/audit.py
- **严重程度**：严重
- **影响范围**：业务闭环正确性、演示数据可信度
- **发现依据**：
  - `rfqs.py:394-395`（报价时 `if r.status in ("sent", "draft"): r.status = "quoted"`——draft 可跳过 sent 直达 quoted）；
  - `rfqs.py:391-392`（`lk.status in ("sent", "viewed", "pending")` 可转 quoted——pending（未发送）即可报价）；
  - `api/routers/supplier_leads.py:103-105`（`lk.status in ("sent", "pending")` 可转 viewed——未发送即可"已查看"）；
  - `kb/models.py:518-519`（RFQ 声明 `closed|cancelled` 状态）vs 全部 router 无任何接口设置 closed/cancelled——死状态；
  - `supplier_leads.py:117-119`（declined 为终态，无重邀/复活路径）；
  - `api/routers/audit.py:72-103`（approve/reject 不检查当前 status，已审批项可被反复改写，`reviewed_at` 被覆盖）
- **问题描述**：状态流转规则散落在 if 语句里且与模型注释的状态定义不一致：可"未发送先报价/先查看"、RFQ 永远无法关闭、审核可重复盖章。
- **可能后果**：演示/客户数据出现逻辑矛盾（draft 单已有报价）；无法表达"已关闭"业务；审核结论被后一次操作无痕迹覆盖。
- **推荐解决方案**：用一张显式状态迁移表（dict: `{(from, event): to}`）统一收口 RFQ 与 Link 的状态推进，非法迁移返回 409；报价/查看前置条件收紧为 `lk.status in ("sent","viewed")`；补 `POST /rfqs/{id}/close`、`/cancel`；审核 approve/reject 前置校验 `status == "pending"`。
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：部分（报价跳态影响数据可信度）
- **是否需要重构**：是（轻量重构：抽状态机模块，不动架构）
- **验收标准**：pending 线索调 view/quote 返回 409/400；draft RFQ 无法变 quoted；closed/cancelled 有接口且 closed 后拒绝 send/quote；重复 approve 返回 409。

### 问题 9：公司访问控制默认全通，越权防护对白名单外用户形同虚设（中等）

- **所属模块**：kb/auth.py（被 api/deps.py 使用）
- **严重程度**：中等
- **影响范围**：所有 `check_company_access` 保护的接口
- **发现依据**：`kb/auth.py:227-241`（`cnt == 0: return True`——用户无白名单记录即可访问任意公司）；`api/deps.py:48-52`
- **问题描述**：`check_company_access` 的实际语义是"有白名单记录才隔离"，而当前部署中没有任何为用户 pre-seed 白名单的流程（`grant_company_access` 仅在 kb 内部定义），因此现实中的效果 ≈ 所有登录用户可访问所有公司数据。这使问题 2 的越权面进一步放大。
- **可能后果**：企业私域数据（驾驶舱、BOM、缺件、RFQ）对全部注册用户可见。
- **推荐解决方案**：注册/企业绑定流程中为该用户写入其所属企业的 `kb_company_access` 记录（把默认策略自然切换为白名单模式）；或在 `can_access_company` 增加"企业归属"默认规则（用户 company 字段 ↔ company_id 映射）。MVP 阶段保留公开供应商知识可读，但 RFQ/驾驶舱/缺件类接口应强制归属校验。
- **修改成本**：中
- **优先级**：P1
- **是否影响当前上线**：是（决定问题 2/演示数据的实际暴露面）
- **是否需要重构**：否
- **验收标准**：新注册用户 A 访问企业 B 的 `/companies/{B}/dashboard`、`/companies/{B}/rfqs` 返回 403；访问本企业返回 200；公开公司列表接口行为不变。

### 问题 10：会话 token 无过期、无登出（中等）

- **所属模块**：kb/auth.py、api/routers/auth.py
- **严重程度**：中等
- **影响范围**：账号安全
- **发现依据**：`kb/auth.py:52-60`（`KbSession` 只有 `created_at`，无 `expires_at`）；`api/routers/auth.py` 全文无 logout/revoke 端点；`kb/auth.py:186-215`（`resolve_token` 不校验时效）
- **问题描述**：token 一旦签发永久有效，无法注销、无法过期；泄露即永久失陷。
- **可能后果**：演示环境 token 泄露后长期可用；离职/换设备无法收回会话。
- **推荐解决方案**：`KbSession` 加 `expires_at`，`resolve_token` 校验时效；加 `POST /auth/logout` 删除当前 token 行。
- **修改成本**：低
- **优先级**：P1
- **是否影响当前上线**：否（MVP 可接受，但应在真实客户接入前完成）
- **是否需要重构**：否
- **验收标准**：过期 token 调 `/auth/me` 返回 401；logout 后原 token 立即失效。

### 问题 11：列表接口无分页，全量加载（中等）

- **所属模块**：api/routers/rfqs.py、companies.py、audit.py、supplier_leads.py、demo.py、enterprise_context.py
- **严重程度**：中等
- **影响范围**：接口性能与内存
- **发现依据**：`api/routers/rfqs.py:251`（`.all()`）、`companies.py:38`、`audit.py:68`、`supplier_leads.py:83`、`demo.py:184`、`enterprise_context.py:72`——均无 limit/offset/page 参数（仅 procure sessions 与 demo events 有 limit）
- **问题描述**：所有列表端点一次返回全表。
- **可能后果**：数据量到数千行后接口耗时与内存线性膨胀，前端首屏卡顿。
- **推荐解决方案**：统一 `page/page_size`（默认 20，上限 100）或 `limit/offset` 参数，响应 `{items,total,page,page_size}`；至少给 RFQ/审核队列/线索三张增长型表加分页。
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：上述端点接受 `page/page_size` 且默认截断；total 为全量计数。

### 问题 12：序列化层 N+1 查询（中等）

- **所属模块**：api/routers/enterprise_context.py、relationships.py、rfqs.py、supplier_leads.py
- **严重程度**：中等
- **影响范围**：列表类接口延迟
- **发现依据**：`enterprise_context.py:26-39,68-76`（`_build_context` 每公司 3 次 count 查询，列表页 = 3N+1）；`relationships.py:143-144`（每关系 2 次 `s.get(CompanyCache)`）；`rfqs.py:137-138,153-154`（`_link_dict`/`_quote_dict` 每行 1 次 get）；`supplier_leads.py:34-36`（每线索 2 次 get）
- **问题描述**：逐行 `s.get()` 补全名称字段。Session 一级缓存可缓解同对象重复，但不同供应商/买方仍是逐行一次查询。
- **可能后果**：线索/报价列表上百行时单接口数百次 SQL 往返。
- **推荐解决方案**：MVP 级方案——先查列表，收集 id 集合后用一次 `IN` 查询批量取 `CompanyCache`/`RfqRecord` 建 dict 再组装；驾驶舱列表用 3 条 `GROUP BY company_id` 聚合查询替代逐公司 count。
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：`GET /suppliers/{id}/leads`（100 条线索）SQL 次数 ≤ 5；`/enterprise-context/companies` SQL 次数与公司数无关（常数级）。

### 问题 13：响应格式与错误处理不统一，无 response_model、无全局异常处理（中等）

- **所属模块**：api/ 整体
- **严重程度**：中等
- **影响范围**：前端联调成本、API 文档（OpenAPI）可信度、错误可诊断性
- **发现依据**：`api/routers/rfqs.py:232-235`（`{"rfq": ..., "supplier_leads": [...]}`）vs `rfqs.py:252`（`{"items","total"}`）vs `procure.py:210`（`{"sessions","total","notice"}`）vs 死代码 `api/schemas.py:83-86`（`ApiResponse{ok,data,msg}`）；全部 router 无 `response_model=`；`api/main.py` 全文无 `exception_handler`，IntegrityError 等未捕获异常直接 500；Pydantic 校验失败为 FastAPI 默认 422 结构，与业务错误 `{detail}` 不一致
- **问题描述**：响应包装、分页字段、错误体三类格式并存；schema 不约束出参，文档与实际响应可能漂移。
- **推荐解决方案**：定义统一错误体 `{"code","message","detail"}` + 全局 `Exception`/`RequestValidationError` handler；列表响应统一 `{items,total,page,page_size}`；为核心写接口（rfqs/quotations）补 `response_model`。MVP 阶段不必上错误码平台，先固定 10 个以内业务错误码。
- **修改成本**：中
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：唯一约束冲突返回 409 + 统一错误体而非 500；校验失败与业务错误同构；`/docs` 中核心接口有明确响应 schema。

### 问题 14：嵌套会话与只读事务也 commit（中等）

- **所属模块**：api/deps.py、kb/db.py、api/routers/rfqs.py
- **严重程度**：中等
- **影响范围**：事务语义清晰度、连接占用
- **发现依据**：`api/routers/rfqs.py:272-274`（`send_rfq` 在 `session_scope` 内调用 `check_company_access`）；`api/deps.py:41-47`（该校验内部再开一个 `session_scope`）；`kb/auth.py:235-241`（`can_access_company` 再开一个）——单请求最多 3 个会话；`kb/db.py:49-60`（`session_scope` 无论读写，退出即 `session.commit()`）
- **问题描述**：鉴权/访问校验与业务写操作分属不同事务，校验通过与写入提交之间无一致性保证（MVP 可接受但需知晓）；只读 GET 也执行一次 commit 产生多余 round-trip。
- **可能后果**：高并发下连接占用放大；将来若在校验后、提交前插入跨表一致性要求会踩坑。
- **推荐解决方案**：`check_company_access` 增加可选 `session` 参数复用外层会话；`kb/db.py` 增加只读 `query_scope()`（不 commit）。
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：`send_rfq` 全流程单会话单事务；只读端点无 commit 日志。

### 问题 15：应用启动即建表，import 即副作用，且无迁移机制（中等）

- **所属模块**：api/main.py、kb/db.py
- **严重程度**：中等
- **影响范围**：部署可靠性、schema 演进
- **发现依据**：`api/main.py:52-54`（`create_app` 内执行 `init_db()` → `Base.metadata.create_all`）；`api/main.py:102`（模块级 `main = create_app()`，import api.main 即触库）；`api/requirements.txt` 无 alembic；`tests/*` 多处 `from api.main import create_app` 意味着跑测试也会连真实库建表
- **问题描述**：启动与建表耦合：数据库不可用时应用无法启动；`create_all` 只增不改，列变更无迁移路径；任何 `import api.main`（测试、工具脚本）都产生数据库副作用。
- **可能后果**：改列/改索引需手工 DDL，环境间 schema 漂移；DB 抖动导致服务起不来。
- **推荐解决方案**：建表移到独立命令（`python -m scripts.init_db` 或 uvicorn startup event 且失败可降级）；MVP 阶段至少建立 `migrations/` SQL 版本目录（database/ 已有类似实践可复用），后续再视需要引入 Alembic。
- **修改成本**：中
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：DB 宕机时 `/api/v1/health` 仍可响应（或明确降级）；`import api.main` 无 DB 连接；schema 变更走版本化脚本。

### 问题 16：业务规则硬编码在 router 层，缺 service 层（中等）

- **所属模块**：api/routers/rfqs.py、audit.py、supplier_leads.py
- **严重程度**：中等
- **影响范围**：可测试性、规则复用（demo 与正式双轨重复实现的风险）
- **发现依据**：`rfqs.py:397-402`（报价异常阈值 1.5 倍硬编码）、`rfqs.py:296-315`（审核项生成规则）、`rfqs.py:285-294`（状态推进）均在 router 函数体内；对照 `dashboard.py:31-104`/`demo.py` 委托 `kb/dashboard_calc.py`/`kb/demo_calc.py` 的薄路由风格；`kb/demo_calc.py`（2374 行）与 rfqs 存在平行实现的报价/审核逻辑
- **问题描述**：同一业务域两套实现路径（正式表走 router 内联逻辑、演示表走 demo_calc），规则已开始分叉。
- **推荐解决方案**：把 RFQ 状态机、异常判定、审核项生成抽成 `api/services/rfq_service.py`（或 `kb/rfq_calc.py` 与现有风格一致），router 只做参数解析与调用；demo 与正式共用同一规则函数。
- **修改成本**：中
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：是（轻量提炼，不动数据模型）
- **验收标准**：报价异常规则单测不经过 HTTP 层即可运行；demo 与正式路径断言同一阈值常量。

### 问题 17：db_init.py 与三套 ORM 模型互不一致（中等）

- **所属模块**：api/db_init.py、api/models.py、api/models/__init__.py、ai/tools/mysql_client.py
- **严重程度**：中等
- **影响范围**：数据层认知一致性、未来切库风险
- **发现依据**：`api/db_init.py:57-79`（DDL 建 `suppliers`：category/brand_coverage/moq/lead_time_weeks/rating…）；`api/models.py:41-58`（ORM `Supplier`：region/categories/brands/match_score…，String 主键）；`api/models/__init__.py:130-144`（另一 ORM `Supplier`：company_id FK/Enum status…，BigInt 主键）；`ai/tools/mysql_client.py:127,167`（裸 SQL `FROM suppliers s`，实际消费的是 db_init 的表结构）
- **问题描述**：同一个 `suppliers` 表存在三份互不匹配的 schema 定义；两份 ORM 都无法正确映射线上真实表；`material_dictionary` 只有 DDL 无 ORM。
- **可能后果**：若有人启用任一 ORM 访问 suppliers，查询即报列不存在；新人无法判断哪份是真相。
- **推荐解决方案**：随问题 4 删除死 ORM；保留 db_init DDL 为 suppliers 唯一真相（或反向生成一份活的只读 ORM 供查询）；在 `database/` 文档中登记表归属（ai 工具层 vs kb 层）。
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：每张飞 kb 表在项目中有且仅有一份 schema 定义来源；文档可查。

### 问题 18：demo 路由组未按环境隔离，任意登录用户可重置/写演示沙盘（轻微）

- **所属模块**：api/routers/demo.py、api/main.py
- **严重程度**：轻微
- **影响范围**：演示数据稳定性、生产暴露面
- **发现依据**：`api/main.py:93`（无条件注册 demo.router）；`demo.py:239-245`（`reset_scenario` 仅要求登录）；`demo.py:252-335`（全部动作仅 `_require_primary` 校验 company_id 属于 6 家演示企业，不校验用户与该企业的归属/角色）
- **问题描述**：任何注册用户都能重置演示场景、为 9001-9006 企业生成订单/RFQ/报价。虽然只写 `demo_*` 表（`demo.py:24` 注释），但演示环境被路人清空会直接影响售前演示。
- **推荐解决方案**：demo 路由组按环境变量（如 `KB_DEMO_MODE=true`）整体挂载，生产不注册；或对 demo 动作加 `require_admin`/演示账号白名单。
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：视部署形态而定（公网演示环境=是）
- **是否需要重构**：否
- **验收标准**：`APP_ENV=production` 时 `/api/v1/demo/*` 全部 404；非演示账号调 reset 返回 403。

### 问题 19：关键数值字段缺少边界校验（轻微）

- **所属模块**：api/routers/rfqs.py、auth.py、chat.py
- **严重程度**：轻微
- **影响范围**：数据质量
- **发现依据**：`rfqs.py:47`（`quantity: int = 1` 无 `ge=1`）；`rfqs.py:71`（`unit_price: float` 无 `gt=0`，依赖 `rfqs.py:397-402` 事后审核而非拒收）；`rfqs.py:44`（`title` 无长度上限）；`api/routers/auth.py:16-18`（`password` 无最小长度）；`api/routers/chat.py:16`（`query` 无 `min_length=1`）
- **问题描述**：负数数量、0/负单价、空标题、1 位密码均可落库。
- **推荐解决方案**：补 `Field(ge=1)`/`Field(gt=0)`/`Field(min_length=..., max_length=...)`；单价 ≤0 直接 422 而非入库后再审。
- **修改成本**：低
- **优先级**：P2
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：`quantity=0`、`unit_price=-1`、`password="123"` 分别返回 422。

### 问题 20：datetime.utcnow() 弃用且全链路无时区（轻微）

- **所属模块**：api/routers/rfqs.py、supplier_leads.py、audit.py、kb/auth.py
- **严重程度**：轻微
- **影响范围**：时间字段一致性、Python 3.12+ 兼容
- **发现依据**：`rfqs.py:102,283`、`supplier_leads.py:105`、`audit.py:82,99`、`kb/auth.py:49,60`（`datetime.utcnow`，Python 3.12 起 DeprecationWarning）
- **问题描述**：全链路 naive datetime，跨时区部署/展示时会含糊；新版本解释器告警。
- **推荐解决方案**：统一 `datetime.now(timezone.utc)`，序列化保持 ISO8601 带 Z。
- **修改成本**：低
- **优先级**：P3
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：代码库无 `utcnow()` 调用；API 返回时间带时区标记。

### 问题 21：登录/注册响应与真实会话角色不一致（轻微）

- **所属模块**：api/routers/auth.py
- **严重程度**：轻微
- **影响范围**：前端角色展示正确性
- **发现依据**：`api/routers/auth.py:39`（login 硬编码 `{"name": "user", "role": "user"}`，真实管理员登录也返回 user）；`api/routers/auth.py:48`（register 回显 `req.role` 而非落库值）
- **问题描述**：响应体角色与 `resolve_token` 会话角色可能不一致，前端据此渲染权限界面会失真。
- **推荐解决方案**：login 从 `KbUser` 读取真实 name/role 返回；register 同理。
- **修改成本**：低
- **优先级**：P3
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：admin 登录响应 `role="admin"`；普通用户为 `user`。

### 问题 22：kb_admin 后台任务管理粗糙（轻微）

- **所属模块**：api/routers/kb_admin.py
- **严重程度**：轻微
- **影响范围**：管理端可观测性
- **发现依据**：`kb_admin.py:31,75`（调用私有函数 `kb_tasks._update_task`）；`kb_admin.py:99-102`（`cancel_task` 无论成功与否都返回 cancelled）；`kb_admin.py:43-51`（重复点击 generate 会并行启动多个全量任务，无去重/互斥）
- **推荐解决方案**：`_update_task` 提为公开 API；cancel 返回真实状态；generate 启动前检查是否已有 running 任务，有则 409。
- **修改成本**：低
- **优先级**：P3
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：任务运行中再次 POST /generate 返回 409；cancel 响应反映真实状态。

### 问题 23：路由风格不一致 + 健康检查重复（轻微）

- **所属模块**：api/main.py、api/routers/*
- **严重程度**：轻微
- **影响范围**：API 表面整洁度
- **发现依据**：`api/main.py:95-97`（`/api/v1/health`）vs `api/routers/procure.py:187-196`（`/api/v1/procure/health`）vs 死代码 `api/routes/health.py:5`（`/api/health`）；前缀风格混用：companies/relationships 共享 `/companies` 前缀，dashboard/demo/rfqs 空前缀+全路径，auth 自带前缀
- **推荐解决方案**：保留一个聚合 `/health`（可含 db/llm 子项检查）；统一 router 前缀声明风格。
- **修改成本**：低
- **优先级**：P3
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：健康检查入口唯一；新路由按统一约定注册。

### 问题 24：CORS 配置过宽（轻微）

- **所属模块**：api/main.py
- **严重程度**：轻微
- **影响范围**：浏览器侧安全面
- **发现依据**：`api/main.py:42-48`（`allow_methods=["*"]`、`allow_headers=["*"]`、`allow_credentials=True`）
- **问题描述**：凭据模式下全方法全头放开，MVP 本地可接受，上线应收紧到实际使用的方法与头。
- **推荐解决方案**：上线前收敛为 `["GET","POST","DELETE"]` + `["Authorization","Content-Type"]`，origins 由环境变量精确配置（当前已支持）。
- **修改成本**：低
- **优先级**：P3
- **是否影响当前上线**：否
- **是否需要重构**：否
- **验收标准**：预检请求返回的 allow-methods/headers 为显式列表。

---

## 3. 事实与推断标注汇总

| # | 判断 | 标注 |
|---|------|------|
| 1 | `api/main.py` 只注册 `api/routers/*`，`api/routes/*` 及配套 9 个文件为死代码 | 【已确认事实】（main.py:56-93 + 全项目引用检索） |
| 2 | 注册接口传 `role="admin"` 可获得管理员权限 | 【已确认事实】（routers/auth.py:21-27,45 → kb/auth.py:140-160 → deps.py:23-29，代码路径闭合） |
| 3 | `GET /rfqs`、`GET /rfqs/{id}`、`GET /rfqs/{id}/quotations`、`GET /rfqs/{id}/quote-comparison` 无公司访问校验 | 【已确认事实】（rfqs.py:238-252,255-266,421-436,439-470） |
| 4 | procure 路由组无鉴权、user_id 客户端自报、会话任意读删 | 【已确认事实】（procure.py:47,68-71,82,201-232） |
| 5 | `api/models/` 包遮蔽 `api/models.py`；`api/database.py:30` 导入 AuditRecord 必然失败 | 【已确认事实】（实测 import 解析到包 `__init__.py`；包内无 AuditRecord） |
| 6 | 无循环依赖（kb/、ai/ 不反向引用 api/） | 【已确认事实】（grep 无匹配） |
| 7 | 报价无唯一约束可重复提交、编号生成有竞态、状态机可跳态、审核可重复审批 | 【已确认事实】（代码级缺陷存在性确认；线上是否已触发【尚未验证】） |
| 8 | `can_access_company` 默认公开导致 check_company_access 对现状部署近乎失效 | 【合理推断】（默认放行逻辑【已确认事实】kb/auth.py:236-238；"线上没有任何用户被配白名单"依赖部署数据，【尚未验证】） |
| 9 | db_init.py 的 suppliers DDL 是 ai 工具层实际消费的表结构 | 【合理推断】（ai/tools/mysql_client.py:127,167 裸 SQL 列名与 DDL 吻合；未连库核对真实表结构，【尚未验证】） |
| 10 | demo 接口组在"生产"环境的暴露面 | 【尚未验证】（取决于部署时 APP_ENV/KB_DEMO_MODE 及是否公网；`.env` 属敏感文件未读取） |
| 11 | 并发撞 RFQ 号/重复提交在实际运营中已发生 | 【尚未验证】（代码路径确认，未查库中是否有重复数据；backend.log 未逐一分析） |
| 12 | 前端是否已对所有列表做了客户端分页/防双击 | 【缺少材料】（本分工不覆盖 web/，前端缓解措施不影响后端缺陷成立） |

## 4. 领域评分

### 评分一：架构与代码组织 —— 4.5 / 10

依据：
- 加分：依赖方向清晰无循环（api → kb/ai 单向）；dashboard/demo 薄路由 + 计算层下沉的范式正确；鉴权模块在 P0 修复后（无硬编码 token、bcrypt 渐进迁移、`kb/auth.py:1-18`）基线健康。
- 扣分：约半数 `api/` 代码为死代码且仍在被测试引用（问题 4、5）；三套 ORM Base、三份 suppliers schema、两套 get_current_user 并存；业务规则内联 router 且与 demo 轨道开始分叉（问题 16、17）；启动即建表无迁移（问题 15）。这些问题每日都在产生真实维护成本（已有"给死代码修 bug"的记录）。

### 评分二：API 设计与安全 —— 3.5 / 10

依据：
- 加分：核心闭环接口真实可用且落库；路径语义基本 RESTful；关系协同问答（relationships.py:199-244）有服务端关系校验，说明团队具备正确的安全意识；错误处理大体使用 HTTPException。
- 扣分：存在一个致命自助提权（问题 1）+ 两组严重越权（问题 2、3）——任何一项在公网即数据事故；写接口无幂等（问题 6）、状态机可跳态（问题 8）、访问控制默认全通（问题 9）；无分页/无 response_model/无统一错误格式（问题 11、13）。安全与规范性距离"可对外试商用"差一个集中的 P0/P1 修复迭代。

> 总体判断：当前后端处于"功能能跑通演示、安全与工程卫生未达标"的原型阶段。建议优先闭环问题 1-3（P0，合计约 1-2 天工作量），随后以问题 4-9 做一次针对性的清理迭代，即可支撑 MVP 对外试用；无需引入更重的架构方案。
