-- 07_user_name_company.sql
-- ============================================================================
-- P1 auth 路由修复: User 模型补 name/company 列。
--   - login/refresh/me 路由响应引用 user.name/user.company, 缺列会 AttributeError
--   - database.py 演示种子 User(name=, company=) 缺列会 TypeError (全新库 seed)
--   - 注册路由据 req.name/req.company 持久化到 User
-- 补列后 auth 全链路可用; company 为展示用字符串, enterprise_id 仍为关联企业 FK(可空)。
--
-- 非破坏式: 仅新增列, 不删除/修改现有列, 不改写历史数据。
-- 影响表: users (matchforge 运营库)。
-- 可重复执行: 否 (MySQL ADD COLUMN 不支持 IF NOT EXISTS); 首次执行前请确认列不存在。
--   * 全新库由 Base.metadata.create_all 自动建表时已含 name/company, 无需执行本迁移。
--   * 本迁移仅用于已存在的 users 表补列 (历史库)。
-- ============================================================================

ALTER TABLE users
  ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT '' COMMENT '用户姓名(展示用)';

ALTER TABLE users
  ADD COLUMN company VARCHAR(200) NOT NULL DEFAULT '' COMMENT '企业名称(展示用; 关联企业见 enterprise_id)';

-- 说明: 不自动回填历史用户的 name/company (留空默认 ''), 不影响现有登录。
-- demo 种子 (api/database.py) 的 name="Demo Buyer" / company="MatchForge Demo" 在新建时会正确写入。
