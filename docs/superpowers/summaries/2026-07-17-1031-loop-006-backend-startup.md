# MatchForge Loop-006 Summary - 后端启动加速 (延迟 langchain_openai 导入)

- **Time:** 2026-07-17 10:31 +08:00
- **Role:** Development Loop AI (loop-006)
- **Goal:** 解除 QA 09:06 P0 -- 后端 `uvicorn api.main:main` / `from api.main import main` 90s 无进展(疑似启动卡住)。
- **Branch:** `codex/loop-006-backend-startup`
- **Commit:** (提交后填入)
- **Base:** `origin/main` (`1f7440b`)
- **Ready 状态:** ready (启动 82.4s->22.7s, P0 解除; 9/9 测试过; build 过)

## 1. 根因分析 (python -X importtime profile)

`from api.main import main` = **82.4s**(非卡死, 是慢导入)。调用链:

```
api.main (82s) -> create_app() -> from api.routers import procure (61s)
  -> ai.graph -> ai -> ai.base_agent (55s)
    -> from langchain_openai import ChatOpenAI (54s cumulative)
      -> transformers (25.7s self) + langchain_openai.chat_models.azure (23.8s)
```

`ai/base_agent.py:21` 与 `ai/supervisor.py:23` 在**模块级** `from langchain_openai import ChatOpenAI`, 触发 `transformers`(~26s) + `langchain_openai` 累计 ~54s。而 `ChatOpenAI` 仅在工厂函数 `get_agent_llm`/`get_supervisor_llm`(运行时调用)使用, 不在导入期需要。`import langgraph` 本身 0.0s(非瓶颈, 历史"langgraph 冷导入慢"判断有误)。

## 2. 修改说明

**延迟 langchain_openai 导入到工厂函数内首次调用:**

- `ai/base_agent.py`:
  - 移除模块级 `from langchain_openai import ChatOpenAI`, 改为 `if TYPE_CHECKING:` 块(仅供类型注解; `from __future__ import annotations` 已启用, 运行期注解为字符串不求值)。
  - `get_agent_llm()` / `get_supervisor_llm()` 内部加局部 `from langchain_openai import ChatOpenAI`(首次调用才触发 transformers)。
- `ai/supervisor.py`:
  - 同样移除模块级导入 -> `if TYPE_CHECKING:` 块; `get_supervisor_llm()` 内部局部导入。

**效果:**
- `from api.main import main`: **82.4s -> 22.7s**(-72%, 远低于 QA 90s 阈值, P0 解除)。
- 测试冷导入: ~130s -> **12.5s**(conftest mock LLM, 延迟导入不触发 transformers, 测试大幅提速)。
- 真实首次 procure 请求仍会加载 transformers(~25s), 但发生在用户主动寻源时, 不阻塞启动; 且仅一次(后续复用已加载模块)。

## 3. 修改文件清单

- `ai/base_agent.py` - 模块级 langchain_openai -> TYPE_CHECKING + 工厂函数内局部导入
- `ai/supervisor.py` - 同上

无前端/路由/数据改动。

## 4. 数据变更说明

无。纯 Python 导入时机调整。

## 5. 测试与 Build 结果

- **后端 pytest:** `tests/test_supervisor.py + tests/test_register_identity.py` -> **9 passed**(12.48s)。test_supervisor 覆盖 ai/supervisor + ai/base_agent 路由(mock LLM, 验证延迟导入不破坏模块导入与功能)。
- **启动计时:** `python -c "from api.main import main"` -> **22.7s**(修前 82.4s)。
- **延迟导入 smoke:** `from ai.base_agent import get_agent_llm` 10.8s(无 langchain_openai); `get_agent_llm()` 触发延迟导入并构造 ChatOpenAI(报 "Missing credentials" 仅因 `python -c` 未加载 .env, 非回归; 真实后端加载 .env 有 key)。`ai.supervisor.get_supervisor_llm` 同理。
- **前端 build:** `npm run build` ✓(6.60s, 无前端改动)。

## 6. 浏览器验收结果

**N/A(纯后端导入改动, 不涉及前端页面行为)。** 建议 Codex QA 复验: `uvicorn api.main:main` 启动 <90s 进入监听, `/api/v1/health` 可达; demo 链路 + procure 寻源(首次触发延迟导入)正常。

## 7. 未验证项

- 真实后端(加载 .env + MySQL)启动时长(本环境 22.7s 为 import 计时, 未含 uvicorn 监听就绪; 但 import 是主要耗时, 已大幅下降)。
- 首次 procure 请求的延迟导入耗时(预期 ~25s transformers 加载, 一次性)。
- 全量后端 pytest(本轮跑 supervisor+register 子集 9/9; 历史 16 个 ai/kb 预存失败与本轮无关, 未重跑)。

## 8. 风险

- **首次 procure 请求变慢(~25s):** transformers 延迟到首次 get_agent_llm 调用加载。演示场景可预热(启动后发一个 procure 请求), 或接受首次略慢。后续请求复用已加载模块, 无影响。
- **剩余 22.7s 启动:** 主要为 `init_db()`(MySQL create_all) + langchain_core + pydantic + fastapi 导入。可后续优化(init_db 异步化 / 进一步延迟), 但已解除 P0。
- **TYPE_CHECKING 注解:** `-> ChatOpenAI` 通过 TYPE_CHECKING 解析(类型检查器可见, 运行期为字符串), 不影响运行。

## 9. 下一步建议

1. **Codex QA 复验** 后端启动 <90s + procure 寻源(首次延迟导入)正常。
2. integration 合并 `codex/zhl-value-absorb`(待合并) + 本 `codex/loop-006-backend-startup`。
3. 后续优化(可选): init_db 异步化 / 启动日志, 进一步降启动耗时; 或预热 procure 路径。
4. 推进 QA P1-4 余(9004 ShortageProcurement/ProductsBom 物流语义) / P1-3 供应商工作台空状态。

## 10. 元信息

- **branch:** `codex/loop-006-backend-startup`
- **commit:** `74d8a10`
- **base:** `origin/main` `1f7440b`
- **worktree:** `D:/Project/project mvp/MatchForge-loop-006-backend-startup`
- **ready:** yes(目标完成 + 9/9 测试 + build 过 + 启动 82.4s->22.7s P0 解除 + 浏览器验收 N/A 移交 QA 复验启动)
