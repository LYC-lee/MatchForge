-- 06_enterprise_type.sql
-- ============================================================================
-- P1 注册身份模型: 取消注册时固化 buyer/supplier, 改为"企业类型 + 用户权限角色"。
--   - 用户权限角色 (users.role): member / enterprise_admin / platform_admin
--   - 企业类型 (users.enterprise_type): manufacturer / component_material / oem_brand /
--     channel_customer / logistics_service / government_park / other
--   - 供需角色由订单 / RFQ / BOM / 服务关系动态派生, 不在注册时固化。
--
-- 非破坏式: 仅新增列, 不删除/修改现有列, 不改写历史数据。
-- 影响表: users (matchforge 运营库)。
-- 可重复执行: 否 (MySQL ADD COLUMN 不支持 IF NOT EXISTS); 首次执行前请确认列不存在。
--   * 全新库由 Base.metadata.create_all 自动建表时已包含 enterprise_type, 无需执行本迁移。
--   * 本迁移仅用于已存在的 users 表补列 (历史库)。
-- ============================================================================

ALTER TABLE users
  ADD COLUMN enterprise_type VARCHAR(40) NOT NULL DEFAULT 'other'
  COMMENT '企业类型: manufacturer/component_material/oem_brand/channel_customer/logistics_service/government_park/other';

-- 说明: users.role 列已存在, 应用层 default 已改为 'member'。
-- 历史数据不自动改写 (避免影响 demo 种子 role="buyer" 与现有会话)。
-- 如需统一历史用户为 member 权限角色, 可手动执行:
--   UPDATE users SET role = 'member' WHERE role IN ('buyer', 'supplier');
