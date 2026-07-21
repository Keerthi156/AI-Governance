"""
Bootstrap local PostgreSQL: create role + database for AI_GOVERNANCE.

Why this script exists:
- Avoids using the superuser password in the app .env long-term.
- Creates a dedicated role/database matching backend/.env DATABASE_URL.

Usage (PowerShell, from backend/):
  .\\.venv\\Scripts\\python.exe scripts\\bootstrap_postgres.py --admin-password YOUR_POSTGRES_PASSWORD

Requires: PostgreSQL listening on --port (default 5432).
"""

from __future__ import annotations

import argparse
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap AI_GOVERNANCE Postgres DB")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument(
        "--admin-password",
        required=True,
        help="Password for the PostgreSQL superuser (postgres)",
    )
    parser.add_argument("--app-user", default="ai_governance")
    parser.add_argument("--app-password", default="ai_governance_dev")
    parser.add_argument("--app-db", default="ai_governance")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            user=args.admin_user,
            password=args.admin_password,
            dbname="postgres",
        )
    except psycopg2.Error as exc:
        print(f"ERROR: cannot connect as {args.admin_user}: {exc}", file=sys.stderr)
        print(
            "Tip: use the password you set when installing PostgreSQL.",
            file=sys.stderr,
        )
        return 1

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (args.app_user,))
    if cur.fetchone() is None:
        cur.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(args.app_user),
                sql.Literal(args.app_password),
            )
        )
        print(f"Created role: {args.app_user}")
    else:
        cur.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(args.app_user),
                sql.Literal(args.app_password),
            )
        )
        print(f"Updated password for role: {args.app_user}")

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (args.app_db,))
    if cur.fetchone() is None:
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(args.app_db),
                sql.Identifier(args.app_user),
            )
        )
        print(f"Created database: {args.app_db}")
    else:
        print(f"Database already exists: {args.app_db}")

    cur.execute(
        sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
            sql.Identifier(args.app_db),
            sql.Identifier(args.app_user),
        )
    )

    cur.close()
    conn.close()

    # Grant schema privileges inside the app database (Postgres 15+).
    app_conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.admin_user,
        password=args.admin_password,
        dbname=args.app_db,
    )
    app_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    app_cur = app_conn.cursor()
    app_cur.execute(
        sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(args.app_user))
    )
    app_cur.execute(
        sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(args.app_user))
    )
    app_cur.close()
    app_conn.close()

    print()
    print("Bootstrap complete. Set backend/.env DATABASE_URL to:")
    print(
        f"DATABASE_URL=postgresql+psycopg2://{args.app_user}:{args.app_password}"
        f"@{args.host}:{args.port}/{args.app_db}"
    )
    print()
    print("Then run: alembic upgrade head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
