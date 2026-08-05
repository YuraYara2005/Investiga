"""Unit tests for Identity Domain SQLAlchemy 2.0 Models and Relationships."""

import uuid

from sqlalchemy import inspect

from app.auth.models import (
    Permission,
    Role,
    User,
    role_permissions,
    user_roles,
)


def test_user_model_instantiation_and_defaults() -> None:
    user = User(
        email="analyst@investiga.internal",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        full_name="Incident Analyst",
    )

    assert user.email == "analyst@investiga.internal"
    assert user.full_name == "Incident Analyst"
    assert user.is_active is True
    assert user.is_verified is False
    assert user.is_superuser is False
    assert user.is_deleted is False
    assert user.deleted_at is None
    assert user.tenant_id is None
    assert user.last_login_at is None
    assert isinstance(user.id, uuid.UUID) or user.id is None
    assert repr(user) == "<User id=None email='analyst@investiga.internal' active=True superuser=False>"


def test_role_model_instantiation_and_defaults() -> None:
    role = Role(
        name="incident_responder",
        display_name="Incident Responder",
        description="First-line operational incident investigator.",
    )

    assert role.name == "incident_responder"
    assert role.display_name == "Incident Responder"
    assert role.is_system_role is False
    assert role.is_deleted is False
    assert role.tenant_id is None
    assert repr(role) == "<Role id=None name='incident_responder' system=False>"


def test_permission_model_instantiation() -> None:
    perm = Permission(
        code="investigations:create",
        resource="investigations",
        action="create",
        description="Create new operational incident investigation workspaces.",
    )

    assert perm.code == "investigations:create"
    assert perm.resource == "investigations"
    assert perm.action == "create"
    assert "investigations:create" in repr(perm)


def test_user_role_permission_aggregation_and_properties() -> None:
    # 1. Create permissions
    perm_read = Permission(
        code="investigations:read",
        resource="investigations",
        action="read",
    )
    perm_write = Permission(
        code="investigations:write",
        resource="investigations",
        action="write",
    )
    perm_ai = Permission(
        code="ai:query",
        resource="ai",
        action="query",
    )

    # 2. Create roles and endow permissions
    role_responder = Role(
        name="responder",
        display_name="Responder",
        is_deleted=False,
    )
    role_responder.permissions = [perm_read, perm_write]

    role_ai_user = Role(
        name="ai_operator",
        display_name="AI Operator",
        is_deleted=False,
    )
    role_ai_user.permissions = [perm_ai]

    role_deprecated = Role(
        name="legacy_role",
        display_name="Legacy Role",
        is_deleted=True,  # Soft-deleted
    )
    role_deprecated.permissions = [
        Permission(code="legacy:admin", resource="legacy", action="admin")
    ]

    # 3. Create user and assign roles
    user = User(
        email="operator@investiga.internal",
        hashed_password="hash",
        full_name="Lead Operator",
    )
    user.roles = [role_responder, role_ai_user, role_deprecated]

    # 4. Verify aggregated role names excludes soft-deleted roles
    assert sorted(user.role_names) == ["ai_operator", "responder"]

    # 5. Verify aggregated permission codes excludes soft-deleted roles
    assert user.permission_codes == {
        "investigations:read",
        "investigations:write",
        "ai:query",
    }
    assert "legacy:admin" not in user.permission_codes


def test_association_tables_foreign_keys_and_constraints() -> None:
    # Verify user_roles junction table
    assert user_roles.name == "user_roles"
    user_roles_cols = {col.name: col for col in user_roles.columns}
    assert "user_id" in user_roles_cols
    assert "role_id" in user_roles_cols
    assert "assigned_at" in user_roles_cols
    assert "assigned_by" in user_roles_cols
    assert user_roles_cols["user_id"].primary_key is True
    assert user_roles_cols["role_id"].primary_key is True

    # Verify foreign key cascade rules
    user_fk = next(iter(user_roles_cols["user_id"].foreign_keys))
    assert user_fk.target_fullname == "users.id"
    assert user_fk.ondelete == "CASCADE"

    role_fk = next(iter(user_roles_cols["role_id"].foreign_keys))
    assert role_fk.target_fullname == "roles.id"
    assert role_fk.ondelete == "CASCADE"

    # Verify role_permissions junction table
    assert role_permissions.name == "role_permissions"
    role_perms_cols = {col.name: col for col in role_permissions.columns}
    assert "role_id" in role_perms_cols
    assert "permission_id" in role_perms_cols
    assert "granted_at" in role_perms_cols
    assert role_perms_cols["role_id"].primary_key is True
    assert role_perms_cols["permission_id"].primary_key is True

    perm_fk = next(iter(role_perms_cols["permission_id"].foreign_keys))
    assert perm_fk.target_fullname == "permissions.id"
    assert perm_fk.ondelete == "CASCADE"


def test_table_metadata_and_declarative_tables() -> None:
    assert User.__tablename__ == "users"
    assert Role.__tablename__ == "roles"
    assert Permission.__tablename__ == "permissions"

    # Verify column existence on User mapper
    user_mapper = inspect(User)
    user_column_names = {c.key for c in user_mapper.column_attrs}
    expected_user_cols = {
        "id",
        "email",
        "hashed_password",
        "full_name",
        "is_active",
        "is_verified",
        "is_superuser",
        "last_login_at",
        "tenant_id",
        "created_at",
        "updated_at",
        "is_deleted",
        "deleted_at",
    }
    assert expected_user_cols.issubset(user_column_names)
