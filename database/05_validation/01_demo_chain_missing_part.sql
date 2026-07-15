-- ============================================================
-- Demo 链路 A：缺货找替代（01_demo_chain_missing_part.sql）
-- ============================================================
-- 用途: 验证“缺货 -> 找替代料 -> 找供应商 -> 询价/报价”闭环
-- 输入: 原型号 TMK212BJ105KG-T（part_id=21，RFQ-2026-001）产线缺货
-- 期望输出:
--   1) 命中原物料 1 条（TMK212BJ105KG-T）
--   2) 替代料 ≥1 条（CL21B105KAFNNNE，L1 完全等效，confidence≥0.9）
--   3) 覆盖 MLCC + 替代品牌的 approved 供应商 ≥2 家
--   4) RFQ-2026-001 关联供应商 ≥2 家，且已有报价记录
-- 数据依赖: 04_seed_data/04_parts_seed.csv、06_part_alternatives_seed.csv、
--           05_suppliers_seed.csv、10_supplier_capabilities_seed.csv、
--           07_rfqs_seed.csv、12_rfq_suppliers_seed.csv、13_quotations_seed.csv
-- ============================================================

USE pc_industry;

-- 1. 命中原型号
SELECT id, part_number, brand, category_name, specs, lifecycle_status
FROM parts
WHERE part_number = 'TMK212BJ105KG-T';
-- 期望: 1 行，id=21

-- 2. 找替代料（仅取 approved 且 l1/l2，按置信度倒序）
SELECT
  pa.alternative_part_number,
  p.brand,
  p.specs,
  pa.level,
  pa.level_desc,
  pa.confidence,
  pa.risk_note,
  pa.source_name
FROM part_alternatives pa
JOIN parts p ON p.id = pa.alternative_part_id
WHERE pa.original_part_id = 21
  AND pa.review_status = 'approved'
  AND pa.level IN ('l1','l2')
ORDER BY pa.confidence DESC;
-- 期望: 1 行，CL21B105KAFNNNE，l1，confidence≈0.92

-- 3. 找覆盖 MLCC 品类 + 替代料品牌的 approved 供应商能力
SELECT DISTINCT
  s.id AS supplier_id,
  s.name AS supplier_name,
  s.location,
  sc.brand_names,
  sc.moq,
  sc.lead_time_days,
  sc.region
FROM supplier_capabilities sc
JOIN suppliers s ON s.id = sc.supplier_id
WHERE sc.category_id = 1
  AND sc.audit_status = 'approved'
  AND (sc.brand_names LIKE '%Samsung%' OR sc.brand_names LIKE '%Taiyo Yuden%'
       OR sc.brand_names LIKE '%Murata%' OR sc.brand_names LIKE '%YAGEO%')
ORDER BY s.rating DESC;
-- 期望: ≥2 家（立创商城/云汉芯城/Digi-Key 等）

-- 4. 该缺货对应的 RFQ 已推送供应商 + 报价
SELECT
  r.rfq_number,
  r.title,
  r.quantity,
  r.target_price,
  rs.supplier_id,
  s.name AS supplier_name,
  rs.match_score,
  rs.status AS rfq_supplier_status,
  q.part_number AS quoted_part,
  q.unit_price,
  q.lead_time_days,
  q.stock_qty,
  q.is_in_stock
FROM rfqs r
JOIN rfq_suppliers rs ON rs.rfq_id = r.id
JOIN suppliers s ON s.id = rs.supplier_id
LEFT JOIN quotations q ON q.rfq_id = r.id AND q.supplier_id = rs.supplier_id
WHERE r.part_id = 21
ORDER BY rs.match_score DESC;
-- 期望: RFQ-2026-001，≥2 家供应商，≥1 条报价（CL21B105KAFNNNE 报价）
