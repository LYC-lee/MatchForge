# MatchForge P4 数据层 - 种子数据与知识库

> **负责人**: P4 (数据/知识库工程师)
> **阶段**: Phase 0 - 2天Spike
> **生成日期**: 2026-07-14
> **最后更新**: 2026-07-14（v1.4）
> **运行环境**: Windows + Docker Desktop + Python 3.11+
> **文档版本**: v1.4（对齐系统架构文档 v1.2 + PRD v2.0）

> ⚠️ **凭据对齐说明（2026-07-15）**：本文档原引用早期独立环境的容器名/凭据（`ecs-mysql`/`root`/`123456`、Neo4j `root1234`、phpMyAdmin:8080），已全文改写为对齐 [`deploy/docker-compose.yml`](../deploy/docker-compose.yml) 的权威配置：容器名 `matchforge-mysql` / `matchforge-neo4j` 等，统一密码 `matchforge123`（MySQL 用户 `matchforge`、Neo4j 用户 `neo4j`、MinIO `minioadmin`/`minioadmin123`、Redis 密码 `matchforge123`）。
> 实际连接以根目录 `.env`（对齐 docker-compose）为准；`matchforge` 库由 docker-compose 自动创建，故 `mysql_schema.sql` 不再 `CREATE DATABASE`，`matchforge` 用户（仅持 `matchforge.*` 权限）可直接加载本脚本与导入种子数据。
> 产业链全链路库 `pc_industry`（13 表）见 [`../database/`](../database/README.md)，与本 `matchforge` 库并存，收敛方案见 [database/06_handoff/01_retrospective.md](../database/06_handoff/01_retrospective.md)。

## 目录架构

```
MatchForge/
├── .env.example                    # 环境变量模板
├── .gitignore
└── data/
    ├── README.md                   # 本文件
    ├── mysql_schema.sql            # MySQL 建表脚本（10张表）
    ├── init_all.py                 # 一键初始化入口
    ├── view_all_data.py            # 数据查看脚本（Python）
    ├── view_all_data.ps1           # 数据查看脚本（PowerShell）
    ├── suppliers/                  # 种子供应商（JSON -> MySQL + Milvus）
    │   ├── suppliers.json          #   35家供应商 + 119条产品（中文）
    │   └── import_to_mysql.py      #   JSON -> MySQL 导入脚本（含资质独立表）
    ├── alternatives/               # 替代料交叉引用（JSON -> Neo4j）
    │   ├── alternatives.json       #   30组 + 131条替代关系（含L1-L5等级）
    │   └── import_to_neo4j.py      #   JSON -> Neo4j 导入脚本（含level属性）
    ├── dictionary/                 # 标准字典（JSON -> MySQL）
    │   ├── dictionary.json         #   81条标准编码（中文）
    │   └── import_to_mysql.py      #   JSON -> MySQL 导入脚本
    ├── milvus_collections.py       # Milvus 集合创建 + 索引构建
    ├── milvus_seed_data.py         # Milvus 向量种子数据（MySQL -> Embedding -> Milvus）
    └── knowledge_base_docs.py      # 知识库文档分块（22个文本块）
```

## 数据库连接信息

### Docker 容器一览

| 容器名 | 镜像 | 端口 | 用途 |
|--------|------|------|------|
| `matchforge-mysql` | mysql:8.0 | 3306 | MySQL 数据库 |
| `matchforge-neo4j` | neo4j:5.20.0 | 7474 / 7687 | Neo4j 图数据库 |
| `matchforge-milvus` | milvusdb/milvus:v2.4.0 | 19530 | Milvus 向量数据库 |
| `matchforge-etcd` | quay.io/coreos/etcd:v3.5.5 | 2379 | Milvus 依赖 |
| `matchforge-minio` | minio/minio:latest | 9000 / 9001 | Milvus 依赖 + 对象存储 |
| `matchforge-redis` | redis:7-alpine | 6379 | Redis 缓存 |
| `matchforge-postgres` | postgres:16-alpine | 5432 | 长期记忆库（AgentMemory，非本数据层使用） |

> 注：docker-compose 未含 phpMyAdmin；MySQL 用 `mysql` CLI 或本地 DBeaver/Navicat 连接 `127.0.0.1:3306`。

### 各数据库访问方式

| 数据库 | 访问地址 | 用户名 | 密码 | 数据库/实例 |
|--------|---------|--------|------|------------|
| **MySQL** | 127.0.0.1:3306（CLI / DBeaver） | `matchforge` | `matchforge123` | `matchforge`（root 密码同为 `matchforge123`） |
| **Neo4j Browser** | http://localhost:7474 | `neo4j` | `matchforge123` | `neo4j` |
| **Milvus** | 127.0.0.1:19530（无 Web 界面） | - | - | - |
| **MinIO 控制台** | http://localhost:9001 | `minioadmin` | `minioadmin123` | - |
| **Redis** | 127.0.0.1:6379（无 Web 界面） | - | `matchforge123` | - |

## MySQL 表结构（10张表，对齐架构文档 v1.2）

| 表名 | 用途 | 记录数 |
|------|------|--------|
| `enterprises` | 企业表（采购方与供应方共用） | 0 |
| `users` | 用户表（采购/供应端账号） | 0 |
| `buyers` | 采购档案表（下游） | 0 |
| `suppliers` | 供应商表（上游） | 35 |
| `qualifications` | 资质证照表（独立表，原 suppliers.qualifications 拆出） | 100 |
| `categories` | 品类字典表（支持层级） | 0 |
| `products` | 供应商产品表（specs 用 JSON 存中文键名） | 101 |
| `material_dictionary` | 标准物料字典表（F3 标准化用） | 81 |
| `rfqs` | 询价单表（含 thread_id 多轮会话标识） | 0 |
| `leads` | 销售线索表（含分级 A/B/C/D） | 0 |

## 数据统计

| 数据集 | 文件 | 数量 | 目标存储 | 导入状态 |
|--------|------|------|----------|---------|
| 种子供应商 | `suppliers/suppliers.json` | 35家供应商 + 101条产品 + 100条资质 | MySQL + Milvus | ✅ MySQL 已导入 |
| 替代料交叉引用 | `alternatives/alternatives.json` | 36组 + 137条关系（114个料号） | Neo4j | ✅ Neo4j 已导入 |
| 标准字典 | `dictionary/dictionary.json` | 81条标准编码 | MySQL | ✅ MySQL 已导入 |
| 知识库文档 | `knowledge_base_docs.py` | 22个文本分块 | Milvus | 待导入 |

## 替代料 L1-L5 五级分类（对齐 PRD v2.0 §11.2）

每条替代关系包含 `level` 和 `level_desc` 字段：

| 等级 | 名称 | 含义 | 数量 |
|------|------|------|------|
| L1 | 完全等效 | 关键参数全部一致，可直接替换 | 56条 |
| L2 | 参数向上兼容 | 替代参数优于原型号，一般可直接替换 | 69条 |
| L3 | 功能兼容需工程调整 | 主体兼容，个别差异需工程师评估 | 6条 |
| L4 | 封装或引脚不兼容 | 电气兼容但物理不兼容，需改板 | 4条 |
| L5 | 仅供参考 | 信息不足或弱关联，不建议直接替换 | 2条 |

> 置信度 <0.7 的替代进入人工审核队列，前端折叠在"仅供参考"区（PRD §13 AI安全红线）

## Neo4j 图谱结构

```
节点:
  (:Part {part_number, brand, category, specs})        -- 107个
  (:Category {name})                                    -- 5个

关系:
  (:Part)-[:EQUIVALENT_TO {confidence, source, verified, note, level, level_desc}]->(:Part)  -- 137条
  (:Part)-[:BELONGS_TO]->(:Category)                                                          -- 114条
```

## 快速使用（Windows 环境）

### 1. 前置条件

- **Docker Desktop** 最新版
- **Python 3.11+**（需安装 pymysql、neo4j、pymilvus、python-dotenv）

```powershell
pip install pymysql neo4j pymilvus python-dotenv
```

> Neo4j 服务端版本: 5.20.0（见 docker-compose），Python 驱动使用最新 6.x 版本

### 2. 启动 Docker 服务

```powershell
# 在项目根目录执行（compose 文件在 deploy/）
docker compose -f deploy/docker-compose.yml up -d
```

### 3. 配置环境变量

```powershell
# 根目录已有 .env（对齐 docker-compose，密码 matchforge123）；如需重生成：
copy .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY / EMBEDDING_API_KEY 等
```

### 4. 一键初始化

```powershell
cd data
python init_all.py                    # 全部执行
python init_all.py --step mysql       # 仅 MySQL（建表 + 供应商 + 字典）
python init_all.py --step neo4j       # 仅 Neo4j（替代料图）
python init_all.py --step milvus      # 仅 Milvus（集合 + 向量索引）
```

### 5. 单独运行各导入脚本

```powershell
# MySQL 建表（matchforge 库由 docker-compose 自动创建；matchforge 用户可直接加载）
docker exec -i matchforge-mysql mysql -u matchforge -pmatchforge123 matchforge < data\mysql_schema.sql

# 种子供应商导入（含资质独立表）
python data\suppliers\import_to_mysql.py

# 标准字典导入
python data\dictionary\import_to_mysql.py

# Neo4j 替代料图（含 L1-L5 等级）
python data\alternatives\import_to_neo4j.py --clear

# Milvus 集合创建 + 种子数据
python data\milvus_collections.py
python data\milvus_seed_data.py
```

### 6. 查看所有数据

```powershell
cd data
python view_all_data.py
```

### 7. 验证数据

```powershell
# MySQL（用 mysql CLI 或本地 DBeaver 连接 127.0.0.1:3306，用户 matchforge / 密码 matchforge123）
docker exec matchforge-mysql mysql -u matchforge -pmatchforge123 matchforge -e "SELECT COUNT(*) FROM suppliers;"          # 应为 35
docker exec matchforge-mysql mysql -u matchforge -pmatchforge123 matchforge -e "SELECT COUNT(*) FROM products;"           # 应为 119
docker exec matchforge-mysql mysql -u matchforge -pmatchforge123 matchforge -e "SELECT COUNT(*) FROM qualifications;"     # 应为 100
docker exec matchforge-mysql mysql -u matchforge -pmatchforge123 matchforge -e "SELECT COUNT(*) FROM material_dictionary;" # 应为 81

# Neo4j（浏览器打开 http://localhost:7474，用户名 neo4j，密码 matchforge123）
MATCH (n) RETURN labels(n), count(n)
MATCH ()-[r:EQUIVALENT_TO]->() RETURN count(r)                   # 应为 137
MATCH ()-[r:EQUIVALENT_TO]->() RETURN r.level, r.level_desc, count(r)  # 按等级统计

# Milvus
python -c "from pymilvus import connections, Collection; connections.connect(host='127.0.0.1', port='19530'); print(Collection('product_embeddings').num_entities)"
```

## 数据说明

### 供应商分布
- 深圳: 22家 | 东莞: 4家 | 苏州: 5家 | 上海: 3家 | 南京: 1家
- 覆盖品类: MLCC电容(26)、贴片电阻(18)、二极管(16)、连接器(14)、MOSFET(9)、贴片电感(8)、LED驱动IC(6)、电解电容(4)、通信模块(4)、三极管(3)、晶振(3)、MCU单片机(3)、电源IC(3)、继电器(2)
- 资质: ISO9001 / RoHS / REACH / IATF16949 / ISO14001（独立 qualifications 表存储，100条）

### 替代料交叉引用
- MLCC电容: 10组（村田/三星电机/国巨/华新科/TDK）
- 贴片电阻: 8组（国巨/厚声/旺诠/村田/KOA）
- 二极管: 5组（ON Semi/ST/Nexperia/Vishay/Diodes Inc）
- 连接器: 4组（JST/Molex/TE）
- MCU: 3组（STM32/GD32）
- 置信度: 0.82~0.99，平均0.93
- 来源: Datasheet交叉引用(53条) / 行业交叉表(78条)
- 等级: L1完全等效(56条) / L2向上兼容(69条) / L3功能兼容(6条) / L4封装不兼容(4条) / L5仅供参考(2条)

### 标准字典
- MLCC电容: 18条（0402/0603/0805/1206封装，X5R/X7R/X7S/C0G介质）
- 贴片电阻: 15条（0201/0402/0603/0805，±1%/±5%精度）
- 电感: 11条（功率电感/高频电感）
- 二极管: 10条（肖特基/稳压/整流/快恢复）
- 连接器: 10条（JST XH/PH/ACH + Molex 51021/51005/43045）
- MOSFET: 9条（N沟道/P沟道，SOT-23/TO-220/SOP-8）
- MCU: 8条（STM32F1/F4/G0/L4 + GD32F1/F3/E2）

## 导入脚本更新说明

### suppliers/import_to_mysql.py
- 适配新表结构：去掉 suppliers 表的 qualifications 字段
- 新增资质独立表写入：qualifications 表（supplier_id, type, status）
- products 表新增 brand 字段
- 清空时同时清空 qualifications 表

### alternatives/import_to_neo4j.py
- EQUIVALENT_TO 关系新增 level + level_desc 属性
- 验证查询新增按 L1-L5 等级统计

## 下游依赖

```
P4 数据层 (本目录) ──喂料──▶ P3 AI智能体 (LangGraph Supervisor + 6子智能体)
                              │
                              ├── F1 需求解析 Agent    ← 读取 material_dictionary
                              ├── F3 标准化 Agent      ← 读取 material_dictionary
                              ├── F4 替代料推荐 Agent  ← 查询 Neo4j 图（含L1-L5等级）
                              ├── F6 供应商匹配 Agent  ← 查询 Milvus 向量 + MySQL 过滤
                              ├── F7 询价生成 Agent    ← 读取 products
                              └── 线索分级 Agent       ← 读取 suppliers + leads
```

> 功能编号 F1-F9 对齐 PRD v2.0 §10

## Git 提交记录

```
53bd522  feat: P4 种子数据与知识库（初次提交）
e543dc0  refactor: 对齐v1.2架构文档（schema+L1-L5等级）
c00dc88  docs: 更新README + Neo4j导入脚本支持等级
439e8b5  docs: v1.3 更新README + import_to_mysql适配新表结构
(下一次)  docs: v1.4 精简README（去掉.env配置块，简化Docker启动）
```

## Git 提交命令

```powershell
cd D:\MatchForge
git add .
git commit -m "docs: v1.4 精简README"
git push origin feature/data-seed
```
