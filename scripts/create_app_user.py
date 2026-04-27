#!/usr/bin/env python3
"""Create a row in app_user (Argon2 password).

Working directory must be **dmrb/dmrb-legacy** (the folder that contains ``scripts/``).
If your shell prompt is already ``.../dmrb-legacy``, do not run ``cd dmrb/dmrb-legacy`` again.

Requires: ``pip install -r requirements.txt`` (provides ``argon2-cffi``) and ``DATABASE_URL``.

Example (from repo root):

  cd dmrb/dmrb-legacy && DATABASE_URL=postgresql://... python3 scripts/create_app_user.py --username admin --role admin
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert an app_user with hashed password.")
    parser.add_argument("--username", required=True, help="Login name (stored lowercased)")
    parser.add_argument(
        "--role",
        required=True,
        choices=("admin", "mga210"),
        help="admin = full app access; validator = W/O Validator only",
    )
    parser.add_argument(
        "--password",
        default="",
        help="If omitted, password is read interactively (recommended)",
    )
    args = parser.parse_args()

    try:
        import argon2  # noqa: F401
    except ImportError:
        print(
            "Missing argon2. Run from dmrb/dmrb-legacy:\n"
            "  python3 -m pip install -r requirements.txt\n"
            "or: python3 -m pip install argon2-cffi",
            file=sys.stderr,
        )
        return 1

    from db.migration_runner import ensure_database_ready
    from db.repository import user_repository
    from services.auth_service import hash_password

    ensure_database_ready()
    pwd = args.password or getpass.getpass("Password: ")
    if not pwd:
        print("Password cannot be empty.", file=sys.stderr)
        return 1
    ph = hash_password(pwd)
    row = user_repository.insert(args.username, ph, args.role)
    print(
        f"Created app_user user_id={row['user_id']} username={row['username']} role={row['role']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
