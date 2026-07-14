# AI 供需对接平台 - 系统架构文档

| 项 | 内容 |
|---|---|
| 文档版本 | v1.2 |
| 编写日期 | 2026-07-14 |
| 适用范围 | 2 天 Spike（Phase 0）+ 8-12 周 MVP（Phase 1-4） |
| 关联文档 | [产品需求文档](AI供需对接平台-产品需求文档.md)、[项目开发文档](AI供需对接平台-项目开发文档.md) |
| 技术栈基线 | 通义千问 DashScope + LangGraph(Supervisor+6 智能体) + FastAPI + MySQL 8.0 + Milvus 2.4 + Neo4j + Redis 7 + Vue 3 |
| 技术栈来源 | 复用团队既有"电脑元件客服 MVP"工程栈，仅替换业务语义 `[待确认]` |

> 本栈继承自既有代码库（Vue3/FastAPI/LangGraph/MySQL/Milvus/Neo4j/Redis/通义千问），Spike 无需从零搭基建，主要工作是**把 6 个智能体的业务语义从"客服/FAQ"改为"供需匹配"**并接入电子元器件数据。

---

## 1. 设计目标与约束

| 目标 | 说明 |
|---|---|
| AI 楔子可验证 | 端到端跑通"NL 需求 -> 解析 -> 替代料 -> 供应商匹配 -> 询价单 -> 线索分级" |
| 幻觉可控 | 事实型数据（型号/规格/报价/供应商）不交给 LLM 自由生成 |
| 可溯源 | 匹配与替代结果必须能追溯到 DB 记录或 Datasheet 来源 |
| 复用既有基建 | 沿用团队 Vue3+FastAPI+LangGraph+MySQL+Milvus+Neo4j 工程，零基建迁移成本 |
| LLM 可替换 | 通过 .env 配置任意 OpenAI 兼容 LLM/Embedding，防供应商锁定 |
| 单边启动 | 下游 AI 工具可独立运行，不依赖上游入驻系统（Spike 期） |

---

## 2. 总体架构（分层）

```
┌──────────────────────────────────────────────────────────────┐
│  前端层  Vue 3 + TypeScript + Pinia + Vue Router + Vite       │
│   ├─ 采购对话式界面（NL 输入 + SSE 流式过程展示）              │
│   ├─ 结果卡（解析规格 / 替代料 / 供应商排序 / RFQ / 线索分级） │
│   └─ 供应商端 + 运营后台（MVP）                               │
│   └─ Axios（自动 Token 刷新拦截器）                           │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS / REST / SSE
┌──────────────────────────▼───────────────────────────────────┐
│  接入层  FastAPI 网关（鉴权 / 限流 / 日志 / SSE）              │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  应用服务层  FastAPI 业务服务                                 │
│   ├─ 询价服务  ├─ 线索服务  ├─ 供应商/画像服务  ├─ 审核服务   │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│  AI 编排层  LangGraph（Supervisor + 6 子智能体）              │
│   Supervisor 调度: parse -> normalize -> alternatives         │
│                   -> match -> gen_rfq -> grade                │
└──────┬───────────────┬───────────────┬───────────────┬───────┘
       │               │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│ LLM 调用    │ │ 向量检索    │ │ 知识库 RAG   │ │ 知识图谱    │
│ 通义千问    │ │ Milvus 2.4  │ │ Milvus      │ │ Neo4j       │
│ DashScope   │ │ (供应商匹配)│ │ (Datasheet  │ │ (替代料交叉 │
│ qwen-max/   │ │             │ │  /标准/FAQ) │ │  引用图)    │
│ qwen-plus   │ │             │ │             │ │             │
│ OpenAI 兼容 │ │             │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
       │               │               │               │
┌──────▼───────────────▼───────────────▼───────────────▼───────┐
│  数据层  MySQL 8.0（业务/供应商/询价/线索）                    │
│          + Redis 7（会话/限流/缓存）+ 对象存储（Datasheet/证照）│
└──────────────────────────────────────────────────────────────┘
```

**多存储职责划分（polyglot persistence）**：
| 存储 | 承载 | 理由 |
|---|---|---|
| MySQL 8.0 | 供应商/产品结构化字段、询价、线索、用户、审核 | 事务可靠、团队既有栈 |
| Milvus 2.4 | 产品/规格向量（供应商匹配）+ 知识分块向量（RAG） | 高吞吐向量检索 |
| Neo4j | 替代料交叉引用图（Part-Part 等效关系） | 多跳传递替代查询是天然图问题 |
| Redis 7 | 会话、限流、热点缓存 | 低延迟 |

---

## 3. 技术栈选型

| 层 | 组件 | 选型 | 说明 |
|---|---|---|---|
| 前端 | 框架 | Vue 3 + TypeScript | 组合式 API，团队既有栈 |
| 前端 | 状态/路由 | Pinia + Vue Router | |
| 前端 | 构建 | Vite | |
| 前端 | HTTP | Axios | 含自动 Token 刷新拦截器 |
| 后端 | 框架 | FastAPI | REST + SSE 流式 |
| 后端 | ORM | SQLAlchemy | |
| 后端 | 工具调用 | LangChain Core + LangChain OpenAI | OpenAI 兼容接口 |
| AI 编排 | 多智能体 | LangGraph（Supervisor + 6 子智能体） | 节点独立、可观测、可替换 |
| LLM | 模型 | 通义千问 DashScope（qwen-max / qwen-plus） | OpenAI 兼容，.env 可换任意兼容模型 |
| Embedding | 向量化 | text-embedding-v3（OpenAI 兼容） | .env 可换 |
| 向量库 | | Milvus 2.4（Docker） | 供应商匹配 + RAG 检索 |
| 知识图谱 | | Neo4j（本地/Docker） | 替代料交叉引用图 |
| 业务 DB | | MySQL 8.0（Docker） | 业务数据，JSON 存规格 |
| 缓存 | | Redis 7（Docker） | 会话管理 / 速率限制 / 缓存 |
| 对象存储 | | MinIO（Spike）/ 云 OSS（MVP） | Datasheet、证照 PDF |
| 部署 | | Docker Compose（Spike）/ 云容器服务（MVP） | 单机起步，MVP 容器编排 |
| 可观测 | | LangFuse + 结构化日志 | LLM trace 必备 |
| LLM 抽象 | | .env 配置任意 OpenAI 兼容 LLM/Embedding | 防供应商锁定，支持 A/B 模型 |

---

## 4. AI 编排层详设（Supervisor + 6 子智能体）

### 4.1 Supervisor 智能体职责
- 接收 raw_query，初始化 Graph State
- 按序调度 6 个子智能体：解析 -> 标准化 -> 替代料 -> 匹配 -> 询价 -> 线索
- 管理共享 State 流转；子智能体失败时捕获异常、写 `errors`、触发模板兜底
- 通过 SSE 向前端回传各阶段进度（"正在解析规格…" "正在匹配供应商…"）
- 可扩展：未来增加协商智能体、采购风险智能体

### 4.2 Graph State（智能体间共享状态）
```python
from typing import TypedDict

class ProcureState(TypedDict):
    thread_id: str                      # 会话标识，支撑多轮上下文（PRD §22.3）
    raw_query: str                      # 原始自然语言需求
    parsed_spec: dict | None            # 抽取的规格
    normalized_spec: dict | None        # 标准化规格（映射标准字典）
    alternatives: list[dict]            # 替代料 [{part, confidence, source, verified}]
    matched_suppliers: list[dict]       # 匹配供应商
    rfq_doc: str | None                 # 结构化询价单
    rfq_id: str | None                  # 持久化的询价单 ID（submit 后回填）
    lead_grade: dict | None             # 线索分级 {grade, score, reasons}
    errors: list[str]                   # 各智能体错误收集
```

### 4.3 子智能体详设

| 子智能体 | 输入 | 处理 | 输出 | 工具/数据 | LLM | 兜底 |
|---|---|---|---|---|---|---|
| 需求解析 Agent（F1） | raw_query | 槽位抽取 + 型号正则校验 | parsed_spec | LangChain + 正则 | qwen-max | 正则命中即信任；未命中走 F-CONFIRM 引导 |
| 标准化 Agent（F2） | parsed_spec | 映射标准品类/参数字典 | normalized_spec | MySQL material_dictionary | qwen-plus（兜底） | 未命中字典保留原值并标 `unmapped` |
| 替代料推荐 Agent（F3） | normalized_spec | 图遍历查等效料 + LLM 推理 | alternatives（带 confidence+source） | **Neo4j** + LLM | qwen-max | 置信度 <0.7 进人工核验队列 |
| 供应商匹配 Agent（F4） | spec + alternatives | 向量召回 + 规则过滤 + 排序 | matched_suppliers | **Milvus** + MySQL | qwen-plus（生成解释） | 召回为空时放宽约束并标注"低置信匹配" |
| 询价生成 Agent（F5） | spec + alternatives + suppliers | 生成结构化询价单 | rfq_doc | LangChain + LLM | qwen-plus | LLM 失败用固定模板填字段 |
| 线索分级 Agent（F6） | 商务字段（用量/交期/品牌偏好） | 规则评分 + LLM 复核理由 | lead_grade | 规则 + LLM | qwen-plus | 规则评分为主，LLM 仅生成可读理由 |

> 智能体编号 F1-F6 对应[产品需求文档 §7.3.2](AI供需对接平台-产品需求文档.md)；单步接口 `/parse` `/alternatives` `/match` `/rfq/generate` 可独立调用单个智能体（见 §6）。

### 4.4 编排图
```
                 ┌──────────────────┐
raw_query ─────▶ │  Supervisor Agent │
                 └────────┬─────────┘
                          │ 按序调度
   ┌──────────┬───────────┼───────────┬──────────┬──────────┐
   ▼          ▼           ▼           ▼          ▼          ▼
 parse    normalize   alternatives  match    gen_rfq    grade
   │          │           │           │          │          │
   └──────────┴───────────┴───────────┴──────────┴──────────┘
                          │
                          ▼ State 流转 + SSE 进度回传
                       END (结果卡 + 线索推送)
```
- 每智能体失败不中断：异常入 `errors`，下游跳过该字段继续
- `alternatives` 与 `match` 可并行（MVP 优化）
- 全程 SSE 回传当前智能体状态

### 4.5 模型选型建议
| 模型 | 用于 | 理由 |
|---|---|---|
| qwen-max | 需求解析、替代料推荐、询价生成 | 准确率/推理质量优先 |
| qwen-plus | 标准化、匹配解释、线索分级 | 轻量任务控成本 |
| （.env 可换） | 全链路 | 支持 A/B 与供应商切换 |

---

## 5. 核心数据流（端到端）

```
采购输入: "0805 10uF X7R 50V MLCC，要国巨或华新科替代，月用量50万，交期2周"
   │
   ▼ 需求解析 Agent (qwen-max + 正则)
parsed_spec = {category:"MLCC", package:"0805", capacitance:"10uF",
               temp_coeff:"X7R", rated_voltage:"50V",
               brand_pref:["YAGEO","Walsin"], monthly_qty:500000, lead_time_weeks:2}
   │
   ▼ 标准化 Agent (MySQL 字典)
normalized_spec = {std_code:"MLCC-0805-X7R-50V-103", ...}
   │
   ▼ 替代料推荐 Agent (Neo4j 图遍历 + qwen-max)
alternatives = [
  {part:"CC0805KKX7R9BB103", brand:"YAGEO", confidence:0.95, source:"Neo4j:EQUIVALENT_TO", verified:true},
  {part:"0805F105Z500NT", brand:"Walsin", confidence:0.66, source:"llm_inferred", verified:false}  # 进人工核验
]
   │
   ▼ 供应商匹配 Agent (Milvus 向量召回 + MySQL 规则过滤: 资质/产能/交期/位置)
matched_suppliers = [
  {id:"S012", name:"深圳XX电子", score:0.92, in_stock:true, moq:100000, lead_time_weeks:1, qualifications:["ISO9001"]},
  {id:"S047", name:"东莞YY科技", score:0.81, in_stock:false, moq:200000, lead_time_weeks:2, qualifications:["ISO9001","IATF16949"]}
]
   │
   ▼ 询价生成 Agent (qwen-plus)
rfq_doc = "询价单 #Q20260714-001\n品名: MLCC 0805 10uF X7R 50V\n可接受替代: YAGEO CC0805KKX7R9BB103...\n月用量: 500000\n交期: 2周\n请报: 含税单价/交期/起订量/库存..."
   │
   ▼ 线索分级 Agent (规则 + qwen-plus)
lead_grade = {grade:"A", score:88, reasons:["月用量高","交期明确","品牌偏好清晰","有替代灵活性"]}
   │
   ▼ 返回前端（结果卡）+ 推送上游（分级线索）
```

---

## 6. API 设计

> 所有业务接口前缀 `/api/v1`；接口契约由 FastAPI 自动生成 OpenAPI，前后端先定 Schema 再并行开发（见[项目开发文档 §7](AI供需对接平台-项目开发文档.md)）。功能 ID 对应[产品需求文档 §7.3](AI供需对接平台-产品需求文档.md)。

### 6.1 接口总览

| 方法 | 路径 | 功能 ID | 说明 | 阶段 |
|---|---|---|---|---|
| GET | `/api/health` | - | 健康检查（Liveness） | Spike |
| POST | `/api/v1/auth/register` | F-AUTH-001 | 用户注册 | MVP |
| POST | `/api/v1/auth/login` | F-AUTH-002 | 用户登录，返回 Access/Refresh Token | MVP |
| POST | `/api/v1/auth/refresh` | F-AUTH-003 | Token 刷新 | MVP |
| GET | `/api/v1/auth/me` | F-AUTH-004 | 当前用户信息 | MVP |
| POST | `/api/v1/procure` | F1-F6 | 一站式寻源，SSE 流式返回各智能体结果 | Spike |
| POST | `/api/v1/parse` | F1 | 仅需求解析 | Spike |
| POST | `/api/v1/alternatives` | F3 | 仅替代料推荐 | Spike |
| POST | `/api/v1/match` | F4 | 仅供应商匹配 | Spike |
| POST | `/api/v1/rfq/generate` | F5 | 生成询价单 | Spike |
| POST | `/api/v1/rfq/submit` | F9-001 | 提交询价 + 触发线索分级与推送 | MVP |
| GET | `/api/v1/rfq/{rfq_id}` | F9-002 | 查询询价状态 | MVP |
| GET | `/api/v1/rfqs` | F9-002 | 当前采购的询价列表 | MVP |
| GET | `/api/v1/suppliers` | F4 | 供应商搜索/列表 | Spike |
| GET | `/api/v1/suppliers/{id}` | F4/F8 | 供应商详情 | Spike |
| POST | `/api/v1/suppliers/onboard` | F7 | 供应商入驻（资质上传） | MVP |
| GET | `/api/v1/leads` | F6 | 上游线索列表（按分级过滤） | MVP |
| POST | `/api/v1/admin/suppliers/{id}/audit` | F10 | 资质审核 | MVP |
| GET | `/api/v1/admin/metrics` | F10 | 运营指标 | MVP |

### 6.2 SSE 事件流（`/api/v1/procure`）

`procure` 为 SSE 流式接口，`Content-Type: text/event-stream`，事件按智能体执行顺序推送：

| 事件 `event` | `data` 字段 | 时机 |
|---|---|---|
| `start` | `{thread_id, rfq_id}` | 链路启动 |
| `progress` | `{agent, status, result?}` | 每个智能体开始/完成；`agent` ∈ `parse/normalize/alternatives/match/gen_rfq/grade`，`status` ∈ `running/done` |
| `token` | `{text}` | 询价单生成阶段的增量 token（可选） |
| `error` | `{agent, message}` | 某智能体失败（不中断链路，写入 `errors`） |
| `result` | 完整 `ProcureState`（见 §4.2） | 全部完成 |
| `end` | `{}` | 流结束 |

示例：
```
event: start
data: {"thread_id":"T123","rfq_id":"Q20260714-001"}

event: progress
data: {"agent":"parse","status":"done","result":{"category":"MLCC","package":"0805",...}}

event: progress
data: {"agent":"match","status":"done","result":[{"id":"S012","score":0.92,...}]}

event: result
data: {"parsed_spec":{...},"alternatives":[...],"matched_suppliers":[...],"rfq_doc":"...","lead_grade":{"grade":"A","score":88}}

event: end
data: {}
```

### 6.3 关键接口 Schema

**POST `/api/v1/procure`**（F1-F6，SSE）
```json
// 请求
{"query": "0805 10uF X7R 50V MLCC，要国巨或华新科替代，月用量50万，交期2周", "thread_id": "可选，多轮时传入"}
// 响应：SSE 事件流（见 §6.2），最终 result 为 ProcureState
```

**POST `/api/v1/parse`**（单步，F1）
```json
// 请求
{"query": "..."}
// 响应
{"parsed_spec": {"category":"MLCC","package":"0805","capacitance":"10uF","temp_coeff":"X7R","rated_voltage":"50V","brand_pref":["YAGEO","Walsin"],"monthly_qty":500000,"lead_time_weeks":2}, "missing_fields": ["tolerance"]}
```

**POST `/api/v1/match`**（单步，F4）
```json
// 请求
{"spec": {...}, "alternatives": [...], "filters": {"in_stock": true, "max_lead_time_weeks": 3}}
// 响应
{"matched_suppliers": [{"id":"S012","name":"深圳XX电子","score":0.92,"in_stock":true,"moq":100000,"lead_time_weeks":1,"qualifications":["ISO9001"]}]}
```

**POST `/api/v1/rfq/generate`**（单步，F5）
```json
// 请求
{"spec": {...}, "alternatives": [...], "suppliers": [...]}
// 响应
{"rfq_doc": "询价单 #Q...\n品名: ...\n月用量: ...\n交期: ...\n请报: 含税单价/交期/起订量/库存..."}
```

**POST `/api/v1/rfq/submit`**（F9-001，需鉴权）
```json
// 请求
{"rfq_doc": "...", "parsed_spec": {...}, "target_supplier_ids": ["S012","S047"]}
// 响应
{"rfq_id": "Q20260714-001", "status": "sent", "leads": [{"supplier_id":"S012","grade":"A","score":88}]}
```

### 6.4 统一错误响应
```json
{"code": "PARSE_FAILED", "message": "需求解析失败：未识别到有效型号", "agent": "parse", "trace_id": "..."}
```
常用 `code`：`UNAUTHORIZED` / `RATE_LIMITED` / `VALIDATION_ERROR` / `PARSE_FAILED` / `NO_MATCH` / `LLM_TIMEOUT`。

### 6.5 鉴权与限流
- Spike 期：`/api/v1/procure` 等寻源接口可匿名调用；`/api/v1/rfq/submit` 及上游/运营接口需 JWT
- MVP：全部业务接口需 JWT（Access 24h / Refresh 7d），仅 `/api/health` 放行
- 限流：Redis 滑动窗口，默认 30 次/分钟/IP（PRD §21.3）
- 所有 LLM 调用经 LangFuse 记录 trace，`trace_id` 透传到响应头便于排障

---

## 7. 数据存储设计

### 7.1 MySQL 8.0（业务数据）
```sql
-- 企业（采购方与供应方共用）
CREATE TABLE enterprises (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  type VARCHAR(20) NOT NULL,               -- buyer/supplier
  credit_code VARCHAR(50),                 -- 统一社会信用代码
  contact VARCHAR(100),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用户（采购/供应端账号；MVP 引入，Spike 期寻源可匿名）
CREATE TABLE users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(128) NOT NULL,     -- bcrypt
  enterprise_id BIGINT,
  role VARCHAR(20) NOT NULL,               -- buyer/supplier/admin
  email VARCHAR(100),
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise (enterprise_id),
  CONSTRAINT fk_user_ent FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 采购档案（下游，关联企业）
CREATE TABLE buyers (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  enterprise_id BIGINT NOT NULL,
  industry VARCHAR(50),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_buyer_ent FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 供应商（上游）
CREATE TABLE suppliers (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  enterprise_id BIGINT,
  name VARCHAR(200) NOT NULL,
  location VARCHAR(100),
  rating DECIMAL(3,2) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'pending',    -- pending/approved/rejected
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_status (status),
  CONSTRAINT fk_supplier_ent FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 资质证照（F7 核验，原 suppliers.qualifications 拆为独立表）
CREATE TABLE qualifications (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id BIGINT NOT NULL,
  type VARCHAR(50) NOT NULL,               -- ISO9001/IATF16949/营业执照...
  cert_no VARCHAR(100),
  file_url TEXT,                           -- 对象存储地址
  status VARCHAR(20) DEFAULT 'pending',    -- pending/verified/rejected
  verified_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_supplier (supplier_id),
  CONSTRAINT fk_qual_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 品类字典
CREATE TABLE categories (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE,        -- MLCC/电阻/连接器...
  parent_id BIGINT,                        -- 支持层级
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 供应商产品（向量在 Milvus，替代关系在 Neo4j）
CREATE TABLE products (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id BIGINT,
  category VARCHAR(50) NOT NULL,           -- 对应 categories.name
  part_number VARCHAR(100),
  specs JSON,                              -- 标准化规格
  datasheet_url TEXT,
  moq INT,
  lead_time_weeks INT,
  price DECIMAL(12,4),
  in_stock BOOLEAN DEFAULT TRUE,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_part (part_number),
  INDEX idx_category (category),
  CONSTRAINT fk_product_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 标准字典（F2 标准化用）
CREATE TABLE material_dictionary (
  std_code VARCHAR(100) PRIMARY KEY,       -- MLCC-0805-X7R-50V-103
  category VARCHAR(50),
  params JSON,
  standard VARCHAR(50)                     -- GB/IEC/EIA
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 询价单（F9）
CREATE TABLE rfqs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  buyer_id BIGINT,
  thread_id VARCHAR(64),                   -- 多轮会话标识
  raw_query TEXT,
  parsed_spec JSON,
  normalized_spec JSON,
  alternatives JSON,
  rfq_doc TEXT,
  status VARCHAR(20) DEFAULT 'draft',      -- draft/sent/quoted/closed
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_buyer (buyer_id),
  CONSTRAINT fk_rfq_buyer FOREIGN KEY (buyer_id) REFERENCES buyers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 线索（上游视角，F6 分级）
CREATE TABLE leads (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_id BIGINT,
  supplier_id BIGINT,
  grade VARCHAR(2),                        -- A/B/C/D
  score INT,
  reasons JSON,
  status VARCHAR(20) DEFAULT 'new',        -- new/contacted/won/lost
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_supplier (supplier_id),
  CONSTRAINT fk_lead_rfq FOREIGN KEY (rfq_id) REFERENCES rfqs(id),
  CONSTRAINT fk_lead_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 7.2 Neo4j（替代料知识图谱）
```cypher
// 节点
(:Part {part_number, brand, category, specs})
(:Supplier {id, name, location, qualifications})
(:Category {name})
(:Standard {code})

// 关系
(:Part)-[:EQUIVALENT_TO {confidence, source, verified}]->(:Part)   // 替代料
(:Part)-[:CROSS_REF {source}]->(:Part)                             // 交叉引用
(:Part)-[:SUPPLIED_BY {moq, lead_time, price, in_stock}]->(:Supplier)
(:Part)-[:BELONGS_TO]->(:Category)
(:Part)-[:CONFORMS_TO]->(:Standard)

// 查询：找某料的替代（含 2 跳传递替代，置信度过滤）
MATCH p=(a:Part {part_number:$pn})-[:EQUIVALENT_TO|CROSS_REF*1..2]-(b:Part)
WHERE all(r IN relationships(p) WHERE coalesce(r.confidence,1) >= 0.7)
RETURN b, p
```
> 用 Neo4j 而非关系表：替代料是多跳图问题（A≈B≈C => A 可替 C），图遍历天然高效且支持传递替代。

### 7.3 Milvus 2.4（向量检索）
| Collection | 字段 | 用途 |
|---|---|---|
| `product_embeddings` | product_id, embedding(1024), category, brand, part_number | 供应商匹配：按 spec 语义召回产品 |
| `knowledge_chunks` | chunk_id, embedding, source_type(datasheet/standard/faq), source_id, text | RAG：行业知识问答、规格查证 |

---

## 8. 部署架构

### 8.1 Spike 期（单机 Docker Compose）
```yaml
services:
  web:        # Vue 3 + Vite
  api:        # FastAPI + LangGraph
  mysql:      # MySQL 8.0
  milvus:     # Milvus 2.4（依赖 etcd + minio 内部存储）
  etcd:       # Milvus 依赖
  neo4j:      # Neo4j（或连本地实例）
  redis:      # Redis 7
  minio:      # 对象存储（亦供 Milvus 内部用）
```
- 目标：5-10 并发，单台云主机或本地
- LLM 走 DashScope 云 API，不自部署
- Neo4j 可用本地实例或入 compose（.env 配置连接串）

### 8.2 MVP 期（容器化 + 可观测）
```
云容器服务（推荐阿里云 ACK，与 DashScope 同生态）:
  - api 多副本 / web / worker
  - RDS MySQL（主从）
  - Milvus（自管或云）
  - Neo4j（Aura 或自管）
  - Redis 云
  - 对象存储 OSS
  - LangFuse（LLM trace）+ Prometheus/Grafana
```
- 异步任务（资质审核通知、线索推送）走 Redis Stream 或消息队列

---

## 9. 非功能设计

| 维度 | Spike 要求 | MVP 要求 |
|---|---|---|
| 性能 | 单次 procure ≤30s（含 LLM） | ≤15s；Milvus 召回 ≤200ms |
| 可用性 | Demo 期间稳定；智能体失败有兜底 | 99.5%；关键路径降级策略 |
| 并发 | 5-10 | 100+ |
| 安全 | 基本 HTTPS | 鉴权 RBAC、数据加密、审计日志、Redis 限流 |
| 可观测 | 结构化日志 + LangFuse trace | + 指标看板 + 告警 |
| 数据持久 | MySQL 持久化，刷新不丢 | 同 + 定期备份 |

---

## 10. 幻觉与数据质量防控（技术落地）

| 风险 | 技术对策 |
|---|---|
| 型号/规格编造 | 需求解析 Agent 用正则 + 标准字典校验；事实字段不交给 LLM 自由生成 |
| 供应商虚构 | 供应商匹配 Agent 仅从 Milvus 召回 + MySQL 过滤，结果带 `supplier_id` 可溯源；禁止 LLM 编供应商名 |
| 替代料错误 | 必须返回 `confidence` + `source`（Neo4j 关系/LLM 推理）；<0.7 进人工核验队列，前端不直接展示 |
| 报价/交期过期 | `products.updated_at` + TTL 规则（如 >30 天标 stale，前端降权/隐藏） |
| 资质造假 | OCR 证照 + 企查查 API 交叉核验 + 人工审核（status=pending 不可匹配） |
| LLM 失败 | 每智能体模板兜底；询价生成失败用固定模板填字段 |
| 不可解释 | 前端展示每条结果来源引用（Neo4j 关系 / Datasheet / 人工核验） |

---

## 11. 技术风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| 替代料交叉引用数据不足 | 高 | 高 | Spike 期人工 curate 20-50 组高频等效料入 Neo4j；MVP 持续扩充 + 用户反馈回流 |
| LLM 解析准确率不达标 | 中 | 高 | Prompt 迭代 + few-shot + 正则前置；不达标字段走人工确认 |
| Milvus 召回噪声大 | 中 | 中 | MySQL 规则强约束过滤（资质/产能/交期）+ 排序调优 |
| Neo4j 图查询性能 | 低 | 中 | 建索引（part_number）、限制跳数（*1..2）、置信度剪枝 |
| 数据合规抓取边界 | 中 | 高 | 优先官方 API/开放数据；爬取需法务确认 |
| 多存储数据一致性 | 中 | 中 | 以 MySQL 为业务事实源；Neo4j/Milvus 异步同步，标注同步时间 |

---

## 12. 架构决策记录（ADR 摘要）

| 决策 | 选择 | 理由 |
|---|---|---|
| AI 编排用 Supervisor 多智能体 | LangGraph Supervisor + 6 子智能体 | 智能体独立可替换、可观测、错误隔离、可扩展 |
| 事实数据不走 LLM | 规则+字典+DB | 控制幻觉、可溯源、成本低 |
| 替代料用 Neo4j | Neo4j 图 | 交叉引用是多跳图问题，支持传递替代查询 |
| 向量库起即用 Milvus | Milvus 2.4（Spike 起） | 沿用既有栈，避免 pgvector→Milvus 迁移 |
| 业务库用 MySQL | MySQL 8.0 | 团队既有栈；JSON 存规格足够（重检索走 Milvus） |
| LLM 用通义千问 + .env 抽象 | DashScope OpenAI 兼容，.env 可换 | 防供应商锁定，支持模型 A/B |
| 前端用 Vue 3 | Vue 3 + TS | 团队既有栈，零学习成本 |
| 早期不碰交易 | 仅信息撮合 | 规避履约/资金/合规风险，聚焦楔子 |
