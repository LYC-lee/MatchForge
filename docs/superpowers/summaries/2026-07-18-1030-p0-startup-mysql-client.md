# P0-04 修复总结报告

**日期**: 2026-07-18  
**修复人**: Hermes Agent  
**项目**: LYC-lee/MatchForge  
**关联 Issue**: #43  

---

## 🎯 验收结果（2026-07-18 16:30 实测 - 含 3 点建议修复后）

| 验收项 | 标准 | 实测结果 | 状态 |
|--------|------|---------|------|
| 导入验证 | `from api.main import main` 通过 | 输出 `FastAPI`，无报错 | ✅ 通过 |
| 启动验证 | `/api/v1/health` 返回 200 | `{"status":"ok"}` HTTP 200 | ✅ 通过 |
| 核心查询 | `filter_suppliers_raw('MLCC')` 不报列不存在错误 | **返回 1 条供应商，走 JOIN 不降级** | ✅ 通过 |
| 字段验证 | SQL 不含 `s.category`/`s.brand_coverage`/`s.moq`/`s.lead_time_weeks`/`s.data_source` | 3/3 单元测试通过 | ✅ 通过 |
| 单元测试 | `test_mysql_client_schema.py` 全部通过 | 3/3 通过 | ✅ 通过 |
| .env 配置 | `.env.example` 密码预填 | MySQL/Neo4j/PostgreSQL/Redis 密码均为 `matchforge123` | ✅ 通过 |
| **supplier_capabilities 表** | 表存在，JOIN 查询正常 | **表已创建，1 条测试数据，查询返回品类/品牌/MOQ/交期** | ✅ 通过 |
| **api/routes/ 清理** | 死代码目录已删除 | **已删除，备份到 docs/archive/** | ✅ 通过 |
| **ORM id 类型统一** | 所有模型 id 为 BigInteger | **User/Supplier/RFQ/Lead/AuditRecord 全部 BigInteger** | ✅ 通过 |

---

## 📋 修复概览

| 任务 | 状态 | 验收标准 | 测试结果 |
|------|------|---------|---------|
| A1: 启动命令校准 | ✅ 完成 | `uvicorn api.main:main` 统一 | 文档已校准 |
| A2: 依赖管理 | ✅ 完成 | `pip install -r requirements.txt` 后 import 通过 | requirements.txt 新建 |
| A3: 环境配置 | ✅ 完成 | `.env.example` 复制后不因空密码崩溃 | 密码预填 matchforge123 |
| A4: 数据库查询修复 | ✅ 完成 | `filter_suppliers_raw('MLCC')` 不报列不存在错误 | ✅ 3/3 测试通过 |
| **建议1: 创建 supplier_capabilities 表** | ✅ 完成 | JOIN 查询不降级 | ✅ 返回 1 条供应商 |
| **建议2: 清理 api/routes/ 死代码** | ✅ 完成 | 死代码已删除 | ✅ 导入验证通过 |
| **建议3: 统一 Supplier.id 类型** | ✅ 完成 | 所有模型 id 为 BigInteger | ✅ 5 个模型全部修复 |

---

## A1: 启动命令校准

### 问题
- 2 份文档使用错误的启动命令 `uvicorn api.main:app`（实际入口是 `main`，不是 `app`）
- README.md 没有启动说明

### 修复
| 文件 | 修改 |
|------|------|
| `docs/.../2026-07-16-1736-demo-scenario-integration-summary.md` | `api.main:app` -> `api.main:main` |
| `docs/.../2026-07-16-2020-demo-state-merge-dashboard-summary.md` | `api.main:app` -> `api.main:main` |
| `README.md` | 新增完整快速启动说明（Docker->.env->pip install->uvicorn->前端） |

---

## A2: 依赖管理

### 问题
- `requirements.txt` **不存在**（空文件被删除）
- 所有运行依赖（fastapi/sqlalchemy/pymysql/langchain/openai/pymilvus 等）都没有声明
- `requirements-dev.txt` 只有 pytest，缺少运行依赖

### 修复
| 文件 | 修改 |
|------|------|
| `requirements.txt` | **新建**，20+ 运行依赖 |
| `requirements-dev.txt` | 改为 `-r requirements.txt` + pytest/ragas |

---

## A3: 环境配置

### 问题
- `.env.example` 中 MySQL/Neo4j/PostgreSQL/Redis 密码全为空
- `KB_DATABASE_URL` 注释掉了，密码也是空的
- 缺少 MinerU/Reranker 配置

### 修复
| 配置项 | 修改前 | 修改后 |
|--------|--------|--------|
| `MYSQL_PASSWORD` | (空) | `matchforge123` |
| `KB_DATABASE_URL` | 注释掉，密码空 | 启用，密码 `matchforge123` |
| `NEO4J_PASSWORD` | (空) | `matchforge123` |
| `POSTGRES_PASSWORD` | (空) | `matchforge123` |
| `REDIS_PASSWORD` | (空) | `matchforge123` |
| `MINERU_API_URL` | (缺失) | 预填 |
| `RERANKER_MODEL` | (缺失) | 预填 |

---

## A4: 数据库查询修复（核心）

### 问题
`mysql_client.py` 的 `filter_suppliers_raw` 查询了 5 个**在真实表中不存在的列**：

| 死字段 | 真实位置 |
|--------|---------|
| `s.category` | `supplier_capabilities.category_name` |
| `s.brand_coverage` | `supplier_capabilities.brand_names` |
| `s.moq` | `supplier_capabilities.moq` |
| `s.lead_time_weeks` | `supplier_capabilities.lead_time_days` |
| `s.data_source` | `suppliers.source_name` 或 `supplier_capabilities.source_name` |

### 修复内容

#### 1. `ai/tools/mysql_client.py` - 完全重写
- `filter_suppliers_raw`: 改为 `LEFT JOIN supplier_capabilities` 查询
- 字段映射: `sc.category_name` / `sc.brand_names` / `sc.moq` / `sc.lead_time_days`
- 新增**降级机制**: `supplier_capabilities` 表不存在时自动降级
- 保持参数化 SQL，不退化

#### 2. `api/models.py` - ORM 重写
- Supplier: 移除 9 个死字段，与真实 DDL 对齐
- 所有模型 id: `String(12) UUID` -> `BigInteger autoincrement`
- 移除 `_uuid()` 函数

#### 3. `ai/agents/match.py` - 适配新 schema
- 品牌取值: `brand_names`（逗号分隔字符串）优先
- 品类取值: `category_name` 优先
- 交期取值: `lead_time_days` 优先，自动转换为周

---

## 🔧 3 点建议修复

### 建议 1: 创建 supplier_capabilities 表 ✅

**问题**: matchforge 库中不存在 `supplier_capabilities` 表，导致 `filter_suppliers_raw` 降级查询。

**修复**:
- 新建 `database/migrations/08_supplier_capabilities.sql` DDL 文件
- 在 matchforge 库中执行创建表
- 插入测试数据: `supplier_id=1, category_name='MLCC', brand_names='Murata,YAGEO,Samsung EM', moq=5000, lead_time_days=14`

**验证结果**:
```
查询成功: 返回 1 条供应商
  - 深圳华强电子科技有限公司 | 品类=MLCC | 品牌=Murata,YAGEO,Samsung EM | MOQ=5000 | 交期=14天
```
✅ JOIN 查询正常工作，不再降级

### 建议 2: 清理 api/routes/ 死代码目录 ✅

**问题**: `api/routes/` 整个目录（9 个文件）未在 `main.py` 中注册，是死代码。

**修复**:
- 备份到 `docs/archive/api_routes_deprecated/`
- 删除 `api/routes/` 目录
- 验证 `from api.main import main` 仍正常

**验证结果**: ✅ 导入验证通过，无影响

### 建议 3: 统一 Supplier.id 类型 ✅

**问题**: DDL 是 `BIGINT AUTO_INCREMENT`，但 ORM 用 `String(12)` UUID。

**修复**: `api/models.py` 中所有 5 个模型统一为 `BigInteger autoincrement`:

| 模型 | 修改前 | 修改后 |
|------|--------|--------|
| `User.id` | `String(12), default=_uuid` | `BigInteger, autoincrement=True` |
| `Supplier.id` | 已修复 (A4) | `BigInteger, autoincrement=True` |
| `RFQ.id` | `String(12), default=_uuid` | `BigInteger, autoincrement=True` |
| `RFQ.buyer_id` | `String(12), ForeignKey` | `BigInteger, ForeignKey` |
| `Lead.id` | `String(12), default=_uuid` | `BigInteger, autoincrement=True` |
| `Lead.rfq_id` | `String(12), ForeignKey` | `BigInteger, ForeignKey` |
| `Lead.supplier_id` | `String(12), ForeignKey` | `BigInteger, ForeignKey` |
| `AuditRecord.id` | `String(12), default=_uuid` | `BigInteger, autoincrement=True` |
| `AuditRecord.target_id` | `String(12)` | `BigInteger` |
| `AuditRecord.operator_id` | `String(12)` | `BigInteger` |

同时移除了 `_uuid()` 函数和 `import uuid`。

**验证结果**: ✅ 导入验证通过

---

## ✅ 最终测试结果

```
--- 1. 导入验证 ---
OK: FastAPI

--- 2. 单元测试 ---
  ✓ test_filter_suppliers_no_dead_fields
  ✓ test_filter_suppliers_raw_with_brands
  ✓ test_filter_suppliers_raw_returns_list
结果: 3 通过, 0 失败

--- 3. MLCC 查询（走 JOIN 不降级）---
查询成功: 返回 1 条供应商
  - 深圳华强电子科技有限公司 | 品类=MLCC | 品牌=Murata,YAGEO,Samsung EM | MOQ=5000 | 交期=14天

--- 4. supplier_capabilities 表 ---
COUNT(*): 1

--- 5. api/routes/ 已删除 ---
(目录不存在)

--- 6. models.py 中所有 id 都是 BigInteger ---
id = Column(BigInteger, primary_key=True, autoincrement=True)  ×5 个模型
```

---

## 📦 修改文件清单（最终版）

| 文件 | 操作 | 说明 |
|------|------|------|
| `README.md` | 修改 | 新增快速启动说明 |
| `requirements.txt` | 新建 | 20+ 运行依赖 |
| `requirements-dev.txt` | 修改 | 基于 requirements.txt + 测试依赖 |
| `.env.example` | 修改 | 密码预填 + MinerU/Reranker 配置 |
| `ai/tools/mysql_client.py` | 重写 | JOIN supplier_capabilities + 降级机制 |
| `api/models.py` | 重写 | 所有 ORM 与真实 DDL 对齐，id 统一 BigInteger |
| `ai/agents/match.py` | 修改 | 适配新 schema 字段名 |
| `tests/test_mysql_client_schema.py` | 新建 | 3 个测试用例 |
| `tests/verify_mlcc_query.py` | 新建 | 真实数据库验证脚本 |
| `tests/verify_import.py` | 新建 | 导入验证脚本 |
| `database/migrations/08_supplier_capabilities.sql` | **新建** | supplier_capabilities 表 DDL |
| `docs/archive/api_routes_deprecated/` | **新建** | 旧 routes/ 目录备份 |
| `api/routes/` | **删除** | 死代码目录已清理 |
| 2 份 docs summary | 修改 | 启动命令修正 |

---

## ⚠️ 后续建议

1. **前端适配**: 如果前端依赖 `categories`/`brands`/`moq` 等字段，需要改为从 `supplier_capabilities` 获取
2. **补充供应商测试数据**: 当前只有 1 条测试数据，建议导入真实供应商数据
3. **supplier_capabilities 种子数据**: 建议为每个供应商创建对应的能力记录
