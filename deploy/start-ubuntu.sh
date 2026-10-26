#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
if [[ ! -f .env ]]; then
    echo 'Copy .env.example to .env and configure PostgreSQL and the public origin first.' >&2
    exit 2
fi
if [[ ! -x .venv/bin/python || ! -f frontend/dist/index.html ]]; then
    bash deploy/setup-ubuntu.sh
fi
.venv/bin/python server/app.py --env-file .env --check-db
exec .venv/bin/python server/app.py --env-file .env "$@"
