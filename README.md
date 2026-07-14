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
见 [环境要求.txt](环境要求.txt)

## 6 个子智能体
需求解析 → 标准化 → 替代料推荐(Neo4j) → 供应商匹配(Milvus) → 询价生成 → 线索分级

## 路线图
- **Phase 0（2 天 Spike）**：验证 AI 楔子
- **Phase 1-4（8-12 周 MVP）**：双边最小产品 + 试点

---
真实创业方向 · 电子元器件切入 · 工具先行策略
