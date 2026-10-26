# blockchainLedger

A small React website and Python API for public, SHA-256-linked ledgers. Anyone
can browse a ledger, open its blocks and download an encrypted snapshot. Sign in
to create a ledger and receive its private write token. One administrator manages
ledger metadata, availability and deletion.

Records live in a local PostgreSQL database. This is a centralized application,
not distributed consensus: hashes reveal inconsistent records and links, but do
not prove that submitted information is truthful or prevent a database owner from
rebuilding all history. Keep a trusted chain-head fingerprint outside the server
when you need to detect a complete rewrite.

## Accounts and permissions

| Action | Visitor | Ledger creator | Administrator |
| --- | --- | --- | --- |
| List and view ledgers, download and validate snapshots | Yes | Yes | Yes |
| Create a ledger | Sign in first | Yes | Yes |
| See integration details or rotate a ledger's write token | No | Own ledger only | Only if also its creator |
| Append a block through the API | Valid bearer token required | Valid bearer token required | Valid bearer token required |
| Edit name/description, change state or delete a ledger | No | No | Yes |
| Rewrite saved blocks or change an established schema | No | No | No |

Ordinary accounts use self-registration. Passwords are hashed; browser login uses
an HTTP-only session cookie. Browser account/ledger changes require a CSRF token.
Write tokens belong in an API client's secret configuration, not frontend source,
URLs or Git. The full write token is shown at creation/rotation; store it safely.
Rotating it invalidates the previous token.

Integration details are hidden from visitors in the UI and owner-only API.
Endpoint names are not a security boundary: append requests are authorized using
the bearer token even if someone discovers the route.

States are **active**, **read_only** and **archived**. Only an active ledger accepts
new blocks. Read-only and archived ledgers remain publicly inspectable. Deletion
removes that ledger's stored records and encryption key; it is not an undo action.

## Create a ledger and define its blocks

The home screen offers **View ledgers** or **Log in**. Visitors can choose any
listed ledger. After login, the account view lists ledgers created by that user;
the administrator's view lists all ledgers.

Choose a name, description and field list before creating a ledger. Each field
has a name, type and required flag. Supported types are `string`, `integer`,
`boolean`, `object` and `array`. For example:

```json
[
  { "name": "winner", "type": "string", "required": true },
  { "name": "scores", "type": "array", "required": true },
  { "name": "duration_seconds", "type": "integer", "required": true }
]
```

Creation generates the genesis block and fixes the schema. Later submissions
must satisfy it; fields and existing block contents cannot be edited afterward.
Objects and arrays accept the project's supported JSON values, rather than an
additional nested field designer. Fractional values must be represented as scaled
integers. The canonical JSON format intentionally rejects floating-point values,
unsafe-range integers, duplicate keys and excessive nesting.

## Local setup on Windows

Requirements:

- Python 3.11 or newer, with `python` available in the terminal.
- Node.js 22.12 or newer and npm for building the React frontend.
- A local PostgreSQL server and a dedicated application database/user.

Create the PostgreSQL role and database once using pgAdmin or PostgreSQL's tools.
Use a normal login role that owns the application database, not a PostgreSQL
superuser. Then, from this project directory:

```powershell
Copy-Item .env.example .env
```

Edit `.env`: set `LEDGER_DATABASE_URL` to the local database and its password.
Percent-encode reserved URL characters in the password. The example's
`CHANGE_ME` is a placeholder. Keep `.env` private; it is ignored by Git.
Explicit process environment variables take priority over values in `.env`.

For first-time administrator creation only, set `LEDGER_ADMIN_USERNAME` and
`LEDGER_ADMIN_PASSWORD` in `.env`, then run:

```powershell
.\Start Ledger.bat --init-admin
```

This prepares `.venv`, installs pinned Python requirements, builds the viewer if
its build is missing, checks PostgreSQL and runs the requested command. Remove
`LEDGER_ADMIN_PASSWORD` from `.env` after initialization. Ordinary startup does not
overwrite the administrator or reset its password.
Usernames use 3–32 letters, numbers, underscores or hyphens; passwords contain
12–128 characters.

Start the website by double-clicking **Start Ledger.bat** or running:

```powershell
.\Start Ledger.bat
```

For local development the example configuration serves
`http://127.0.0.1:8000`. The Python process serves both the built React viewer and
the API. Stop it with Ctrl+C. After frontend changes, rebuild explicitly:

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

The separate **Start Demo Ledger.bat** launcher requests explicit demo seeding.
Set `LEDGER_ADMIN_USERNAME` to the initialized administrator's name first. It
creates the designated demo ledger only if absent; normal startup inserts no
sample results and does not need administrator credentials in the environment.

## Local setup on Ubuntu

Install PostgreSQL and Python prerequisites if they are not already installed:

```bash
sudo apt update
sudo apt install postgresql postgresql-client python3 python3-venv python3-pip
```

Use Python 3.11+ and install Node.js 22.12+ with npm separately if the distribution
version is older. See the [official Node.js downloads](https://nodejs.org/en/download).

Create the application role/database once. `--pwprompt` keeps the password out of
the shell command; these commands do not replace an existing role/database:

```bash
sudo -u postgres createuser --pwprompt ledger_app
sudo -u postgres createdb --owner=ledger_app blockchain_ledger
cp .env.example .env
chmod 600 .env
```

Edit `.env` with the same role password and database name, then run setup as your
ordinary user:

```bash
bash deploy/setup-ubuntu.sh
```

Setup creates a project virtual environment, installs pinned Python dependencies,
runs `npm ci` and builds the viewer, then checks PostgreSQL. It does not install
system packages, change PostgreSQL users or replace data.

Set the first administrator username/password in `.env`, initialize once, and
remove its password from the environment file afterward:

```bash
.venv/bin/python server/app.py --env-file .env --init-admin
bash deploy/start-ubuntu.sh
```

After pulling application updates, run `bash deploy/setup-ubuntu.sh` again to
reinstall locked dependencies and rebuild. The start script runs setup only if
the virtual environment or frontend build is missing.

## HTTPS with your certificate

No certificate or private key is included in the repository. Supply your actual
certificate chain and matching private key later. Set these values in `.env`:

```ini
LEDGER_BIND=0.0.0.0
LEDGER_PORT=8443
LEDGER_ALLOWED_HOSTS=ledger.example.com
LEDGER_PUBLIC_ORIGIN=https://ledger.example.com:8443
LEDGER_TLS_CERT=/etc/blockchainLedger/fullchain.pem
LEDGER_TLS_KEY=/etc/blockchainLedger/private.key
LEDGER_DEV_MODE=false
LEDGER_SECURE_COOKIES=true
```

Replace the hostname and paths. The certificate must cover the hostname visitors
use, and their devices must trust its issuing CA. A private CA requires installing
its CA certificate on those devices; do not work around trust failures by disabling
certificate verification. Keep the private key readable only by the service
account and its administrator.

Start the same script. Python terminates TLS directly; the viewer and API share
the configured HTTPS origin. `LEDGER_PUBLIC_ORIGIN` must exactly match the browser's
scheme, hostname and port. `LEDGER_ALLOWED_HOSTS` is a comma-separated host list,
without schemes or ports. Use one canonical public origin for login.

The built-in server is intended for this small deployment. Do not place an HTTPS
reverse proxy in front of it without also configuring trusted origin and cookie
handling; arbitrary forwarded headers must not be trusted.

An optional `deploy/blockchain-ledger.service` example runs an already prepared
installation at `/opt/blockchainLedger` as an unprivileged `ledger` user. Create
that account, adjust the paths and give it read access to `.env` and the TLS key
before installing the unit. Use an unprivileged port such as 8443. The example
does not create accounts, databases, certificates or firewall/router rules.

```bash
sudo cp deploy/blockchain-ledger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blockchain-ledger
sudo journalctl -u blockchain-ledger -f
```

## Append through the creator's API

The creator receives a per-ledger path and a bearer token when the ledger is
created. Use the displayed path, rather than the old shared `/api/blocks` route.
The request still contains an idempotent record identifier called `match_id` for
compatibility with the original data format; it need not describe a game match.

```http
POST /api/ledgers/LEDGER_ID/blocks HTTP/1.1
Host: ledger.example.com:8443
Authorization: Bearer YOUR_PRIVATE_WRITE_TOKEN
Content-Type: application/json

{
  "match_id": "RECORD-001",
  "data": { "winner": "Team 1", "scores": [8, 5], "duration_seconds": 180 }
}
```

Send it over the configured HTTPS origin. A new record returns HTTP 201. Retrying
the same identifier and data returns the existing block with HTTP 200; different
data for that identifier produces a conflict. Invalid schema data, invalid tokens
and writes to a non-active ledger are rejected without appending.

The server owns indexes, timestamps, previous hashes and record hashes. The token
authorizes submission but does not establish that a reported score or other fact
is true. Requests are bounded; no endpoint edits saved block contents.

Browser routes include:

| Route | Purpose |
| --- | --- |
| `GET /api/me` | Current login and CSRF token |
| `POST /api/register`, `POST /api/login`, `POST /api/logout` | Account/session operations |
| `GET /api/ledgers` | Public ledger listing |
| `GET /api/my-ledgers` | Own ledgers, or all for the administrator |
| `POST /api/ledgers` | Create a ledger with its immutable field schema |
| `GET /api/ledgers/ID` | Public block history and verification |
| `GET /api/ledgers/ID/snapshot` | Encrypted chain download; `?block=N` selects one block |
| `POST /api/ledgers/ID/validate-snapshot` | Compare an encrypted file with that ledger |
| `GET /api/ledgers/ID/credentials` | Creator-only integration details |
| `POST /api/ledgers/ID/rotate-token` | Creator-only token replacement |
| `PATCH /api/ledgers/ID`, `DELETE /api/ledgers/ID` | Administrator metadata/state changes or deletion |

GFX integration needs a separate client adapter update for the new ledger ID,
bearer token and HTTPS URL. The old Windows GFX uploader uses an unauthenticated
HTTP endpoint and cannot automatically publish to this new API. This ledger
upgrade does not change GFX gameplay or its source code.

## Snapshots and visible verification

Every ledger has its own randomly generated encryption key. All use the same
vetted authenticated encryption algorithm, Fernet; independent keys provide
isolation, rather than inventing a different encryption algorithm for each ledger.
Keys stay server-side in PostgreSQL and are never returned to browsers or API
clients. A snapshot from one ledger cannot be authenticated using another's key.

Visitors can download the whole chain or one block. Uploading a `.ledger` file
checks its authenticity, the saved hashes/links and its records against the
current server. It does not import or overwrite anything.

The chain's verification display distinguishes:

- **Green — verified:** this block was in the saved file and matches.
- **Red — changed/missing:** an authenticated saved record differs from current
  history, is missing, or fails a hash/link check. The report identifies the index.
- **Red, labelled not in snapshot:** this block was not included in the file,
  such as a newer append. This is not evidence of tampering.

A file that fails encryption authentication cannot reliably identify a changed
block. It is reported as an untrusted/changed file without inventing an index.
Comparison is refreshed or cleared when the ledger changes so old green results
are not shown as a fresh verdict. Files are limited to 8 MiB.

## PostgreSQL storage and backups

`LEDGER_DATABASE_URL` selects a local PostgreSQL database. Shared tables hold
accounts, sessions and the ledger registry. Each ledger gets separate block and
secret-key tables, using server-generated identifiers rather than user-provided
SQL names. Creating/deleting a ledger manages those tables transactionally.
Appends are serialized for that ledger to avoid two blocks sharing the same index.

The field schema is fixed in genesis. Verification checks block hashes, links,
indexes, schema and duplicate record identifiers. Storage errors and inconsistent
history are reported instead of silently resetting the ledger.

Back up the complete database, including its encryption-key tables, using
PostgreSQL backup tools. A source clone, frontend build or encrypted snapshot is
not a substitute for that backup. Deleting keys or restoring unrelated keys makes
older downloaded snapshots unreadable. Store database backups outside Git and
limit who can read them.

The old `server/data/chain.jsonl` and `snapshot.key` files are not automatically
deleted or silently treated as PostgreSQL records. Keep them safe if migrating
an older installation; do not assume old snapshots belong to a new ledger.

Verify a PostgreSQL ledger without starting the website:

```bash
.venv/bin/python server/app.py --env-file .env --verify --ledger-id LEDGER_ID
```

The retained offline audit of an old JSON Lines ledger uses `--verify --data-dir
PATH`. Do not use it as the new application's storage configuration.

## Development and checks

The project uses pinned frontend dependencies and Python requirements. Recreate
the virtual environment on each machine rather than copying it between Windows
and Ubuntu.

For frontend development, keep the Python server running locally, then:

```powershell
npm.cmd --prefix frontend run dev
```

Vite serves `http://127.0.0.1:5173` and proxies `/api` to port 8000. Keep the local
settings from `.env.example` (`LEDGER_DEV_MODE=true`,
`LEDGER_SECURE_COOKIES=false`, loopback bind and an HTTP public origin). Development
mode explicitly permits the loopback Vite origins on port 5173. The deployed
build uses one HTTPS origin and does not permit those development exceptions.

```powershell
.venv\Scripts\python.exe -m unittest discover -s server -v
npm.cmd --prefix frontend run build
```

PostgreSQL integration tests require a separate disposable database selected by
`LEDGER_TEST_DATABASE_URL`; do not point it at a real deployment database. A
skipped database test is not evidence that PostgreSQL behavior passed.

Important source areas:

```text
frontend/src/          Public viewer, accounts, ledger creation and admin UI
server/app.py          Authenticated PostgreSQL deployment entry point
server/legacy_http.py  Old JSONL HTTP fixtures used only by regression tests
server/web_app.py      HTTP/API routing, authorization and HTTPS configuration
server/accounts.py    Password hashes, administrator bootstrap and browser sessions
server/settings.py    Literal environment-file loading and origin configuration
server/store.py        PostgreSQL ledger registry, per-ledger tables and append rules
server/field_schema.py Immutable field definitions and submitted-data validation
server/ledger.py       Canonical JSON, SHA-256 block/hash/verification helpers
server/multi_snapshots.py  Per-ledger encrypted exports and visual comparison reports
deploy/               Ubuntu preparation/start scripts and optional systemd unit
```

`.gitignore` excludes dependencies, builds, environment files, certificates/keys,
local database dumps, legacy local data, downloaded snapshots and test output.
Keep the tracked `.env.example` free of real credentials.
