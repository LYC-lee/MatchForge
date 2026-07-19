-- ============================================================
-- MatchForge 演示场景沙盘 (demo scenario sandbox) - MySQL 迁移
--
-- 用途: 切 MySQL 时创建演示场景相关表。SQLite 为默认开发库, init_db() 自动建表。
-- 非破坏式: 全部 CREATE TABLE IF NOT EXISTS, 不删除/修改任何现有业务表。
--
-- 设计原则:
--   - 所有演示变化 (订单/库存/RFQ/报价/事件/动作日志) 都带 scenario_id。
--   - 原始基线数据 (kb_production_orders/kb_inventory_items/kb_rfqs/...) 不被污染。
--   - 重置场景只删除该 scenario_id 下的演示数据 (见末尾 reset 注释)。
--
-- 执行:
--   mysql -h 127.0.0.1 -u matchforge -p matchforge < database/migrations/05_demo_scenario.sql
-- 或对应你的 KB_DATABASE_URL 所指库。
-- ============================================================

CREATE TABLE IF NOT EXISTS demo_scenarios (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id         VARCHAR(64)  NOT NULL UNIQUE COMMENT '场景标识 如 default_mvp_demo',
  name                VARCHAR(200) NOT NULL,
  description         LONGTEXT     NULL,
  status              VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT 'active|archived|reset',
  primary_company_ids LONGTEXT     NULL COMMENT 'JSON 数组: 可登录主视角企业ID',
  config_json         LONGTEXT     NULL COMMENT '场景配置 JSON',
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_demo_scn_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示场景沙盘';

CREATE TABLE IF NOT EXISTS demo_events (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id         VARCHAR(64)  NOT NULL,
  seq                 INT          NOT NULL COMMENT '全局递增序号, 排序用',
  phase               VARCHAR(40)  NULL COMMENT '分阶段按钮标识',
  action_log_id       BIGINT       NULL COMMENT '触发该事件的动作日志ID',
  company_id          BIGINT       NOT NULL COMMENT '事件主体企业ID',
  company_name        VARCHAR(200) NULL,
  linked_company_id   BIGINT       NULL COMMENT '联动企业ID (上游/下游/支撑)',
  linked_company_name VARCHAR(200) NULL,
  event_type          VARCHAR(60)  NOT NULL,
  title               VARCHAR(300) NOT NULL,
  detail              LONGTEXT     NULL,
  payload_json        LONGTEXT     NULL COMMENT '结构化载荷 JSON',
  parent_event_id     BIGINT       NULL COMMENT '父事件ID (因果链)',
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_demo_event_scenario_seq (scenario_id, seq),
  KEY idx_demo_event_company (scenario_id, company_id),
  KEY idx_demo_event_action (action_log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示事件日志 (因果链)';

CREATE TABLE IF NOT EXISTS demo_action_logs (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id   VARCHAR(64)  NOT NULL,
  company_id    BIGINT       NOT NULL COMMENT '操作的主视角企业',
  action_type   VARCHAR(60)  NOT NULL,
  request_json  LONGTEXT     NULL,
  result_json   LONGTEXT     NULL COMMENT '动作结果摘要 JSON',
  event_ids_json LONGTEXT    NULL COMMENT '产生的事件ID列表 JSON',
  status        VARCHAR(20)  NOT NULL DEFAULT 'success' COMMENT 'success|partial|failed|no_direct_supplier',
  message       LONGTEXT     NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_demo_action_scenario (scenario_id, company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示动作执行日志';

CREATE TABLE IF NOT EXISTS demo_company_states (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id   VARCHAR(64)  NOT NULL,
  company_id    BIGINT       NOT NULL,
  company_name  VARCHAR(200) NULL,
  is_primary    BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '是否可登录主视角企业',
  role          VARCHAR(50)  NULL,
  chain_position VARCHAR(20) NULL,
  state_json    LONGTEXT     NULL COMMENT '聚合状态 JSON',
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_demo_state_company (scenario_id, company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示企业状态快照';

CREATE TABLE IF NOT EXISTS demo_inventory_overrides (
  id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id        VARCHAR(64)  NOT NULL,
  company_id         BIGINT       NOT NULL,
  part_number        VARCHAR(120) NOT NULL,
  part_name          VARCHAR(200) NULL,
  category_name      VARCHAR(120) NULL,
  baseline_on_hand   INT          NOT NULL DEFAULT 0,
  baseline_reserved  INT          NOT NULL DEFAULT 0,
  safety_stock_qty   INT          NOT NULL DEFAULT 0,
  consumed_qty       INT          NOT NULL DEFAULT 0 COMMENT '演示消耗量',
  replenished_qty    INT          NOT NULL DEFAULT 0 COMMENT '演示补货量',
  unit               VARCHAR(20)  NOT NULL DEFAULT '个',
  source             VARCHAR(40)  NULL COMMENT 'consume_inventory|execute_replenishment|select_alternative',
  updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_demo_inv_override (scenario_id, company_id, part_number),
  KEY idx_demo_inv_company (scenario_id, company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示库存增量 (消耗/补货)';

CREATE TABLE IF NOT EXISTS demo_orders (
  id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id           VARCHAR(64)  NOT NULL,
  company_id            BIGINT       NOT NULL COMMENT '生产方(主视角)企业',
  product_id            BIGINT       NOT NULL,
  product_name          VARCHAR(200) NULL,
  order_number          VARCHAR(80)  NOT NULL COMMENT 'DEMO-ORD-...',
  customer_company_id   BIGINT       NULL COMMENT '下游客户企业ID',
  customer_company_name VARCHAR(200) NULL,
  quantity              INT          NOT NULL,
  due_date              DATETIME     NULL,
  priority              VARCHAR(20)  NOT NULL DEFAULT 'normal',
  status                VARCHAR(20)  NOT NULL DEFAULT 'open' COMMENT 'open|confirmed|in_progress|completed|cancelled',
  event_id              BIGINT       NULL COMMENT '关联事件ID',
  created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_demo_order_company_status (company_id, status),
  KEY idx_demo_order_scenario (scenario_id, company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示生成订单 (场景内)';

CREATE TABLE IF NOT EXISTS demo_rfqs (
  id                          BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id                 VARCHAR(64)  NOT NULL,
  company_id                  BIGINT       NOT NULL COMMENT '买方(主视角)企业',
  rfq_number                  VARCHAR(64)  NOT NULL COMMENT 'DEMO-RFQ-...',
  title                       VARCHAR(300) NOT NULL,
  part_number                 VARCHAR(200) NULL,
  part_name                   VARCHAR(200) NULL,
  quantity                    INT          NOT NULL DEFAULT 1,
  unit                        VARCHAR(20)  NOT NULL DEFAULT '个',
  target_price                FLOAT        NULL,
  lead_time_days              INT          NULL,
  accept_alternatives         BOOLEAN      NOT NULL DEFAULT FALSE,
  scenario                    VARCHAR(40)  NULL COMMENT 'shortage|sourcing|cost_down',
  status                      VARCHAR(20)  NOT NULL DEFAULT 'draft' COMMENT 'draft|sent|quoted|closed|cancelled',
  candidates_json             LONGTEXT     NULL COMMENT 'JSON: 直接关系候选供应商列表',
  selected_supplier_company_id BIGINT      NULL,
  shortage_event_id           BIGINT       NULL COMMENT '触发改 RFQ 的缺件事件ID',
  event_id                    BIGINT       NULL COMMENT 'RFQ 创建事件ID',
  created_at                  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at                  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_demo_rfq_company_status (company_id, status),
  KEY idx_demo_rfq_scenario (scenario_id, company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示询价单 (场景内)';

CREATE TABLE IF NOT EXISTS demo_quotations (
  id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
  scenario_id           VARCHAR(64)  NOT NULL,
  rfq_id                BIGINT       NOT NULL,
  supplier_company_id   BIGINT       NOT NULL,
  supplier_name         VARCHAR(200) NULL,
  part_number           VARCHAR(200) NULL,
  unit_price            FLOAT        NOT NULL COMMENT '报价单价',
  currency              VARCHAR(10)  NOT NULL DEFAULT 'CNY',
  moq                   INT          NULL,
  lead_time_days        INT          NULL COMMENT '报价交期(天)',
  stock_qty             INT          NULL,
  is_in_stock           BOOLEAN      NOT NULL DEFAULT FALSE,
  note                  LONGTEXT     NULL,
  event_id              BIGINT       NULL COMMENT '报价事件ID',
  created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_demo_quote_supplier (rfq_id, supplier_company_id),
  KEY idx_demo_quote_rfq (rfq_id),
  KEY idx_demo_quote_scenario (scenario_id, rfq_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='演示供应商报价 (场景内)';

-- ============================================================
-- 重置场景 (仅删除 default_mvp_demo 演示数据, 不触碰基线业务表):
--   DELETE FROM demo_quotations     WHERE scenario_id = 'default_mvp_demo';
--   DELETE FROM demo_rfqs           WHERE scenario_id = 'default_mvp_demo';
--   DELETE FROM demo_orders         WHERE scenario_id = 'default_mvp_demo';
--   DELETE FROM demo_inventory_overrides WHERE scenario_id = 'default_mvp_demo';
--   DELETE FROM demo_events         WHERE scenario_id = 'default_mvp_demo';
--   DELETE FROM demo_action_logs    WHERE scenario_id = 'default_mvp_demo';
--   DELETE FROM demo_company_states WHERE scenario_id = 'default_mvp_demo';
-- (POST /api/v1/demo/scenarios/reset 接口已封装上述操作)
--
-- Rollback (仅删除演示场景表, 不影响知识库/业务表):
--   DROP TABLE IF EXISTS demo_quotations, demo_rfqs, demo_orders,
--     demo_inventory_overrides, demo_events, demo_action_logs,
--     demo_company_states, demo_scenarios;
-- ============================================================
