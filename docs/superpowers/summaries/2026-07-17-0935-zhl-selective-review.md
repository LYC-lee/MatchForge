# MatchForge zhl Selective Review

- **Time:** 2026-07-17 09:35 +08:00
- **Base:** `origin/main` (`1f7440b`)
- **Reviewed branch:** `origin/zhl` (`919364b`)
- **Review branch:** `codex/selective-zhl-api-alignment`
- **Result:** no code cherry-pick applied

## 1. Reviewed Commits

- `aa27b59` - `feat: 移除mock依赖+高风险样式优化+后端API字段对齐`
- `ea676fa` - `fix: apply mock removal and API alignment to P1Home and P3Alternatives`
- `919364b` - `merge: 合并 main 到 zhl，保留 zhl 的 mock 移除和 API 对齐改动`

## 2. Decision

Do not merge `origin/zhl` into `main`.

Do not cherry-pick the three commits as-is.

The branch contains some useful intent around mock removal, API field alignment, and sourcing-flow pages, but its final tree is older than current `main` and would remove or overwrite major recently integrated capabilities.

## 3. High-Risk Findings

- `origin/zhl` deletes current demo scenario backend/frontend work, including `api/routers/demo.py`, `kb/demo_calc.py`, `web/src/api/demo.ts`, `web/src/components/demo/DemoConsole.vue`, and demo scenario tests.
- It deletes loop state, QA findings, and integration summaries under `docs/superpowers/`.
- It deletes current registration identity migrations/tests: `06_enterprise_type.sql`, `07_user_name_company.sql`, and `tests/test_register_identity.py`.
- Its `ShortageProcurementView.vue` version is older than current `main` and does not preserve the demo sandbox/RFQ flow now present on main.
- Its `P3Alternatives.vue` still depends on `@/mock/enterpriseContext`, so the "mock removal" is incomplete.
- Its router would re-enable old flow pages (`P1Home`, `P3Alternatives`, etc.) that are not part of current main's routed UX, which now intentionally redirects those routes to `/chat`.

## 4. Potentially Useful Ideas To Rebuild Later

- A dedicated sourcing landing page for `/flow`, but rebuilt against current `useDashboard` and demo/runtime APIs rather than importing old flow pages wholesale.
- A real alternatives page that uses current backend/RAG/procure state instead of `@/mock/enterpriseContext`.
- Some UI treatments from `P1Home.vue` and `P3Alternatives.vue`, especially compact risk/status presentation, can be used as visual reference.
- API field-alignment checks should be reimplemented as narrow tests around current API contracts instead of taking `zhl`'s broad store/API rewrites.

## 5. Verification

- `cd web && npm run build` was run after the attempted low-risk inspection path and passed.
- No code change was retained from `origin/zhl`.

## 6. Recommended Next Step

If the user wants value from `zhl`, create a new clean development loop from current `origin/main` and implement one focused task:

1. real `/flow` sourcing landing page using current `useDashboard`;
2. real alternatives page using current procure/RAG state;
3. supplier workspace empty-state improvement;
4. API contract tests for current procure payloads.

Avoid merging or rebasing `origin/zhl` directly.
