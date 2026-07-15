# 05 Validation

用于 16 小时冲刺的闭环验证查询和验收记录。

## 放什么

- Demo 查询 SQL
- 手动验证记录
- 三条业务链路的输入和期望输出
- 冲刺验收清单

## 建议文件

```text
01_demo_chain_missing_part.sql
02_demo_chain_spec_search.sql
03_demo_chain_bom_risk.sql
04_acceptance_checklist.md
```

## 必验链路

```text
链路 A：缺货找替代
链路 B：按参数找候选物料
链路 C：BOM 风险预演
```

所有验证结果必须来自样例数据或数据库记录，不依赖 LLM 编造事实。
