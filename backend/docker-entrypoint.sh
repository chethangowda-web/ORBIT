#!/bin/sh
# Container entrypoint: migrate, optionally seed, then exec the server.
set -e

echo "[entrypoint] applying database migrations"
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] seeding initial data"
  python -m db.seed
fi

exec "$@"
