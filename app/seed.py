"""
Database seeder — idempotent.
Run once after `alembic upgrade head` (or create_all) to populate:
  - roles: employee, agent, admin
  - default admin user
"""

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.auth import hash_password
from app.models import Role, RoleNameEnum, User


DEFAULT_ADMIN_EMAIL = "admin@helpdesk.com"
DEFAULT_ADMIN_PASSWORD = "Admin1234"  # Change in production!


def seed_roles(db: Session) -> dict[RoleNameEnum, Role]:
    roles: dict[RoleNameEnum, Role] = {}
    for name in RoleNameEnum:
        existing = db.query(Role).filter(Role.name == name).first()
        if not existing:
            role = Role(name=name, description=name.value.capitalize())
            db.add(role)
            db.flush()
            roles[name] = role
        else:
            roles[name] = existing
    return roles


def seed_admin(db: Session, admin_role: Role) -> User:
    existing = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
    if existing:
        return existing

    admin = User(
        role_id=admin_role.id,
        full_name="System Admin",
        email=DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        is_active=True,
    )
    db.add(admin)
    db.flush()
    return admin


def run_seed(db: Session) -> None:
    roles = seed_roles(db)
    seed_admin(db, roles[RoleNameEnum.admin])
    db.commit()
    print("✅  Seed complete. Default admin:", DEFAULT_ADMIN_EMAIL)


if __name__ == "__main__":
    from app.database import SessionLocal
    with SessionLocal() as session:
        run_seed(session)
