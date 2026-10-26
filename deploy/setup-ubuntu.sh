#!/usr/bin/env bash
set -euo pipefail

# Install project dependencies as the current user; never change system packages or databases.
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -f .env ]]; then
    echo 'Copy .env.example to .env and configure PostgreSQL before setup.' >&2
    exit 2
fi
command -v python3 >/dev/null || { echo 'Python 3.11+ is required.' >&2; exit 1; }
command -v npm >/dev/null || { echo 'Node.js 22.12+ and npm are required to build the viewer.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r server/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python server/app.py --env-file .env --check-db
echo 'Setup finished. Initialize the administrator once, then run bash deploy/start-ubuntu.sh.'
