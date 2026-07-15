-- ============================================================
-- MatchForge 缺件采购闭环 (RFQ / 供应商线索 / 报价 / 审核) - MySQL 迁移
--
-- 用途: 切 MySQL 时创建闭环相关表。SQLite 为默认开发库, init_db() 自动建表。
-- 非破坏式: 全部 CREATE TABLE IF NOT EXISTS, 不删除/修改任何现有表。
-- 支持 rollback: DROP TABLE IF EXISTS kb_audit_queue, kb_quotations,
--   kb_rfq_suppliers, kb_rfqs; (见末尾)
--
-- 执行:
--   mysql -h 127.0.0.1 -u matchforge -p pc_industry < database/migrations/03_rfq_supplier_loop.sql
-- 或对应你的 KB_DATABASE_URL 所指库。
-- ============================================================

CREATE TABLE IF NOT EXISTS kb_rfqs (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_number          VARCHAR(64)  NOT NULL UNIQUE COMMENT '业务编号 RFQ-YYYY-NNNN',
  buyer_company_id    BIGINT       NOT NULL COMMENT '买方公司ID',
  title               VARCHAR(300) NOT NULL,
  raw_query           LONGTEXT     NULL COMMENT '原始用户询价文本',
  part_number         VARCHAR(200) NULL,
  part_name           VARCHAR(200) NULL,
  quantity            INT          NOT NULL DEFAULT 1,
  unit                VARCHAR(20)  NOT NULL DEFAULT '个',
  target_price        FLOAT        NULL COMMENT '目标单价',
  lead_time_days      INT          NULL COMMENT '期望交期(天)',
  accept_alternatives BOOLEAN      NOT NULL DEFAULT FALSE,
  scenario            VARCHAR(40)  NULL COMMENT 'shortage|sourcing|cost_down|...',
  status              VARCHAR(20)  NOT NULL DEFAULT 'draft' COMMENT 'draft|sent|quoted|closed|cancelled',
  created_by          VARCHAR(100) NULL COMMENT '创建人 user_id',
  context_json        LONGTEXT     NULL COMMENT 'Phase2 兼容字段 JSON',
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_rfq_buyer_status (buyer_company_id, status),
  KEY idx_rfq_number (rfq_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-询价单';

CREATE TABLE IF NOT EXISTS kb_rfq_suppliers (
  id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_id               BIGINT       NOT NULL,
  supplier_company_id  BIGINT       NOT NULL,
  match_score          FLOAT        NULL COMMENT '匹配分 0-1',
  match_reason         LONGTEXT     NULL COMMENT '匹配理由',
  status               VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending|sent|viewed|quoted|declined|expired',
  sent_at              DATETIME     NULL,
  viewed_at            DATETIME     NULL,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_rfq_supplier (rfq_id, supplier_company_id),
  KEY idx_rfq_supplier_status (supplier_company_id, status),
  KEY idx_rfq_suppliers_rfq (rfq_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-RFQ供应商线索';

CREATE TABLE IF NOT EXISTS kb_quotations (
  id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
  rfq_id               BIGINT       NOT NULL,
  supplier_company_id  BIGINT       NOT NULL,
  part_number          VARCHAR(200) NULL,
  unit_price           FLOAT        NOT NULL COMMENT '报价单价',
  currency             VARCHAR(10)  NOT NULL DEFAULT 'CNY',
  moq                  INT          NULL COMMENT '最小起订量',
  lead_time_days       INT          NULL COMMENT '报价交期(天)',
  stock_qty            INT          NULL COMMENT '现货库存',
  valid_until          DATETIME     NULL COMMENT '报价有效期',
  is_in_stock          BOOLEAN      NOT NULL DEFAULT FALSE,
  note                 LONGTEXT     NULL,
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_quote_rfq_supplier (rfq_id, supplier_company_id),
  KEY idx_quote_supplier (supplier_company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-供应商报价';

CREATE TABLE IF NOT EXISTS kb_audit_queue (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  item_type     VARCHAR(40)  NOT NULL COMMENT 'supplier_capability|rfq_supplier_match|quotation_anomaly',
  entity_id     BIGINT       NULL COMMENT '关联实体ID',
  company_id    BIGINT       NULL,
  title         VARCHAR(300) NOT NULL,
  payload_json  LONGTEXT     NULL COMMENT '审核上下文 JSON',
  status        VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending|approved|rejected',
  review_note   LONGTEXT     NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at   DATETIME     NULL,
  KEY idx_audit_status_type (status, item_type),
  KEY idx_audit_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库-审核队列';

-- ============================================================
-- Rollback (谨慎执行, 仅删除闭环表, 不影响知识库/业务表):
--   DROP TABLE IF EXISTS kb_audit_queue, kb_quotations,
--     kb_rfq_suppliers, kb_rfqs;
-- ============================================================
