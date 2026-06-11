"""Create or update an API user (run once per account).

Usage (from backend/):
    python scripts/create_user.py staff@authority.gov.vn --role admin

The password is read from the AQUASIGNAL_NEW_USER_PASSWORD environment
variable, or prompted interactively (never passed on the command line, where
it would land in shell history and process listings).
"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from core.database import SessionFactory, engine  # noqa: E402
from core.security import hash_password  # noqa: E402
from models.db import User  # noqa: E402


async def upsert_user(email: str, password: str, role: str, full_name: str) -> str:
    async with SessionFactory() as session:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            existing.hashed_password = hash_password(password)
            existing.role = role
            existing.is_active = True
            if full_name:
                existing.full_name = full_name
            action = "updated"
        else:
            session.add(
                User(
                    email=email,
                    hashed_password=hash_password(password),
                    role=role,
                    full_name=full_name,
                )
            )
            action = "created"
        await session.commit()
    await engine.dispose()
    return action


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument(
        "--role", default="field_officer", choices=["field_officer", "admin"]
    )
    parser.add_argument("--full-name", default="")
    args = parser.parse_args()

    password = os.environ.get("AQUASIGNAL_NEW_USER_PASSWORD") or getpass.getpass(
        "Password for new user: "
    )
    if len(password) < 12:
        raise SystemExit("Refusing: password must be at least 12 characters.")
    if len(password.encode("utf-8")) > 72:
        raise SystemExit("Refusing: bcrypt caps passwords at 72 bytes.")

    action = asyncio.run(upsert_user(args.email, password, args.role, args.full_name))
    print(f"User {args.email} {action}.")


if __name__ == "__main__":
    main()
