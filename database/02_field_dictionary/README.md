# 02 Field Dictionary

用于 16 小时冲刺的字段字典、枚举值和数据可信度规则。

## 放什么

- 每张表的字段定义
- 字段类型、是否必填、示例值
- 枚举值说明
- 数据来源和可信度规则

## 建议文件

```text
01_core_tables_dictionary.md
02_enums.md
03_data_source_rules.md
```

## 字段字典格式

| field_name | cn_name | type | required | example | note |
|---|---|---|---|---|---|
| part_number | 型号 | varchar(100) | yes | TMK212BJ105KG-T | 原厂或供应商型号 |
