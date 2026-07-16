-- ============================================================
-- MatchForge 驾驶舱 Phase2: 企业经营数据表 (追加式, 不修改 02_kb_schema.sql)
--
-- 与 Phase1 一致, 复用 KB 数据库 (SQLite 自动建表, MySQL 执行本文件)。
-- 全部 CREATE TABLE IF NOT EXISTS, 幂等可重入。
-- 表前缀 kb_ 与知识库表对齐, 不触碰 pc_industry 业务库。
-- ============================================================

-- 10. 当前企业生产的产品 (产能/状态)
CREATE TABLE IF NOT EXISTS kb_company_products (
    id                BIGINT NOT NULL AUTO_INCREMENT,
    company_id        BIGINT NOT NULL,
    product_name      VARCHAR(200) NOT NULL,
    product_model     VARCHAR(200) NULL,
    product_type      VARCHAR(80) NULL,
    description       TEXT NULL,
    monthly_capacity  INT NULL COMMENT '月产能',
    unit              VARCHAR(20) NOT NULL DEFAULT '台',
    status            VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'active|paused|eol',
    created_at        DATETIME NOT NULL,
    updated_at        DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_cprod_company_status (company_id, status),
    INDEX idx_cprod_model (product_model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11. 产品 BOM 零件
CREATE TABLE IF NOT EXISTS kb_product_bom_items (
    id                              BIGINT NOT NULL AUTO_INCREMENT,
    product_id                      BIGINT NOT NULL COMMENT 'CompanyProduct.id',
    part_number                     VARCHAR(120) NOT NULL,
    part_name                       VARCHAR(200) NOT NULL,
    category_name                   VARCHAR(120) NULL,
    qty_per_unit                    DOUBLE NOT NULL DEFAULT 1.0 COMMENT '单台用量',
    unit                            VARCHAR(20) NOT NULL DEFAULT '个',
    is_critical                     TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否关键件',
    preferred_supplier_company_id   BIGINT NULL COMMENT '首选上游供应商企业ID',
    created_at                      DATETIME NOT NULL,
    updated_at                      DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_bom_product (product_id),
    INDEX idx_bom_part (part_number),
    INDEX idx_bom_product_part (product_id, part_number),
    INDEX idx_bom_supplier (preferred_supplier_company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 12. 生产订单
CREATE TABLE IF NOT EXISTS kb_production_orders (
    id                  BIGINT NOT NULL AUTO_INCREMENT,
    company_id          BIGINT NOT NULL,
    product_id          BIGINT NOT NULL,
    order_number        VARCHAR(80) NOT NULL,
    customer_company_id BIGINT NULL,
    quantity            INT NOT NULL,
    due_date            DATETIME NULL,
    priority            VARCHAR(20) NOT NULL DEFAULT 'normal' COMMENT 'urgent|high|normal|low',
    status              VARCHAR(20) NOT NULL DEFAULT 'open' COMMENT 'open|confirmed|in_progress|completed|cancelled',
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_order_company_status (company_id, status, priority),
    INDEX idx_order_product (product_id),
    INDEX idx_order_number (order_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 13. 预测需求
CREATE TABLE IF NOT EXISTS kb_demand_forecasts (
    id                BIGINT NOT NULL AUTO_INCREMENT,
    company_id        BIGINT NOT NULL,
    product_id        BIGINT NOT NULL,
    forecast_period   VARCHAR(20) NOT NULL COMMENT '如 2026-08',
    forecast_quantity INT NOT NULL,
    confidence        DOUBLE NOT NULL DEFAULT 0.7,
    source_type       VARCHAR(30) NOT NULL DEFAULT 'manual',
    created_at        DATETIME NOT NULL,
    updated_at        DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_forecast_company_product (company_id, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 14. 库存 (企业 × 零件号)
CREATE TABLE IF NOT EXISTS kb_inventory_items (
    id                BIGINT NOT NULL AUTO_INCREMENT,
    company_id        BIGINT NOT NULL,
    part_number       VARCHAR(120) NOT NULL,
    part_name         VARCHAR(200) NULL,
    category_name     VARCHAR(120) NULL,
    on_hand_qty       INT NOT NULL DEFAULT 0,
    reserved_qty      INT NOT NULL DEFAULT 0,
    safety_stock_qty  INT NOT NULL DEFAULT 0,
    updated_at        DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_inv_company_part (company_id, part_number),
    INDEX idx_inv_part (part_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 15. 缺件/库存预警 (recalculate 物化)
CREATE TABLE IF NOT EXISTS kb_shortages (
    id                              BIGINT NOT NULL AUTO_INCREMENT,
    company_id                      BIGINT NOT NULL,
    product_id                      BIGINT NULL,
    product_name                    VARCHAR(300) NULL,
    part_number                     VARCHAR(120) NOT NULL,
    part_name                       VARCHAR(200) NOT NULL,
    category_name                   VARCHAR(120) NULL,
    shortage_type                   VARCHAR(20) NOT NULL COMMENT 'shortage|warning',
    required_qty                    DOUBLE NOT NULL DEFAULT 0.0,
    available_qty                   DOUBLE NOT NULL DEFAULT 0.0,
    shortage_qty                    DOUBLE NOT NULL DEFAULT 0.0,
    safety_stock_qty                INT NOT NULL DEFAULT 0,
    unit                            VARCHAR(20) NOT NULL DEFAULT '个',
    is_critical                     TINYINT(1) NOT NULL DEFAULT 0,
    severity                        VARCHAR(20) NOT NULL DEFAULT 'medium',
    status                          VARCHAR(20) NOT NULL DEFAULT 'open',
    preferred_supplier_company_id   BIGINT NULL,
    relationship_missing            TINYINT(1) NOT NULL DEFAULT 0,
    affected_order_numbers          TEXT NULL COMMENT 'JSON 数组',
    affected_product_ids            TEXT NULL COMMENT 'JSON 数组',
    created_at                      DATETIME NOT NULL,
    updated_at                      DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_shortage_company_type (company_id, shortage_type, status),
    INDEX idx_shortage_part (part_number),
    INDEX idx_shortage_supplier (preferred_supplier_company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
