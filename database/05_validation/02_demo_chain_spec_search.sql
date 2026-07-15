-- ============================================================
-- Demo 链路 B：按参数找候选物料（02_demo_chain_spec_search.sql）
-- ============================================================
-- 用途: 验证“规格参数 -> 命中品类 -> 匹配 parts.specs -> 候选物料 -> 供应商”闭环
-- 输入: 0805 1uF X5R 25V MLCC
-- 期望输出:
--   1) 命中品类 MLCC（id=1）
--   2) parts.specs 匹配 ≥2 条候选料号（TMK212BJ105KG-T、CL21B105KAFNNNE）
--   3) 命中物料的供应商能力 ≥2 家
-- 说明: MySQL 8.0 支持 JSON_EXTRACT 取中文键；specs 键名见
--       02_field_dictionary/01_field_dictionary.md §5
-- ============================================================

USE pc_industry;

-- 1. 由“MLCC”关键字命中品类
SELECT id, name, description
FROM categories
WHERE name = 'MLCC' OR description LIKE '%陶瓷电容%';
-- 期望: id=1, MLCC

-- 2. 在 MLCC 品类下按 specs 参数匹配候选物料
--    封装=0805 且 容值=1uF 且 温度系数=X5R 且 额定电压=25V
SELECT
  id,
  part_number,
  brand,
  specs,
  lifecycle_status,
  confidence_level
FROM parts
WHERE category_id = 1
  AND JSON_UNQUOTE(JSON_EXTRACT(specs, '$.封装')) = '0805'
  AND JSON_UNQUOTE(JSON_EXTRACT(specs, '$.容值')) = '1uF'
  AND JSON_UNQUOTE(JSON_EXTRACT(specs, '$.温度系数')) = 'X5R'
  AND JSON_UNQUOTE(JSON_EXTRACT(specs, '$.额定电压')) = '25V'
  AND lifecycle_status = 'active'
ORDER BY part_number;
-- 期望: 2 行 —— CL21B105KAFNNNE(id=17)、TMK212BJ105KG-T(id=21)

-- 3. 放宽到 0805 1uF（不限介质/耐压）查看同封装同容值候选
SELECT
  part_number, brand,
  JSON_UNQUOTE(JSON_EXTRACT(specs, '$.温度系数')) AS 介质,
  JSON_UNQUOTE(JSON_EXTRACT(specs, '$.额定电压')) AS 耐压,
  confidence_level
FROM parts
WHERE category_id = 1
  AND JSON_UNQUOTE(JSON_EXTRACT(specs, '$.封装')) = '0805'
  AND JSON_UNQUOTE(JSON_EXTRACT(specs, '$.容值')) = '1uF'
ORDER BY 耐压, 介质;
-- 期望: ≥2 行，展示 X5R 25V 与 X7R 50V 等差异，供工程师评估替代

-- 4. 为候选物料匹配 approved 供应商（MLCC 品类）
SELECT
  p.part_number,
  p.brand,
  s.id AS supplier_id,
  s.name AS supplier_name,
  sc.brand_names,
  sc.moq,
  sc.lead_time_days,
  sc.region
FROM parts p
JOIN supplier_capabilities sc ON sc.category_id = p.category_id AND sc.audit_status = 'approved'
JOIN suppliers s ON s.id = sc.supplier_id
WHERE p.id IN (17, 21)
ORDER BY p.part_number, sc.lead_time_days;
-- 期望: 每个候选料号 ≥2 家 approved 供应商
