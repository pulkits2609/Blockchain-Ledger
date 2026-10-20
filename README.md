# blockchainLedger

A standalone college prototype: a React block explorer and a Python SHA-256
hash-linked ledger. GFX does not import or depend on this project.

This is a centralized, single-writer ledger. Hash verification checks consistency;
it does not prove who submitted a result or stop an owner rebuilding history.

## Start the viewer

Requirements: Python 3.11+ and Node.js 22.12+ for building the frontend.

On Windows, double-click **Start Ledger.bat**, then open http://127.0.0.1:8000.
The launcher installs locked frontend dependencies and builds the viewer if its
build is missing. Python serves both the built React app and its API.

Or run these commands from this project folder:

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
python server/app.py
```

On Linux, use `npm` and `python3` instead. No Python packages need installing.
After editing frontend source, run the build command again.

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
open when submitting. Its **New result** form uses the same API.

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

This initial API binds to localhost for a trusted local demonstration. It is not
a public authenticated result service. Nothing is deployed or port-forwarded.

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

The CLI is read-only and exits nonzero for an invalid or missing ledger. The
Verification lab checks edited copies without changing the stored chain.
Export a checkpoint to retain a fingerprint elsewhere. Internal validity alone
cannot reveal a fully rewritten chain or deletion of a complete final suffix;
that needs comparison with a previously trusted external checkpoint.

## Source map and checks

```text
frontend/src/      React screens, API calls and styles
server/ledger.py   Familiar block/hash/verify functions and JSONL storage
server/app.py      Local HTTP routes, static viewer serving and verification CLI
server/test_ledger.py  Storage, verification and real HTTP tests using temporary data
```

```powershell
python -m unittest discover -s server -v
npm.cmd --prefix frontend run build
```

The first run starts with genesis only. No example matches are silently added.
GFX integration, result authentication and distributed consensus are not part of
this first standalone viewer/API build.
