-- supplier_capabilities 表 (从 02_pc_industry_schema.sql 提取)
-- 创建到 matchforge 库，供 mysql_client.py 的 filter_suppliers_raw 使用
-- 注意: 去掉了外键约束 (fk_cap_category) 避免依赖问题

CREATE TABLE IF NOT EXISTS supplier_capabilities (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id    BIGINT       NOT NULL COMMENT '供应商ID',
  category_id    BIGINT       NOT NULL DEFAULT 0 COMMENT '品类ID',
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
  KEY idx_cap_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='供应商能力表';
