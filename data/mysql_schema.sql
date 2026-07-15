-- ════════════════════════════════════════════════════════════
-- MatchForge - MySQL 建表脚本 (P4 数据层)
-- 负责人: P4 (数据/知识库工程师)
-- 版本: v1.2 (对齐系统架构文档 v1.2)
-- 用途: 创建业务数据表结构，供种子数据导入使用
-- 注: matchforge 库由 deploy/docker-compose.yml 自动创建（MYSQL_DATABASE=matchforge），
--     故此处不再 CREATE DATABASE，使 matchforge 用户（仅持 matchforge.* 权限）也能加载本脚本。
-- ════════════════════════════════════════════════════════════

USE matchforge;

-- ── 企业（采购方与供应方共用）──
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS rfqs;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS qualifications;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS buyers;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS enterprises;
DROP TABLE IF EXISTS material_dictionary;
DROP TABLE IF EXISTS categories;

CREATE TABLE enterprises (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL COMMENT '企业名称',
    type VARCHAR(20) NOT NULL COMMENT 'buyer=采购方/supplier=供应方',
    credit_code VARCHAR(50) COMMENT '统一社会信用代码',
    contact VARCHAR(100) COMMENT '联系方式',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业表';

-- ── 用户（采购/供应端账号；MVP 引入，Spike 期寻源可匿名）──
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(128) NOT NULL COMMENT 'bcrypt 密码哈希',
    enterprise_id BIGINT COMMENT '关联企业',
    role VARCHAR(20) NOT NULL COMMENT 'buyer/supplier/admin',
    email VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_enterprise (enterprise_id),
    CONSTRAINT fk_user_ent FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ── 采购档案（下游，关联企业）──
CREATE TABLE buyers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    enterprise_id BIGINT NOT NULL,
    industry VARCHAR(50) COMMENT '所属行业',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_buyer_ent FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购档案表';

-- ── 供应商（上游）──
CREATE TABLE suppliers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    enterprise_id BIGINT COMMENT '关联企业',
    name VARCHAR(200) NOT NULL COMMENT '供应商名称',
    location VARCHAR(100) COMMENT '所在地',
    rating DECIMAL(3,2) DEFAULT 0 COMMENT '评分 0-5',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending=待审核/approved=已认证/rejected=已拒绝',
    main_category VARCHAR(100) COMMENT '主营品类',
    contact_phone VARCHAR(50) COMMENT '联系电话',
    contact_email VARCHAR(100) COMMENT '联系邮箱',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_location (location),
    INDEX idx_category (main_category),
    CONSTRAINT fk_supplier_ent FOREIGN KEY (enterprise_id) REFERENCES enterprises(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商表';

-- ── 资质证照（F7 核验，独立表）──
CREATE TABLE qualifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    supplier_id BIGINT NOT NULL,
    type VARCHAR(50) NOT NULL COMMENT 'ISO9001/IATF16949/营业执照...',
    cert_no VARCHAR(100) COMMENT '证书编号',
    file_url TEXT COMMENT '对象存储地址',
    status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending=待核验/verified=已核验/rejected=已驳回',
    verified_at DATETIME COMMENT '核验时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_supplier (supplier_id),
    CONSTRAINT fk_qual_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资质证照表';

-- ── 品类字典（支持层级）──
CREATE TABLE categories (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '品类名称: MLCC电容/贴片电阻/二极管...',
    parent_id BIGINT COMMENT '父品类（支持层级）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品类字典表';

-- ── 供应商产品（向量在 Milvus，替代关系在 Neo4j）──
CREATE TABLE products (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    supplier_id BIGINT,
    category VARCHAR(50) NOT NULL COMMENT '品类（对应 categories.name）',
    part_number VARCHAR(100) NOT NULL COMMENT '料号',
    brand VARCHAR(100) COMMENT '品牌',
    specs JSON COMMENT '标准化规格参数（中文键名）',
    datasheet_url TEXT COMMENT 'Datasheet 链接',
    moq INT COMMENT '最小起订量',
    lead_time_weeks INT COMMENT '交期(周)',
    price DECIMAL(12,4) COMMENT '单价(USD)',
    in_stock BOOLEAN DEFAULT TRUE COMMENT '是否有库存',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_part (part_number),
    INDEX idx_category (category),
    INDEX idx_supplier (supplier_id),
    INDEX idx_brand (brand),
    CONSTRAINT fk_product_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商产品表';

-- ── 标准字典（F3 标准化用）──
CREATE TABLE material_dictionary (
    std_code VARCHAR(100) PRIMARY KEY COMMENT '标准编码 如 MLCC-0805-X7R-50V-103',
    category VARCHAR(50) NOT NULL COMMENT '品类（中文）',
    params JSON COMMENT '参数（中文键名）',
    standard VARCHAR(100) COMMENT '标准 GB/IEC/EIA/JIS',
    description TEXT COMMENT '中文描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准物料字典表';

-- ── 询价单（F9）──
CREATE TABLE rfqs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    buyer_id BIGINT COMMENT '采购方ID',
    thread_id VARCHAR(64) COMMENT '多轮会话标识',
    raw_query TEXT COMMENT '原始自然语言需求',
    parsed_spec JSON COMMENT 'AI解析后的结构化规格',
    normalized_spec JSON COMMENT '标准化规格',
    alternatives JSON COMMENT '替代料结果',
    rfq_doc TEXT COMMENT '询价单文本',
    status VARCHAR(20) DEFAULT 'draft' COMMENT 'draft=草稿/sent=已发送/quoted=已报价/closed=已关闭',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_buyer (buyer_id),
    CONSTRAINT fk_rfq_buyer FOREIGN KEY (buyer_id) REFERENCES buyers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='询价单表';

-- ── 线索（上游视角，F6 分级）──
CREATE TABLE leads (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    rfq_id BIGINT,
    supplier_id BIGINT,
    grade VARCHAR(2) COMMENT '分级 A/B/C/D',
    score INT COMMENT '评分 0-100',
    reasons JSON COMMENT '分级原因（中文）',
    status VARCHAR(20) DEFAULT 'new' COMMENT 'new=新线索/contacted=已联系/won=已成交/lost=已流失',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_supplier (supplier_id),
    CONSTRAINT fk_lead_rfq FOREIGN KEY (rfq_id) REFERENCES rfqs(id),
    CONSTRAINT fk_lead_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售线索表';
