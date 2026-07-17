"""
P1 注册身份模型 - 防回归测试。

校验注册身份模型重构:
- RegisterRequest 默认权限角色为 member (不再 buyer/supplier)
- RegisterRequest 接受 enterprise_type 字段
- User 模型包含 enterprise_type 列
- 自注册用户权限角色与供需角色解耦 (供需角色由业务关系动态派生)
"""

from __future__ import annotations


def test_register_request_defaults_role_to_member():
    """注册请求默认权限角色应为 member, 而非 buyer。"""
    from api.schemas import RegisterRequest

    req = RegisterRequest(name="李明", account="liming@hx.com", password="abc12345", company="华芯")
    assert req.role == "member"
    assert req.enterprise_type == "other"


def test_register_request_accepts_enterprise_type():
    """注册请求应接受企业类型字段。"""
    from api.schemas import RegisterRequest

    req = RegisterRequest(
        name="李明",
        account="liming@hx.com",
        password="abc12345",
        company="华芯",
        role="member",
        enterprise_type="component_material",
    )
    assert req.enterprise_type == "component_material"
    assert req.role == "member"


def test_user_model_has_enterprise_type_column():
    """User 模型应包含 enterprise_type 列 (供需角色动态派生, 不在注册时固化)。"""
    from api.models import User

    cols = {c.name for c in User.__table__.columns}
    assert "enterprise_type" in cols
    assert "role" in cols


def test_register_request_does_not_force_buyer_supplier():
    """注册请求默认角色不应是 buyer/supplier (供需角色由业务关系动态派生)。"""
    from api.schemas import RegisterRequest

    req = RegisterRequest(name="x", account="x@y.com", password="abc12345", company="c")
    assert req.role not in ("buyer", "supplier")
