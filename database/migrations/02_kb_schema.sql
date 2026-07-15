-- ============================================================
-- MatchForge 企业私域知识库 - MySQL 迁移脚本 (非破坏式)
--
-- 用途: 在 MySQL (pc_industry 或独立库) 创建知识库表。
--       SQLite 为默认开发库; 切 MySQL 时设置 KB_DATABASE_URL 后执行本脚本。
-- 非破坏式: 全部为 CREATE TABLE IF NOT EXISTS, 不删除/修改任何现有业务表。
-- 支持 rollback: DROP TABLE IF EXISTS kb_* (见末尾)。
--
-- 执行:
--   mysql -h 127.0.0.1 -u matchforge -p pc_industry < database/migrations/02_kb_schema.sql
-- 或对应你的 KB_DATABASE_URL 所指库。
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_companies (
  id BIGINT PRIMARY KEY COMMENT '= 源 company_id',
  name VARCHAR(200) NOT NULL,
  name_en VARCHAR(200) NULL,
  name_alias VARCHAR(500) NULL,
  country VARCHAR(50) NULL,
  region VARCHAR(50) NULL,
  website VARCHAR(500) NULL,
  description TEXT NULL,
  segment_code VARCHAR(80) NULL,
  segment_name_cn VARCHAR(120) NULL,
  segment_name_en VARCHAR(160) NULL,
  chain_position VARCHAR(20) NULL,
  role VARCHAR(50) NULL,
  typical_products TEXT NULL COMMENT 'JSON',
  business_boundary_json TEXT NULL COMMENT '业务边界 JSON',
  confidence_level VARCHAR(30) NULL,
  source_name VARCHAR(200) NULL,
  source_url VARCHAR(500) NULL,
  knowledge_status VARCHAR(20) NOT NULL DEFAULT 'none',
  last_generated_at DATETIME NULL,
  source_hash VARCHAR(64) NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_kbcomp_segment (segment_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-公司快照';

CREATE TABLE IF NOT EXISTS kb_manuals (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  company_id BIGINT NOT NULL,
  manual_type VARCHAR(20) NOT NULL COMMENT 'product|business',
  language VARCHAR(8) NOT NULL COMMENT 'zh|en',
  title VARCHAR(500) NOT NULL,
  content LONGTEXT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  content_hash VARCHAR(64) NOT NULL,
  source_hash VARCHAR(64) NOT NULL,
  active_version BOOLEAN NOT NULL DEFAULT TRUE,
  generation_status VARCHAR(20) NOT NULL DEFAULT 'completed',
  source_type VARCHAR(30) NOT NULL DEFAULT 'ai_generated_demo',
  source_url VARCHAR(500) NULL,
  source_title VARCHAR(300) NULL,
  generated_by_ai BOOLEAN NOT NULL DEFAULT TRUE,
  confidence FLOAT NOT NULL DEFAULT 0.7,
  generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_manual_active (company_id, manual_type, language, active_version),
  KEY idx_manual_company_type_lang (company_id, manual_type, language)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-手册(Source of Truth)';

CREATE TABLE IF NOT EXISTS kb_products (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  company_id BIGINT NOT NULL,
  product_name VARCHAR(200) NOT NULL,
  product_series VARCHAR(200) NULL,
  product_model VARCHAR(200) NULL,
  category VARCHAR(100) NULL,
  positioning VARCHAR(300) NULL,
  price FLOAT NULL,
  price_min FLOAT NULL,
  price_max FLOAT NULL,
  currency VARCHAR(10) NULL DEFAULT 'USD',
  price_type VARCHAR(20) NULL,
  price_confidence FLOAT NULL,
  specification TEXT NULL COMMENT 'JSON',
  language VARCHAR(8) NOT NULL DEFAULT 'zh',
  source_type VARCHAR(30) NOT NULL DEFAULT 'ai_generated_demo',
  source_hash VARCHAR(64) NULL,
  confidence FLOAT NOT NULL DEFAULT 0.7,
  generated_by_ai BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_product_company_model (company_id, product_model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-结构化产品';

CREATE TABLE IF NOT EXISTS kb_chunks (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  chunk_uid VARCHAR(80) NOT NULL UNIQUE,
  company_id BIGINT NOT NULL,
  manual_id BIGINT NOT NULL,
  manual_type VARCHAR(20) NOT NULL,
  language VARCHAR(8) NOT NULL,
  chunk_type VARCHAR(40) NOT NULL,
  section VARCHAR(200) NULL,
  product_id BIGINT NULL,
  product_model VARCHAR(200) NULL,
  business_type VARCHAR(80) NULL,
  text LONGTEXT NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  source_type VARCHAR(30) NOT NULL DEFAULT 'ai_generated_demo',
  source_url VARCHAR(500) NULL,
  source_file VARCHAR(500) NULL,
  generated_by_ai BOOLEAN NOT NULL DEFAULT TRUE,
  confidence FLOAT NOT NULL DEFAULT 0.7,
  version INT NOT NULL DEFAULT 1,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  vector_synced BOOLEAN NOT NULL DEFAULT FALSE,
  vector_backend VARCHAR(20) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_chunk_retrieval (company_id, language, manual_type, active),
  KEY idx_chunk_product (company_id, product_model, chunk_type),
  KEY idx_chunk_business (company_id, business_type, chunk_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-语义切片';

CREATE TABLE IF NOT EXISTS kb_tasks (
  id VARCHAR(64) PRIMARY KEY,
  company_id BIGINT NULL,
  task_type VARCHAR(30) NOT NULL,
  total_steps INT NOT NULL DEFAULT 0,
  completed_steps INT NOT NULL DEFAULT 0,
  progress INT NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  current_stage VARCHAR(100) NULL,
  error_message TEXT NULL,
  retry_count INT NOT NULL DEFAULT 0,
  checkpoint TEXT NULL COMMENT 'JSON',
  result_summary TEXT NULL COMMENT 'JSON',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  KEY idx_task_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-后台任务';

CREATE TABLE IF NOT EXISTS kb_failures (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  task_id VARCHAR(64) NOT NULL,
  company_id BIGINT NULL,
  company_name VARCHAR(200) NULL,
  generation_stage VARCHAR(80) NULL,
  language VARCHAR(8) NULL,
  manual_type VARCHAR(20) NULL,
  retry_count INT NOT NULL DEFAULT 0,
  error TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_failure_task (task_id),
  KEY idx_failure_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-失败记录';

CREATE TABLE IF NOT EXISTS kb_rag_traces (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  request_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(100) NULL,
  company_id BIGINT NULL,
  company_ids VARCHAR(300) NULL,
  query TEXT NOT NULL,
  detected_language VARCHAR(8) NULL,
  query_intent VARCHAR(20) NULL,
  retrieved_chunk_ids TEXT NULL COMMENT 'JSON',
  retrieval_scores TEXT NULL COMMENT 'JSON',
  manual_versions TEXT NULL,
  source_types TEXT NULL COMMENT 'JSON',
  model VARCHAR(100) NULL,
  answer LONGTEXT NULL,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_trace_request (request_id),
  KEY idx_trace_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-RAG检索追溯';

CREATE TABLE IF NOT EXISTS kb_company_access (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  company_id BIGINT NOT NULL,
  granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_company (user_id, company_id),
  KEY idx_access_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-公司访问白名单';

CREATE TABLE IF NOT EXISTS kb_sessions (
  token VARCHAR(64) PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  name VARCHAR(200) NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  account VARCHAR(100) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_session_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-API会话';

CREATE TABLE IF NOT EXISTS kb_vectors (
  chunk_uid VARCHAR(80) PRIMARY KEY,
  company_id VARCHAR(40) NOT NULL,
  embedding LONGTEXT NOT NULL COMMENT 'JSON float list (Local 向量库降级)',
  meta LONGTEXT NOT NULL COMMENT 'JSON',
  KEY idx_vec_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-本地向量(Local后端, Milvus模式不使用)';

-- ============================================================
-- Rollback (谨慎执行, 仅删除知识库表, 不影响业务表):
--   DROP TABLE IF EXISTS kb_vectors, kb_sessions, kb_company_access,
--     kb_rag_traces, kb_failures, kb_tasks, kb_chunks, kb_products,
--     kb_manuals, kb_companies;
-- ============================================================
