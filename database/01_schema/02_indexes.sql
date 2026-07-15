-- ============================================================
-- MatchForge pc_industry - 补充复合索引（02_indexes.sql）
-- 说明: 01_core_tables_ddl.sql 已在建表时定义主键/外键/单列索引；
--       本文件只补 Demo 链路常用的复合索引，提升按品类+品牌/品类+状态检索性能。
-- 执行: 在 01_core_tables_ddl.sql 之后运行（幂等：用 IF NOT EXISTS 风格先 DROP 再建）
-- ============================================================

USE pc_industry;

-- parts: 按 品类+品牌 检索候选物料（链路 B 按参数找料 + 链路 A 品牌偏好过滤）
CREATE INDEX idx_parts_category_brand ON parts (category_id, brand);

-- parts: 按 品类+生命周期 过滤在产料（排除 eol/obsolete）
CREATE INDEX idx_parts_category_lifecycle ON parts (category_id, lifecycle_status);

-- supplier_capabilities: 按 品类+供货区域 找供应商（链路 A/C 供应商匹配）
CREATE INDEX idx_cap_category_region ON supplier_capabilities (category_id, region);

-- companies: 按国家+地区筛选公司库
CREATE INDEX idx_companies_country_region ON companies (country, region);

-- ============================================================
-- 后续可扩展（本轮不做，留作 10_ 长期扩展）:
--   - parts.specs 的 JSON 函数索引（MySQL 8.0.17+）:
--       CREATE INDEX idx_parts_specs_cap ON parts (
--         (CAST(JSON_EXTRACT(specs, '$.容值') AS CHAR(50)))
--       );
--   - companies 全文索引 (FULLTEXT) 支持公司名/简介搜索
--   - 软删除字段 deleted_at + 索引（第一版未引入）
-- ============================================================
