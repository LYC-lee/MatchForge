-- Purpose: Validate the first batch of industry_segments data after import.
-- Expected input: industry_segments table populated from 04_seed_data/01_industry_segments_seed.csv.
-- Expected result: 15 active level-1 segments, no duplicate segment_code, no invalid chain_position.

-- 1. Count active first-batch segments.
SELECT
  COUNT(*) AS active_segment_count
FROM industry_segments
WHERE data_scope = 'sprint_16h'
  AND is_active = TRUE;

-- Expected: active_segment_count = 15

-- 2. Find duplicate segment_code values.
SELECT
  segment_code,
  COUNT(*) AS duplicate_count
FROM industry_segments
GROUP BY segment_code
HAVING COUNT(*) > 1;

-- Expected: zero rows

-- 3. Find invalid chain_position values.
SELECT
  segment_code,
  chain_position
FROM industry_segments
WHERE chain_position NOT IN ('upstream', 'midstream', 'downstream', 'support');

-- Expected: zero rows

-- 4. Check chain position distribution.
SELECT
  chain_position,
  COUNT(*) AS segment_count
FROM industry_segments
WHERE data_scope = 'sprint_16h'
GROUP BY chain_position
ORDER BY chain_position;

-- Expected:
-- downstream = 2
-- midstream = 3
-- support = 1
-- upstream = 9

-- 5. Confirm 16-hour sprint priority segments exist.
SELECT
  segment_code,
  segment_name_cn,
  chain_position
FROM industry_segments
WHERE segment_code IN (
  'passive_components',
  'memory_storage',
  'connectors_cables',
  'sourcing_distribution',
  'odm_ems_manufacturing'
)
ORDER BY sort_order;

-- Expected: 5 rows
