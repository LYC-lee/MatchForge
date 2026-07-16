# Schema 收敛决策文档

> **负责人**: 数据负责人 (P4)
> **日期**: 2026-07-15
> **状态**: 已决策，作为后端 ORM 和迁移依据

---

## 1. 背景

当前项目存在两个 MySQL schema：

| Schema | 来源 | 表数量 | 定位 |
|--------|------|--------|------|
| `matchforge` | `data/mysql_schema.sql` | 10 张表 | 运营库：用户、认证、询价、线索 |
| `pc_industry` | `database/01_schema/01_core_tables_ddl.sql` | 13 张表 | 产业链事实库：公司、物料、替代关系、供应商能力、RFQ、报价 |

后端 FastAPI 不能在未决策的情况下直接建 ORM，必须先明确数据源边界。

---

## 2. 决策：MVP 第一阶段双库并存

**结论：MVP 第一阶段保留双库，后端通过双 engine/session 访问。**

### 职责边界

| Schema | 职责 | 读写模式 |
|--------|------|---------|
| `matchforge` | 用户认证、会话管理、采购方/供应商账号、线索运营状态 | 读写（认证写入，线索读写） |
| `pc_industry` | 公司、物料、品类、替代关系、供应商能力、RFQ、报价、数据来源 | 读写（事实数据读写） |

### 理由

1. `matchforge` 面向运营流程（谁登录、谁发起 RFQ、线索分给谁），`pc_industry` 面向产业链事实（什么物料、谁生产、能替代什么）。
2. 两者关注点不同，合并会造成表数量膨胀且职责模糊。
3. 双 engine 在 SQLAlchemy 中天然支持，成本可控。
4. 后续如需合并，可通过数据库视图或迁移脚本完成，不影响业务层。

---

## 3. 跨库关联键

后端 ORM 通过以下关联键跨库引用（均为 INT 类型，无物理外键）：

| matchforge 表 | 字段 | pc_industry 表 | 字段 | 说明 |
|---------------|------|----------------|------|------|
| `suppliers` | `id` | `suppliers` | `id` | 供应商主体（两库各有一张 suppliers 表，通过 enterprise_id/company_id 关联） |
| `rfqs` | `id` | `rfqs` | `id` | 询价单（matchforge 存运营状态，pc_industry 存事实数据） |
| `users.enterprise_id` | `enterprise_id` | `companies.id` | `id` | 用户所属企业对应产业链公司 |
| `leads.supplier_id` | `supplier_id` | `suppliers.id` | `id` | 线索指向的供应商 |
| `leads.rfq_id` | `rfq_id` | `rfqs.id` | `id` | 线索关联的询价单 |

### 关联策略

- **不建物理外键**：跨库无法建外键约束，应用层负责一致性。
- **ID 对齐**：两库的同名表（如 `suppliers`、`rfqs`）保持 ID 一致，由后端 service 层保证。
- **读取顺序**：先从 `matchforge` 获取用户/运营状态，再从 `pc_industry` 获取事实数据。

---

## 4. 审核模型

**决策：MVP 第一版复用 `pc_industry.supplier_capabilities.audit_status`。**

| 方案 | 说明 | MVP 采用 |
|------|------|---------|
| 复用 `supplier_capabilities.audit_status` | 供应商能力审核状态直接承载审核流 | ✅ |
| 新建 `audit_items` 通用审核队列表 | 支持替代料、供应商、报价等多类型审核 | ❌ 后续 |

### 审核字段映射

| 审核操作 | pc_industry 字段 | 值 |
|---------|-----------------|-----|
| 待审核 | `supplier_capabilities.audit_status` | `pending` |
| 通过 | `supplier_capabilities.audit_status` | `verified` |
| 驳回 | `supplier_capabilities.audit_status` | `rejected` |
| 审核备注 | `supplier_capabilities.audit_note` | 文本 |
| 替代料审核 | `part_alternatives.review_status` | `pending`/`approved`/`rejected` |

---

## 5. 后端 ORM 指引

### 双 engine 配置

```python
# api/app/db/session.py
# matchforge engine - 运营库
matchforge_engine = create_engine(MATCHFORGE_DATABASE_URL)
MatchforgeSession = sessionmaker(bind=matchforge_engine)

# pc_industry engine - 产业链事实库
pc_industry_engine = create_engine(PC_INDUSTRY_DATABASE_URL)
PcIndustrySession = sessionmaker(bind=pc_industry_engine)
```

### ORM 模型分配

| ORM 模型 | Schema | 表 | 用途 |
|---------|--------|-----|------|
| `User` | matchforge | `users` | 认证、角色 |
| `Enterprise` | matchforge | `enterprises` | 企业主体 |
| `Buyer` | matchforge | `buyers` | 采购档案 |
| `Supplier` (运营) | matchforge | `suppliers` | 供应商运营状态 |
| `Qualification` | matchforge | `qualifications` | 资质证照 |
| `Category` (运营) | matchforge | `categories` | 品类（运营侧） |
| `Product` | matchforge | `products` | 供应商产品（运营侧） |
| `MaterialDictionary` | matchforge | `material_dictionary` | 标准字典 |
| `RFQ` (运营) | matchforge | `rfqs` | 询价单运营状态 |
| `Lead` | matchforge | `leads` | 线索 |
| `Company` | pc_industry | `companies` | 产业链公司 |
| `IndustrySegment` | pc_industry | `industry_segments` | 产业环节 |
| `CompanySegment` | pc_industry | `company_segments` | 公司-环节关系 |
| `Category` (事实) | pc_industry | `categories` | 物料品类 |
| `Part` | pc_industry | `parts` | 物料主数据 |
| `SpecDefinition` | pc_industry | `spec_definitions` | 规格字段定义 |
| `Supplier` (事实) | pc_industry | `suppliers` | 供应商事实 |
| `SupplierCapability` | pc_industry | `supplier_capabilities` | 供应商能力 |
| `PartAlternative` | pc_industry | `part_alternatives` | 替代料关系 |
| `RFQ` (事实) | pc_industry | `rfqs` | 询价单事实 |
| `RfqSupplier` | pc_industry | `rfq_suppliers` | RFQ-供应商关联 |
| `Quotation` | pc_industry | `quotations` | 报价记录 |
| `DataSource` | pc_industry | `data_sources` | 数据来源 |

---

## 6. Docker MySQL 初始化

docker-compose.yml 已挂载 `./docker/mysql/init` 到 `/docker-entrypoint-initdb.d`。

| 文件 | 作用 | 对应 Schema |
|------|------|------------|
| `01_matchforge_schema.sql` | 建库建表 | matchforge |
| `02_pc_industry_schema.sql` | 建库建表 | pc_industry |

MySQL 容器首次启动时自动执行，按文件名顺序运行。

---

## 7. 种子数据初始化

| 命令 | 作用 | 目标 |
|------|------|------|
| `python data/init_all.py` | 初始化 matchforge + Neo4j + Milvus | matchforge schema |
| `python scripts/import_pc_industry_seed.py` | 导入 pc_industry CSV 种子数据 | pc_industry schema |

两个命令均可重复执行（幂等设计）。

---

## 8. 后续合并方向（MVP 后）

1. 如双库维护成本上升，可将 `pc_industry` 的运营相关表（rfqs、rfq_suppliers、quotations）迁移到 `matchforge`。
2. 合并后通过 Alembic 迁移脚本完成数据搬迁。
3. `pc_industry` 保留为只读产业链事实库（公司、物料、替代关系、供应商能力）。

---

## 9. 环境变量

```env
# matchforge 运营库
MATCHFORGE_DATABASE_URL=mysql+pymysql://matchforge:matchforge123@127.0.0.1:3306/matchforge

# pc_industry 产业链事实库
PC_INDUSTRY_DATABASE_URL=mysql+pymysql://matchforge:matchforge123@127.0.0.1:3306/pc_industry

# Neo4j
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=matchforge123

# Milvus
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530

# Redis
REDIS_URL=redis://:matchforge123@127.0.0.1:6379/0
```
