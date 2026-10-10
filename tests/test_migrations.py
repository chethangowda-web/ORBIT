"""Migrations must build the same schema the models declare."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def _alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=db_url, SCHEDULER_JOBSTORE="memory")
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_migrations_apply_cleanly_and_match_models(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'schema.db'}"
    upgrade = _alembic(url, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr[-800:]

    check = _alembic(url, "check")
    assert check.returncode == 0, "Models and migrations have drifted:\n" + (check.stdout + check.stderr)[-1500:]


def test_latest_migration_is_reversible(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'roundtrip.db'}"
    assert _alembic(url, "upgrade", "head").returncode == 0
    assert _alembic(url, "downgrade", "-1").returncode == 0
    assert _alembic(url, "upgrade", "head").returncode == 0
