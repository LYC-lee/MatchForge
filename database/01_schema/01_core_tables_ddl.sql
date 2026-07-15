-- ============================================================
-- MatchForge 电脑全链路数据库 - 核心表 DDL（13 张表，合并版）
-- 数据库: pc_industry
-- MySQL 8.0
-- 冲刺: 16 小时数据库底座（10-12h 交付）
-- 关联: 02_field_dictionary/01_field_dictionary.md
-- 规范: NAMING_CONVENTIONS.md（表名复数 snake_case；枚举小写）
--
-- 说明:
--   - industry_segments 的权威定义见 01_industry_segments_ddl.sql（按表拆分版）；
--     本文件保持完全一致，便于一次性建库。CREATE TABLE IF NOT EXISTS 幂等。
--   - id 统一 BIGINT，与 matchforge 库及 industry_segments 对齐。
--   - confidence_level 用 VARCHAR(30) 而非 ENUM，保留扩展空间（对齐命名规范 §6 取值）。
--   - level / status / lifecycle_status / scenario 等稳定枚举仍用 ENUM 校验。
--
-- 执行:
--   mysql -h 127.0.0.1 -u root -p < database/01_schema/01_core_tables_ddl.sql
--   或: docker exec -i matchforge-mysql mysql -u root -pmatchforge123 < database/01_schema/01_core_tables_ddl.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS pc_industry
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE pc_industry;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. industry_segments 产业环节表
--    （与 01_industry_segments_ddl.sql 完全一致；segment_code 为稳定业务键）
-- ============================================================
CREATE TABLE IF NOT EXISTS industry_segments (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  segment_code     VARCHAR(80)  NOT NULL COMMENT '环节业务编码，如 passive_components',
  segment_name_cn  VARCHAR(120) NOT NULL COMMENT '环节中文名',
  segment_name_en  VARCHAR(160) NOT NULL COMMENT '环节英文名',
  chain_position   VARCHAR(20)  NOT NULL COMMENT '链路位置: upstream/midstream/downstream/support',
  parent_code      VARCHAR(80)  NULL     COMMENT '父环节编码（二级环节用）',
  level            TINYINT      NOT NULL DEFAULT 1 COMMENT '层级',
  description      TEXT         NULL     COMMENT '环节说明',
  typical_products JSON         NULL     COMMENT '典型产品 JSON 数组',
  typical_companies JSON        NULL     COMMENT '典型公司 JSON 数组',
  data_scope       VARCHAR(50)  NOT NULL DEFAULT 'sprint_16h' COMMENT '数据范围标记',
  source_name      VARCHAR(120) NOT NULL DEFAULT 'manual_research' COMMENT '数据来源',
  source_url       VARCHAR(500) NULL     COMMENT '来源链接',
  confidence_level VARCHAR(30)  NOT NULL DEFAULT 'manual' COMMENT '可信度: official/authorized/cross_checked/third_party/self_reported/manual/unknown',
  sort_order       INT          NOT NULL DEFAULT 0 COMMENT '排序',
  is_active        BOOLEAN      NOT NULL DEFAULT TRUE COMMENT '是否启用',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_industry_segments_code (segment_code),
  KEY idx_industry_segments_position (chain_position),
  KEY idx_industry_segments_parent (parent_code),
  KEY idx_industry_segments_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='产业环节表（上游/中游/下游/支撑）';

-- ============================================================
-- 2. companies 公司主体表
-- ============================================================
CREATE TABLE IF NOT EXISTS companies (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  name             VARCHAR(200) NOT NULL COMMENT '公司名称',
  name_en          VARCHAR(200) NULL     COMMENT '英文名称',
  name_alias       VARCHAR(500) NULL     COMMENT '别名/简称',
  country          VARCHAR(50)  NULL     COMMENT '国家',
  region           VARCHAR(50)  NULL     COMMENT '地区',
  website          VARCHAR(500) NULL     COMMENT '官网',
  description      TEXT         NULL     COMMENT '公司简介',
  confidence_level VARCHAR(30)  NOT NULL DEFAULT 'unknown' COMMENT '可信度',
  source_name      VARCHAR(200) NULL     COMMENT '数据来源名称',
  source_url       VARCHAR(500) NULL     COMMENT '数据来源链接',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_companies_country (country),
  KEY idx_companies_region (region),
  KEY idx_companies_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公司主体表';

-- ============================================================
-- 3. company_segments 公司-产业环节关系表
--    通过 segment_code 关联 industry_segments（稳定业务键，不依赖自增 id）
-- ============================================================
CREATE TABLE IF NOT EXISTS company_segments (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  company_id    BIGINT       NOT NULL COMMENT '公司ID',
  segment_code  VARCHAR(80)  NOT NULL COMMENT '产业环节编码',
  role          VARCHAR(50)  NULL     COMMENT '角色，如 制造商/分销商/ODM',
  is_primary    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否主要环节',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_cs_company (company_id),
  KEY idx_cs_segment (segment_code),
  CONSTRAINT fk_cs_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
  CONSTRAINT fk_cs_segment FOREIGN KEY (segment_code) REFERENCES industry_segments(segment_code) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公司-产业环节关系表';

-- ============================================================
-- 4. categories 物料品类表
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(50)  NOT NULL UNIQUE COMMENT '品类名称，如 MLCC',
  parent_id   BIGINT       NULL     COMMENT '父品类ID，支持层级',
  description TEXT         NULL     COMMENT '品类说明',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_categories_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物料品类表';

-- ============================================================
-- 5. parts 物料主数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS parts (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  part_number       VARCHAR(100) NOT NULL COMMENT '料号/型号',
  brand             VARCHAR(100) NOT NULL COMMENT '品牌',
  category_id       BIGINT       NOT NULL COMMENT '品类ID',
  category_name     VARCHAR(50)  NOT NULL COMMENT '品类名称（冗余，便于检索）',
  specs             JSON         NULL     COMMENT '规格参数 JSON',
  lifecycle_status  ENUM('active','nrnd','eol','obsolete','unknown') NOT NULL DEFAULT 'active' COMMENT '生命周期',
  datasheet_url     VARCHAR(500) NULL     COMMENT 'Datasheet 链接',
  description       TEXT         NULL     COMMENT '物料描述',
  confidence_level  VARCHAR(30)  NOT NULL DEFAULT 'unknown' COMMENT '可信度',
  source_name       VARCHAR(200) NULL     COMMENT '数据来源名称',
  source_url        VARCHAR(500) NULL     COMMENT '数据来源链接',
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_parts_part_number (part_number),
  KEY idx_parts_category (category_id),
  KEY idx_parts_brand (brand),
  KEY idx_parts_lifecycle (lifecycle_status),
  CONSTRAINT fk_part_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物料主数据表';

-- ============================================================
-- 6. spec_definitions 品类规格字段定义表
-- ============================================================
CREATE TABLE IF NOT EXISTS spec_definitions (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  category_id  BIGINT       NOT NULL COMMENT '品类ID',
  field_name   VARCHAR(50)  NOT NULL COMMENT '字段英文名',
  field_label  VARCHAR(100) NOT NULL COMMENT '字段中文名',
  field_type   ENUM('string','number','enum','boolean') NOT NULL DEFAULT 'string' COMMENT '字段类型',
  unit         VARCHAR(20)  NULL     COMMENT '单位',
  is_required  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否必填',
  enum_values  VARCHAR(500) NULL     COMMENT '枚举值，逗号分隔',
  sort_order   INT          NOT NULL DEFAULT 0 COMMENT '排序',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_spec_category (category_id),
  CONSTRAINT fk_spec_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='品类规格字段定义表';

-- ============================================================
-- 7. suppliers 供应商主体表
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  company_id    BIGINT       NULL     COMMENT '关联公司ID',
  name          VARCHAR(200) NOT NULL COMMENT '供应商名称',
  location      VARCHAR(100) NULL     COMMENT '所在地',
  rating        DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '评分 0-5',
  status        ENUM('pending','approved','rejected','needs_review') NOT NULL DEFAULT 'pending' COMMENT '审核状态',
  contact_phone VARCHAR(50)  NULL     COMMENT '联系电话',
  contact_email VARCHAR(100) NULL     COMMENT '联系邮箱',
  source_name   VARCHAR(200) NULL     COMMENT '数据来源',
  source_url    VARCHAR(500) NULL     COMMENT '来源链接',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_suppliers_status (status),
  KEY idx_suppliers_company (company_id),
  CONSTRAINT fk_supplier_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='供应商主体表';

-- ============================================================
-- 8. supplier_capabilities 供应商能力表
-- ============================================================
CREATE TABLE IF NOT EXISTS supplier_capabilities (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id    BIGINT       NOT NULL COMMENT '供应商ID',
  category_id    BIGINT       NOT NULL COMMENT '品类ID',
  category_name  VARCHAR(50)  NOT NULL COMMENT '品类名称（冗余）',
  brand_names    VARCHAR(500) NULL     COMMENT '代理/覆盖品牌，逗号分隔',
  moq            INT          NULL     COMMENT '最小起订量',
  lead_time_days INT          NULL     COMMENT '交期（天）',
  region         VARCHAR(100) NULL     COMMENT '供货区域',
  audit_status   ENUM('pending','approved','rejected','needs_review') NOT NULL DEFAULT 'pending' COMMENT '审核状态',
  audit_note     TEXT         NULL     COMMENT '审核备注',
  source_name    VARCHAR(200) NULL     COMMENT '数据来源',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_cap_supplier (supplier_id),
  KEY idx_cap_category (category_id),
  CONSTRAINT fk_cap_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
  CONSTRAINT fk_cap_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='供应商能力表';

-- ============================================================
-- 9. part_alternatives 替代料关系表
-- ============================================================
CREATE TABLE IF NOT EXISTS part_alternatives (
  id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
  original_part_id        BIGINT       NOT NULL COMMENT '原物料ID',
  alternative_part_id     BIGINT       NOT NULL COMMENT '替代物料ID',
  original_part_number    VARCHAR(100) NOT NULL COMMENT '原型号（冗余）',
  alternative_part_number VARCHAR(100) NOT NULL COMMENT '替代型号（冗余）',
  level                   ENUM('l1','l2','l3','l4','l5') NOT NULL DEFAULT 'l3' COMMENT '替代等级',
  level_desc              VARCHAR(100) NULL     COMMENT '等级描述',
  confidence              DECIMAL(3,2) NOT NULL DEFAULT 0.80 COMMENT '置信度 0-1',
  param_diff              TEXT         NULL     COMMENT '参数差异说明',
  risk_note               TEXT         NULL     COMMENT '风险说明',
  source_name             VARCHAR(200) NULL     COMMENT '数据来源',
  source_url              VARCHAR(500) NULL     COMMENT '来源链接',
  review_status           ENUM('pending','approved','rejected','needs_review') NOT NULL DEFAULT 'pending' COMMENT '审核状态',
  reviewed_by             VARCHAR(50)  NULL     COMMENT '审核人',
  reviewed_at             DATETIME     NULL     COMMENT '审核时间',
  created_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_alt_original (original_part_id),
  KEY idx_alt_alternative (alternative_part_id),
  KEY idx_alt_original_level_review (original_part_id, level, review_status),
  CONSTRAINT fk_alt_original FOREIGN KEY (original_part_id) REFERENCES parts(id) ON DELETE CASCADE,
  CONSTRAINT fk_alt_alternative FOREIGN KEY (alternative_part_id) REFERENCES parts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='替代料关系表（L1-L5 等级）';

-- ============================================================
-- 10. rfqs RFQ 询价单表
-- ============================================================
CREATE TABLE IF NOT EXISTS rfqs (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_number          VARCHAR(50)  NOT NULL UNIQUE COMMENT '询价单号',
  title               VARCHAR(200) NULL     COMMENT '询价标题',
  raw_query           TEXT         NULL     COMMENT '原始需求描述',
  part_id             BIGINT       NULL     COMMENT '目标物料ID',
  part_number         VARCHAR(100) NULL     COMMENT '目标料号（冗余）',
  quantity            INT          NULL     COMMENT '需求数量',
  unit                VARCHAR(20)  NOT NULL DEFAULT 'pcs' COMMENT '单位',
  target_price        DECIMAL(12,4) NULL    COMMENT '目标单价（USD）',
  lead_time_weeks     INT          NULL     COMMENT '期望交期（周）',
  accept_alternatives TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否接受替代料',
  scenario            ENUM('stockout','cost_reduction','new_sourcing') NOT NULL DEFAULT 'stockout' COMMENT '场景',
  status              ENUM('draft','sent','quoted','closed','cancelled') NOT NULL DEFAULT 'draft' COMMENT '状态',
  created_by          VARCHAR(50)  NULL     COMMENT '创建人',
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_rfqs_status (status),
  KEY idx_rfqs_scenario (scenario),
  KEY idx_rfqs_part (part_id),
  CONSTRAINT fk_rfq_part FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RFQ 询价单表';

-- ============================================================
-- 11. rfq_suppliers RFQ-供应商关联表
-- ============================================================
CREATE TABLE IF NOT EXISTS rfq_suppliers (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_id       BIGINT       NOT NULL COMMENT 'RFQ ID',
  supplier_id  BIGINT       NOT NULL COMMENT '供应商ID',
  match_score  DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '匹配分数 0-1',
  match_reason TEXT         NULL     COMMENT '匹配原因',
  status       ENUM('pending','sent','responded','declined') NOT NULL DEFAULT 'pending' COMMENT '状态',
  sent_at      DATETIME     NULL     COMMENT '发送时间',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rfq_suppliers_rfq (rfq_id),
  KEY idx_rfq_suppliers_supplier (supplier_id),
  KEY idx_rfq_suppliers_rfq_score (rfq_id, match_score),
  CONSTRAINT fk_rs_rfq FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE,
  CONSTRAINT fk_rs_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RFQ-供应商关联表';

-- ============================================================
-- 12. quotations 报价记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS quotations (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_id         BIGINT       NOT NULL COMMENT 'RFQ ID',
  supplier_id    BIGINT       NOT NULL COMMENT '供应商ID',
  part_number    VARCHAR(100) NULL     COMMENT '报价料号（可为替代料号）',
  unit_price     DECIMAL(12,4) NOT NULL COMMENT '单价（USD）',
  moq            INT          NULL     COMMENT '最小起订量',
  lead_time_days INT          NULL     COMMENT '报价交期（天）',
  stock_qty      INT          NULL     COMMENT '库存数量',
  valid_until    DATE         NULL     COMMENT '报价有效期',
  is_in_stock    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否有库存',
  note           TEXT         NULL     COMMENT '备注',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_quotations_rfq (rfq_id),
  KEY idx_quotations_supplier (supplier_id),
  KEY idx_quotations_rfq_supplier (rfq_id, supplier_id),
  CONSTRAINT fk_quot_rfq FOREIGN KEY (rfq_id) REFERENCES rfqs(id) ON DELETE CASCADE,
  CONSTRAINT fk_quot_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报价记录表';

-- ============================================================
-- 13. data_sources 数据来源表
-- ============================================================
CREATE TABLE IF NOT EXISTS data_sources (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  name         VARCHAR(200) NOT NULL COMMENT '来源名称',
  type         ENUM('official','industry_report','news','marketplace','internal') NOT NULL DEFAULT 'official' COMMENT '来源类型',
  url          VARCHAR(500) NULL     COMMENT '来源链接',
  reliability  ENUM('high','medium','low') NOT NULL DEFAULT 'medium' COMMENT '可靠性',
  last_checked DATE         NULL     COMMENT '最后核实日期',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_data_sources_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据来源表';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 验证：13 张表已创建
-- SELECT table_name, table_comment
-- FROM information_schema.tables
-- WHERE table_schema = 'pc_industry' ORDER BY table_name;
-- 期望: 13 行
-- ============================================================
