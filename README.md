# MatchForge / 智配

**AI 供需对接平台** — 面向电子元器件产业链的 AI 寻源与供应商匹配工具。

> 采购用自然语言描述原材料需求 → AI 解析规格 → 推荐替代料 → 匹配供应商 → 生成询价单 → 分级线索推给上游。

## 技术栈
| 层 | 选型 |
|---|---|
| AI | 通义千问 DashScope + LangGraph(Supervisor + 6 子智能体) + LangChain |
| 后端 | FastAPI + SQLAlchemy |
| 数据 | MySQL 8.0 + Milvus 2.4 + Neo4j + Redis 7 |
| 前端 | Vue 3 + TypeScript + Pinia + Vite |

## 目录结构
- `web/` 前端
- `api/` 后端
- `ai/` LangGraph 智能体（Supervisor + 6 子智能体）
- `data/` 种子数据（供应商 / 替代料 / 标准字典）
- `deploy/` docker-compose 部署
- `docs/` 产品需求 / 系统架构 / 项目开发文档

## 快速开始

### 前置条件
- Python 3.11+ (推荐 Conda)
- Node.js 18+ / pnpm
- Docker Desktop (用于 MySQL/Milvus/Neo4j/Redis 等基础设施)

### 1. 启动基础设施 (Docker)
```bash
cd deploy
docker compose up -d mysql milvus etcd minio neo4j redis postgres
# 等待 MySQL healthy (约 10s)
docker compose ps   # 确认 mysql 状态为 healthy
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 填入 API Key 和数据库密码
```

### 3. 安装后端依赖并启动
```bash
pip install -r requirements.txt
# 在项目根目录执行（不是 api/ 目录）
uvicorn api.main:main --host 0.0.0.0 --port 8000 --reload
```
验证: 访问 `http://localhost:8000/api/v1/health` 返回 `{"status":"ok"}`

### 4. 启动前端
```bash
cd web
npm install
npm run dev   # http://localhost:5173
```

详见 [环境要求.txt](环境要求.txt)

## 6 个子智能体
需求解析 → 标准化 → 替代料推荐(Neo4j) → 供应商匹配(Milvus) → 询价生成 → 线索分级


---
真实创业方向 · 电子元器件切入 · 工具先行策略
