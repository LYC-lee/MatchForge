-- Purpose: Create the industry_segments table for the 16-hour database sprint.
-- Scope: Defines computer industry chain segments used by companies, categories, and supplier capabilities.

CREATE TABLE IF NOT EXISTS industry_segments (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  segment_code VARCHAR(80) NOT NULL,
  segment_name_cn VARCHAR(120) NOT NULL,
  segment_name_en VARCHAR(160) NOT NULL,
  chain_position VARCHAR(20) NOT NULL,
  parent_code VARCHAR(80) NULL,
  level TINYINT NOT NULL DEFAULT 1,
  description TEXT NULL,
  typical_products JSON NULL,
  typical_companies JSON NULL,
  data_scope VARCHAR(50) NOT NULL DEFAULT 'sprint_16h',
  source_name VARCHAR(120) NOT NULL DEFAULT 'manual_research',
  source_url VARCHAR(500) NULL,
  confidence_level VARCHAR(30) NOT NULL DEFAULT 'manual',
  sort_order INT NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_industry_segments_code (segment_code),
  KEY idx_industry_segments_position (chain_position),
  KEY idx_industry_segments_parent (parent_code),
  KEY idx_industry_segments_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
