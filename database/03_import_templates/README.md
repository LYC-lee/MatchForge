# 03 Import Templates

用于 16 小时冲刺的 CSV/Excel 导入模板。

## 放什么

- 公司库导入模板
- 物料库导入模板
- 供应商能力导入模板
- 替代关系导入模板
- RFQ 样例导入模板

## 建议文件

```text
01_companies_template.csv
02_parts_template.csv
03_supplier_capabilities_template.csv
04_part_alternatives_template.csv
05_rfqs_template.csv
```

## 模板要求

- 第一行使用英文列名。
- 第二行可以放一条示例数据。
- 必须包含 `source_name`、`source_url`、`confidence_level`、`updated_at`。
- JSON 字段必须是合法 JSON 字符串。
