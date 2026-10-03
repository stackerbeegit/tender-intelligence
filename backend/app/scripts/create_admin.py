"""
One-off CLI to bootstrap the first admin user, since there's no open
registration-to-admin path (by design — see RBAC in docs/architecture.md).

Usage:
    python -m app.scripts.create_admin --email you@stackerbee.com --password <strong-password> --name "Your Name"
"""
import argparse
import sys

from app.core.database import SessionLocal
from app.core.exceptions import DomainError
from app.schemas.user import UserCreate
from app.services import auth_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Stackerbee Admin")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = auth_service.register_user(
            db,
            UserCreate(email=args.email, password=args.password, full_name=args.name, role_name="admin"),
        )
        print(f"Created admin user: {user.email} (id={user.id})")
    except DomainError as exc:
        print(f"Failed to create admin user: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
