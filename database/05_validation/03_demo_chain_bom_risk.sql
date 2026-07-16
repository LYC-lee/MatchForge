-- ============================================================
-- Demo 链路 C：BOM 风险预演（03_demo_chain_bom_risk.sql）
-- ============================================================
-- 用途: 验证“逐行匹配 BOM -> 缺失标记 unknown -> 替代建议 -> 供应风险”闭环
-- 输入: 10 行样例 BOM（含 1 个不存在的料号、1 个无替代的单源料号）
-- 期望输出: 每行给出 命中状态/替代建议数量/供应商源数/风险等级
-- 风险等级规则:
--   missing       -- BOM 料号在 parts 中找不到
--   no_alternative -- 命中但无 approved 替代料（单点风险）
--   single_source -- 有替代但 approved 供应商仅 1 家（单源风险）
--   ok            -- 有替代且 approved 供应商 ≥2 家
-- 说明: 用内联 VALUES 临时表模拟 10 行 BOM，不建 BOM 表（本轮范围外）。
-- ============================================================

USE pc_industry;

WITH bom AS (
  SELECT 1 AS line, 'GRM188R71H104KA93D' AS part_number, 100000 AS qty
  UNION ALL SELECT 2, 'CL10B104KB8NNNC', 100000
  UNION ALL SELECT 3, 'TMK212BJ105KG-T', 100000
  UNION ALL SELECT 4, 'RC0603FR-0710KL', 200000
  UNION ALL SELECT 5, 'XH2.54-2P', 50000
  UNION ALL SELECT 6, 'SS34', 20000
  UNION ALL SELECT 7, 'AO3400A', 15000
  UNION ALL SELECT 8, 'CL31A106KAHNNSN', 30000
  UNION ALL SELECT 9, 'NONEXISTENT-PART-001', 5000
  UNION ALL SELECT 10, '0603WAF4700T5E', 100000
),
alt_cnt AS (
  -- 每个原物料的 approved 替代料数量
  SELECT original_part_id, COUNT(*) AS alt_count
  FROM part_alternatives
  WHERE review_status = 'approved'
  GROUP BY original_part_id
),
src_cnt AS (
  -- 每个品类的 approved 供应商数量（供应源数）
  SELECT category_id, COUNT(DISTINCT supplier_id) AS supplier_count
  FROM supplier_capabilities
  WHERE audit_status = 'approved'
  GROUP BY category_id
)
SELECT
  b.line,
  b.part_number AS bom_pn,
  b.qty,
  p.id AS part_id,
  p.brand,
  p.category_name,
  COALESCE(ac.alt_count, 0) AS approved_alt_count,
  COALESCE(sc.supplier_count, 0) AS approved_supplier_count,
  CASE
    WHEN p.id IS NULL THEN 'missing'
    WHEN COALESCE(ac.alt_count, 0) = 0 THEN 'no_alternative'
    WHEN COALESCE(sc.supplier_count, 0) <= 1 THEN 'single_source'
    ELSE 'ok'
  END AS risk_level,
  CASE
    WHEN p.id IS NULL THEN 'BOM 料号未入库，需人工补录'
    WHEN COALESCE(ac.alt_count, 0) = 0 THEN '无 approved 替代料，单点缺料风险'
    WHEN COALESCE(sc.supplier_count, 0) <= 1 THEN '仅 1 家 approved 供应商，单源风险'
    ELSE '替代料充足且多源可选'
  END AS risk_note
FROM bom b
LEFT JOIN parts p ON p.part_number = b.part_number
LEFT JOIN alt_cnt ac ON ac.original_part_id = p.id
LEFT JOIN src_cnt sc ON sc.category_id = p.category_id
ORDER BY b.line;
-- 期望:
--   line 1-6: ok（有替代 + 多源）
--   line 7 (AO3400A, MOSFET): single_source（仅 supplier 8 覆盖 MOSFET）
--   line 8 (CL31A106KAHNNSN): no_alternative（无 approved 替代料）
--   line 9 (NONEXISTENT): missing
--   line 10 (0603WAF4700T5E): no_alternative（无 approved 替代料）

-- 附：列出 line 8 / line 10 的潜在替代（包含 needs_review，供人工评估）
SELECT
  pa.original_part_number,
  pa.alternative_part_number,
  pa.level,
  pa.confidence,
  pa.review_status,
  pa.risk_note
FROM part_alternatives pa
WHERE pa.original_part_id IN (16, 32)
ORDER BY pa.original_part_id, pa.confidence DESC;
-- 期望: 0 行（这两颗确实没有替代记录，佐证 no_alternative 风险）
