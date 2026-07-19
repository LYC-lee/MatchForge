# MatchForge 分支巡查与维护报告 — 2026-07-17 15:19 (Asia/Shanghai)

- **轮次性质:** 每日定时巡查(第 1 轮,无历史状态文件)
- **本轮结论:** 未自动合并任何分支;未创建 PR(环境受限 + 分支存在冲突);本地 main 已 ff 同步
- **origin/main:** `38c96e4` — docs(zhl): 合入 zhl 分支选择性评审记录 (#15)

## 1. 扫描到的远程分支(14 个,含 origin/HEAD)

| 分支 | ahead | behind | 保护 | 处置 |
|---|---|---|---|---|
| origin/main | 0 | 0 | 是 | 基准 |
| origin/agent | 0 | 7 | 是 | 跳过合并评估;仅记录(PR #14 已合入 main) |
| origin/zhl | 3 | 33 | 是 | **高风险,只报告**(见 §3) |
| origin/rag | 0 | 82 | 是 | 跳过;保护分支不清理 |
| origin/lyc | 0 | 20 | 是 | 跳过;保护分支不清理 |
| origin/feature/data-seed | 0 | 46 | 是 | 跳过;保护分支不清理 |
| origin/codex/zhl-value-absorb | 2 | 8 | 否 | **只报告:有冲突 + 页面改动待浏览器验收**(见 §2) |
| origin/codex/backend-integration-dashboard-rfq | 0 | 54 | 否 | 已全量并入 main → 清理候选 |
| origin/codex/demo-scenario-backend | 0 | 45 | 否 | 已全量并入 main → 清理候选 |
| origin/codex/demo-scenario-frontend | 0 | 41 | 否 | 已全量并入 main → 清理候选 |
| origin/codex/demo-scenario-integration | 0 | 36 | 否 | 已全量并入 main → 清理候选 |
| origin/codex/loop-006-backend-startup | 0 | 6 | 否 | 已全量并入 main → 清理候选 |
| origin/codex/selective-zhl-api-alignment | 0 | 7 | 否 | 已全量并入 main → 清理候选 |

## 2. origin/codex/zhl-value-absorb(ahead 2 / behind 8)— 只报告

- **tip:** `b34e2c8` docs(zhl-absorb): summary + plan update (useDashboard 去 mock 降级, ready)
- **commit 列表:**
  - `d96bed3` refactor(web): useDashboard 移除 mock 降级, 数据来源统一到真实 API (zhl 价值吸收)
  - `b34e2c8` docs(zhl-absorb): summary + plan update
- **diff 摘要(相对 merge-base):** 4 文件,+157/-27。`web/src/composables/useDashboard.ts`(移除 mock 降级,新增 buildEmptyDashboard,dataSource 类型 `'api'|'mock'|'loading'` → `'api'|'loading'|'error'`,删死代码 useMockInternalQuestions)、`web/src/views/ShortageProcurementView.vue`(1 行 UI 分支文案)、2 个 docs 文件。
- **ready 标记来源:** 最新 commit message 含 "ready";summary 文件 `2026-07-17-1008-zhl-value-absorb.md` 明确写 "Ready 状态: ready"。
- **风险等级:高(阻断项存在)**
  - **merge-tree 预演:与 origin/main 冲突**,冲突文件 `docs/superpowers/plans/loop-mvp-industrialization-plan.md`(exit=1)。规则:有冲突 → 高风险 → 只报告。
  - 次要因素:涉及页面(ShortageProcurementView / Home 驾驶舱数据源),summary 自述"浏览器验收移交 QA",浏览器验收未完成。
- **处置:只报告,不合并、不建 PR。** 冲突本身限于 docs 计划文件,代码差异小且方向明确(去 mock 依赖),人工 rebase/解冲突后可重新进入评估。
- **PR 状态:** 通过 `git ls-remote refs/pull/*/head` 比对,15 个 PR ref 中无与 tip `b34e2c8` 匹配者,**该分支当前无 PR**;本环境无 gh CLI 且未配置 GITHUB_TOKEN/GH_TOKEN,本轮无法代为创建 PR。
- **建议下一步:** 人工在分支上 rebase origin/main 解掉 plan 文档冲突 → 跑浏览器验收(Home、ShortageProcurement 后端不可用时的空驾驶舱展示)→ 建 PR 走人工合并。

## 3. origin/zhl(ahead 3 / behind 33)— 高风险,只报告(保护分支)

- **tip:** `919364b` merge: 合并 main 到 zhl,保留 zhl 的 mock 移除和 API 对齐改动
- **commit 摘要:** `aa27b59` 移除mock依赖+高风险样式优化+后端API字段对齐;`ea676fa` apply mock removal and API alignment to P1Home and P3Alternatives;`919364b` 合并 main 到 zhl。
- **diff 摘要:** 3 个前端大文件(P1Home.vue、P3Alternatives.vue、ShortageProcurementView.vue),+1070/-961。
- **风险依据:** 保护分支;2026-07-17 09:35 选择性评审(见 `2026-07-17-0935-zhl-selective-review.md`,已随 PR #15 合入 main)结论为**不合并、不 cherry-pick**——会删除 demo 沙盘/loop/migration/注册身份等内容,属大范围历史回退风险。
- **处置:只报告。** 可吸收价值已通过 `codex/zhl-value-absorb` 以低风险增量方式提取(useDashboard 去 mock),无新增"选择性吸收建议"。

## 4. 本轮未自动合并的说明

- 唯一非保护 ready 分支(zhl-value-absorb)存在合并冲突,触发"有冲突 → 高风险 → 只报告"规则;即使无冲突,其涉及页面且浏览器验收未完成,最高也只到中风险(建 PR 不合并)。
- 本轮自动合并配额(1 个)未使用。无 push,无 force-push,保护分支均未触碰。

## 5. 本地同步

- 用户工作区巡查前干净(仅 main 落后远程 8 个 commit),已执行 `git pull --ff-only`,本地 main `38c96e4` == origin/main ✓。
- 本报告与状态文件为新写入的未跟踪文件,未自动 commit(避免越权推送 main),请人工决定是否提交。

## 6. GitHub 同步状态

- gh CLI 不存在、GITHUB_TOKEN/GH_TOKEN 未配置 → 本轮**无法**创建/更新 PR、无法发 PR/Issue 评论。
- 如需 GitHub 侧同步,请安装 gh 并 `gh auth login`,或提供 token;下一轮起可自动创建 PR 与评论。

## 7. 分支清理候选(半自动模式,仅报告不删除)

以下分支相对 origin/main ahead=0,tip 已被 main 完整包含:

| 分支 | tip 已被 main 包含 | 模式 | 处置建议 |
|---|---|---|---|
| codex/backend-integration-dashboard-rfq | 是 | codex/* | 可删除(待确认) |
| codex/demo-scenario-backend | 是 | codex/* | 可删除(待确认) |
| codex/demo-scenario-frontend | 是 | codex/* | 可删除(待确认) |
| codex/demo-scenario-integration | 是 | codex/* | 可删除(待确认) |
| codex/loop-006-backend-startup | 是 | codex/* | 可删除(待确认) |
| codex/selective-zhl-api-alignment | 是 | codex/* | 可删除(待确认) |
| agent / rag / lyc / feature/data-seed | 是 | 保护 | **永不删除** |

- 连续 5 轮成功后才允许自动清理 codex/*/feature/* 中已合并、无 P0/P1 回归的分支。

## 7.1 清理执行记录(2026-07-17 15:34,用户已确认)

用户于 15:33 确认删除。删除前复核:6 个分支 tip 均为 origin/main 祖先(无新提交),随后执行 `git push origin --delete`,**全部删除成功**:

| 分支 | 删除前 tip |
|---|---|
| codex/backend-integration-dashboard-rfq | `4cf466b` |
| codex/demo-scenario-backend | `d654778` |
| codex/demo-scenario-frontend | `68e2437` |
| codex/demo-scenario-integration | `c9b9eaa` |
| codex/loop-006-backend-startup | `03b62a8` |
| codex/selective-zhl-api-alignment | `89cc4d6` |

删除后远程剩余分支:main、agent、codex/zhl-value-absorb、feature/data-seed、lyc、rag、zhl。保护分支均未触碰,未 force-push。

## 8. 稳定运行计数

- 本轮计为**部分成功**:巡查、评估、本地同步、报告生成均完成;但 GitHub 侧报告/PR 同步因环境缺失(无 gh/token)未达成,按保守原则**连续成功计数保持 0**,维持半自动删除模式。
- 状态文件:`docs/superpowers/branch-maintenance-state.json`
