# blockchainLedger

A standalone college prototype: a React chain viewer and a Python SHA-256
hash-linked ledger. GFX can optionally POST a finished match result; it does not
import ledger code or need the ledger to play a match.

This is a centralized, single-writer ledger. Hash verification checks consistency;
it does not prove who submitted a result or stop an owner rebuilding history.

## What is included

- Python API that appends submitted JSON results to a persistent SHA-256-linked chain.
- Deterministic genesis, canonical serialization, duplicate-result handling and
  independent hash/link verification after restart.
- Minimal React viewer with a live wrapping chain, hover animation and expandable,
  read-only block details.
- Encrypted whole-ledger or individual-block downloads and comparison of an older
  downloaded file against the current server history.
- Chain-head export, four optional demo matches, Windows launchers and automated
  storage, HTTP, verification and encrypted-snapshot tests.
- Optional integration with GFX through HTTP; the ledger also runs independently.

## Repository and local data

The repository contains the Python server, React source, dependency lockfile,
launchers and tests. Install dependencies and build the frontend after cloning.
Generated builds, dependencies, local environment files, test output and downloaded
snapshots are excluded by `.gitignore`.

Live records and the private snapshot key belong in `server/data/` by default and
are also excluded from Git. Back up this directory separately; a source-code clone
does not restore your saved ledger or make old encrypted downloads readable.

## Start the viewer

Requirements: Python 3.11+ and Node.js 22.12+ for building the frontend.

On Windows, double-click **Start Ledger.bat**, then open http://127.0.0.1:8000.
The launcher installs the Python encryption dependency if missing, installs locked
frontend dependencies and builds the viewer if its build is missing. Python serves
both the built React app and its API.

Or run these commands from this project folder:

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
python -m pip install -r server/requirements.txt
python server/app.py
```

On Linux, use `npm` and `python3` instead. The pinned `cryptography` dependency
provides authenticated encryption; the HTTP server and ledger use standard Python.
After editing frontend source, run the build command again.

For the requested four test matches, use **Start Demo Ledger.bat** or:

```powershell
python server/app.py --seed-demo
```

This appends four labelled `DEMO-MATCH-*` records once, preserving existing data.
Restarting with this flag does not duplicate them. Normal startup adds no samples.

The viewer contains just a wrapping chain and a few controls. Hover or focus a
block to lift it, and click to expand its read-only data beneath its row. The
download controls save encrypted `.ledger` files. **Validate file** compares a
previous download against the current server without importing or changing it.

For frontend development, keep `python server/app.py` running, then use a second
terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to Python on port 8000.
`LEDGER_API_URL` can change that development proxy target if needed.

## Submit a result through one API

`POST http://127.0.0.1:8000/api/blocks` is the only append endpoint. Send an object
containing exactly `match_id` and `data` with `Content-Type: application/json`.
The server supplies the index, timestamp, previous hash and new hash.

```powershell
$result = @{
    match_id = 'MATCH-001'
    data = @{
        duration_seconds = 180
        winning_team = 1
        team_scores = @(8, 5)
        players = @(
            @{ name = 'Pulkit'; team = 1; kills = 8; deaths = 5 }
            @{ name = 'Player 2'; team = 2; kills = 5; deaths = 8 }
        )
    }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/blocks `
    -ContentType 'application/json' -Body $result
```

The browser refreshes from the server every 1.5 seconds. It does not need to be
open when submitting. Entries are created through the API, not by editing cards.

- A new match returns HTTP 201 and `{ "block": ..., "duplicate": false }`.
- Retrying the same ID and data returns the existing block with HTTP 200.
- Reusing the ID with different data returns HTTP 409 without appending.
- `data` is a JSON object; its contents are application-defined. The ledger does
  not check whether submitted scores are truthful or came from GFX.
- Use unique match IDs across restarts. IDs and hashes should be strings.
- Bodies are limited to 64 KiB. Data supports strings, safe-range integers,
  booleans, null, objects and arrays. Floating-point values, duplicate JSON keys
  and excessive nesting are rejected. Encode fractional values as scaled integers.

The additional routes only read or verify:

| Route | Purpose |
| --- | --- |
| `GET /api/ledger` | Blocks, disk verification, storage location and read time |
| `POST /api/verify` with `{}` | Verify the saved ledger |
| `POST /api/verify` with `{ "blocks": [...] }` | Verify a supplied copy without saving it |
| `GET /api/checkpoint` | Export the current valid head's index and hash |
| `GET /api/snapshot` | Download the current ledger as an encrypted file |
| `GET /api/snapshot?block=2` | Download only block 2 as an encrypted file |
| `POST /api/validate-snapshot` | Send raw `.ledger` bytes as `application/octet-stream` to compare saved records with the server |

This initial API binds to localhost for a trusted local demonstration. It is not
a public authenticated result service. Nothing is deployed or port-forwarded.

For a GFX host on another trusted LAN computer, explicitly listen on the network
and allow the ledger address that the host will enter. Replace this example IP:

```powershell
python server/app.py --bind 0.0.0.0 --port 8000 --allow-host 192.168.1.20
```

In the current GFX Windows client, open **Home > Connections**, set the game
server address/TCP port, enable the optional blockchain ledger and enter ledger
address `192.168.1.20` and port `8000`. Start both services, then choose
**Validate and save**. GFX checks a game-server welcome and this ledger's
`GET /api/checkpoint` response before saving the endpoints locally.
After a timed match, the host can choose **Submit results** or **Not now**.
No ledger submission prompt appears when the ledger is disabled. The result
screen uses the saved endpoint rather than asking for it after every match.
Repeat `--allow-host` for additional IPs or hostnames. The normal loopback address
needs no extra flag. This is plain HTTP for trusted testing, without user accounts.

## Encrypted downloads

Downloads use Fernet authenticated encryption. The algorithm is public; the secret
key stays in `server/data/snapshot.key` (or your selected data directory). That key
is never included in API responses or frontend assets and is ignored by Git.
Keep a protected backup of it together with the ledger. Losing or changing the
key makes older downloads unreadable by this server. An invalid key is not silently
replaced.

A user can change bytes in a downloaded file, but changed files fail validation.
Validation first checks the encrypted file's authenticity, then the saved hashes
and links, and finally compares every saved record with the server's current
record at that position. A complete-ledger download remains valid after newer
blocks are appended; the response reports how many new blocks follow it. A
single-block file checks that one record against the current valid server chain.
Rewritten or missing saved history fails comparison. No validation call overwrites
server data. Files are limited to 8 MiB; individual downloads help with larger
ledgers.

Encryption authenticates a server-issued download, not the truth of submitted
scores. The trusted-server and external-checkpoint limitations still apply.

## Storage and verification

By default, records live in `server/data/chain.jsonl`, outside Git tracking.
One UTF-8 JSON object is appended per line. The fixed genesis block is index 0;
each submitted result adds one block after it. Never delete the data folder when
replacing application files if you want to keep your history.

Use a separate permanent location with:

```powershell
python server/app.py --data-dir C:/GFXData/ledger
```

Only one writer process may own that directory. Successful submission is
acknowledged after flushing the record to storage. On restart, existing records
are reused. A malformed or incomplete file is reported as invalid and blocks
further appends; the application does not silently repair or replace it.

Hashing uses the stored fields except `hash`: sorted object keys, compact JSON,
UTF-8, and the restricted JSON types described above. Array order matters. This
is our documented project format, not an implementation of RFC 8785/JCS.

The verifier checks schema, exact genesis, indexes, repeated match IDs, each
record's recalculated hash and every previous-hash link. Run it independently:

```powershell
python server/app.py --verify
python server/app.py --verify --data-dir C:/GFXData/ledger
```

The CLI is read-only and exits nonzero for an invalid or missing ledger.
Export a checkpoint to retain a fingerprint elsewhere. Internal validity alone
cannot reveal a fully rewritten chain or deletion of a complete final suffix;
that needs comparison with a previously trusted external checkpoint.

## Source map and checks

```text
frontend/src/      React screens, API calls and styles
server/ledger.py   Familiar block/hash/verify functions and JSONL storage
server/app.py      HTTP routes, static viewer serving, demo seeding and verification CLI
server/snapshots.py  Server-only encryption key, downloads and file comparison
server/test_ledger.py  Storage, verification and real HTTP tests using temporary data
server/test_snapshots.py  Encrypted downloads, tampering and saved-history comparison tests
```

```powershell
python -m unittest discover -s server -v
npm.cmd --prefix frontend run build
```

The first normal run starts with genesis only. Demo records require --seed-demo.
GFX's optional upload is initiated only by the lobby host after completion and
sends the server's finalized JSON. Disabling GFX_ENABLE_LEDGER_UPLOAD at build
time removes that client feature. There is no automatic dependency on a running
ledger, and no changes to match simulation, combat or voice.
