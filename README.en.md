> [中文](README.md) | **English**

# Mi Scale to Garmin

Automatically sync **body composition measurements** from your Mi/Xiaomi body fat scale (via Mi Fitness) to your **Garmin Connect** account. Not just weight — it syncs BMI, body fat %, muscle mass, bone mass, visceral fat, metabolic age, basal metabolism, and more by generating Garmin-compatible FIT files.

**Where data goes**:

- **Pushed to Garmin**: FIT `weight_scale` message measurement fields (weight, BMI, body fat %, body water %, bone mass, muscle mass, metabolic age, visceral fat rating, basal metabolism, physique rating — 10 fields, matching FIT's `weight_scale` message)
- **Stored locally only** (`data/body/body_data_*.json`): all 28 metrics measured by the Mi scale (including protein, waist-hip ratio, body type classification, etc. that the FIT format doesn't support)

---

## 📖 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Download & Install](#2-download--install)
3. [Data Directory Rules](#3-data-directory-rules)
4. [Configuration](#4-configuration)
5. [Usage](#5-usage)
6. [Advanced](#6-advanced)
7. [Docker Deployment](#7-docker-deployment)
8. [Data Filtering](#8-data-filtering)
9. [FAQ](#9-faq)

---

## 1. Prerequisites

### Project Structure

```text
mi-scale-to-garmin/
├── src/                # Source code
│   ├── xiaomi/         # Mi login & data fetching module
│   ├── garmin/         # Garmin upload & FIT file generation (with custom OAuth fallback)
│   ├── core/           # Core: account hash / session storage / guided init / sync orchestration
│   ├── gui/            # Graphical interface (PyQt6, optional)
│   ├── utils/          # Utilities: paths / permission hardening
│   └── main.py         # One-click sync main program (CLI entry)
├── config/             # Config directory (users.json can live here or at project root)
│   └── users.json.example  # Config template (with comments; copy to users.json to use)
├── docs/               # Detailed docs (USAGE / DOCKER_SETUP / FILTER_CONFIG)
├── data/               # Runtime data (auto-created, gitignored)
│   ├── auth/             # Credentials (sensitive; delete = reset all auth)
│   │   ├── xiaomi_auth_*.json  # Mi auth credentials (auto-generated after first auth)
│   │   └── garmin/         # Garmin OAuth session (auto-generated after first auth)
│   ├── body/             # Local body composition backup (full 28 metrics)
│   │   └── body_data_*.json
│   ├── fit/              # Generated FIT files
│   └── captcha/          # Login captcha images (generated when captcha is triggered)
├── dist/               # Build artifacts (gitignored; structure in "6. Advanced → Local packaging")
├── tests/              # Tests (unittest)
├── debug/              # Debug scripts (raw data export, etc.)
├── .github/            # CI (build-release.yml: tag-triggered multi-platform builds)
├── users.json          # Core config file (no secrets: only account/email identity, no password/token)
├── requirements/       # Dependency manifests
│   ├── runtime.txt     # Runtime dependencies
│   ├── gui.txt         # GUI dependencies (PyQt6, etc.)
│   └── build.txt       # Build dependencies (PyInstaller, etc.)
├── packaging/          # Packaging chain (build.py + runtime hook + icon tool; see packaging/README.md)
├── docker/             # Docker image definition + service orchestration (login / sync)
├── .pyinstaller/       # PyInstaller intermediate artifacts (gitignored, regenerable)
└── README.md
```

### Requirements

- **Python 3.12.x**: [Download](https://www.python.org/downloads/). 3.14 is NOT compatible — do not use.
- During installation, check **"Add Python to PATH"**.
- Verify:

```bash
python --version
```

Output should be `Python 3.12.x`.

---

## 2. Download & Install

```bash
# Clone the repo (or click Code → Download ZIP on the repo page and extract)
git clone git@github.com:zeronesun/mi-scale-to-garmin.git
cd mi-scale-to-garmin

# Create and activate a virtual environment (recommended to isolate dependencies)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements/runtime.txt
```

---

## 3. Data Directory Rules

All runtime data (users.json config, Mi token, Garmin session, body data backup, captcha images, FIT files) is stored based on the **runtime form**:

| Version | Runtime form | Data directory | Notes |
|----------|----------|------|------|
| Dev | (`python src/main.py`) | project root `data/` | Follows the project; gitignored, never committed |
| Release | exe (CLI / GUI) | Windows `%APPDATA%\mi-scale-to-garmin\`; macOS `~/Library/Application Support/mi-scale-to-garmin/`; Linux `~/.local/share/mi-scale-to-garmin/` | CLI and GUI share the same directory — authenticate once, works for both; GUI can customize/reset via "Settings → Data Directory" |
| Container | Docker | `/app/data` inside container | Mounted to host via volume |

Inside the data directory, 4 subdirectories by "sensitivity + purpose" (same structure for all three forms):

```
<data dir>/
├── users.json        # User config (packaged version only; dev version at project root)
├── auth/             # Credentials (sensitive) — deleting this dir = reset all auth
│   ├── xiaomi_auth_<prefix>.json
│   └── garmin/<prefix>/
├── body/             # Body data dump (for troubleshooting; can keep long-term)
├── fit/              # FIT output (upload artifacts; safe to clean)
└── captcha/          # Temporary captcha images
```

Notes:

- **`users.json`**: dev version at project root; packaged version inside the data directory (alongside tokens — re-packaging/updating won't lose config).
- Dev and packaged versions each keep their **own token and config**, not shared — authenticate once per form, then zero-interaction afterward.
- Dev version: all data directories are gitignored (`data/*` global guard), sensitive credentials never enter the git repo.
- Release version: does not read/write the code directory; no source needed on the user's machine; clearing data = deleting the data directory.

### 3.1 Confusing point: "Dev build" ≠ "Dev environment" (clarified 2026-09-27)

The code decides the data directory based on the **runtime form** (`sys.frozen`: whether it's a packaged executable), **not** which directory the artifact is in:

| Concept | Meaning | Data directory |
|------|------|----------|
| **Artifact stage** (`dist/dev/` vs `dist/release/`) | Just an output directory label: dev = local verification artifact, release = release candidate | Does not affect behavior |
| **Runtime form** (frozen vs non-frozen) | Packaged exe/ELF = frozen; `python src/main.py` source run = non-frozen | **Determines the data directory** |

Therefore artifacts in `dist/dev/` **also behave as packaged** — they read the user data directory, not the project root. `dist/dev/` and `dist/release/` artifacts currently behave identically (release differences will later be in icon/signing, unrelated to data directory).

**Corollary (common in testing)**: to make the Linux side read the project-root `users.json` + project-root `data/` for a full sync, there's only one way — **run from source**:

```bash
# WSL
cd /mnt/d/zeronesun/002-work-craft/01-developing-debugging/mi-scale-to-garmin
.venv-linux/bin/python src/main.py --sync
```

For packaged artifacts (any platform, any dev/release) to run a sync, first copy `users.json` + `data/` to the corresponding user data directory (Linux: `~/.local/share/mi-scale-to-garmin/`).

---

## 4. Configuration

`users.json` is the program's only config file. If it doesn't exist, copy `config/users.json.example` to `users.json` (the template contains `//` comments; remove them to make it valid JSON).

**`users.json` stores only identity, preferences, and scale model — no password, no token** — safe to back up or share.

```json
{
    "users": [
        {
            "nickname": "me",
            "xiaomi_prefix": "me",
            "username": "your phone/email",
            "model": "yunmai.scales.ms103",
            "garmin_prefix": "me",
            "garmin": {
                "email": "your garmin account",
                "domain": "CN"
            }
        }
    ]
}
```

### Parameter reference

| Parameter | Description |
|------|------|
| `nickname` | Display name (optional): display name for this group (Mi + Garmin), unrelated to specific accounts. Only used for UI/log display, **never in filenames/paths**; suggest ≤20 chars, avoid duplicates (GUI blocks duplicates when adding users). |
| `username` / `garmin.email` | Account identity. If left empty, the program prompts for input on first run and writes it back. |
| `xiaomi_prefix` / `garmin_prefix` | Desensitized identifier (optional), used for output filenames, session dirs, and logs. If empty, falls back to `nickname` (frozen at creation); if none, falls back to the first 8 chars of the account SHA256 — **never uses plaintext account**. |
| `model` | Device model. Mi Body Composition Scale S400 → `yunmai.scales.ms103`; keep default if data is already imported into Mi Fitness. |
| `garmin.domain` | Garmin server region. China `CN`, international (TW/HK/US, etc.) `COM`. |
| Password & token | Password is only entered in the terminal during auth (hidden echo), discarded after auth, never stored; token auto-saved to `data/auth/xiaomi_auth_{prefix}.json` (Mi) and `data/auth/garmin/{prefix}/` (Garmin), auto-reused on next run. |

### Multiple users

`users` is an array; one element = one group (one Mi + one Garmin = one person). Click "Add User" in the GUI to append automatically; for manual config, copy one element block:

```json
{
    "users": [
        {
            "nickname": "me",
            "xiaomi_prefix": "me",
            "username": "13800000000",
            "model": "yunmai.scales.ms103",
            "garmin_prefix": "me",
            "garmin": { "email": "me@example.com", "domain": "CN" }
        },
        {
            "nickname": "wife",
            "xiaomi_prefix": "wife",
            "username": "13900000000",
            "model": "yunmai.scales.ms103",
            "garmin_prefix": "wife",
            "garmin": { "email": "wife@example.com", "domain": "CN" }
        }
    ]
}
```

Each user's data is isolated by prefix:

```
data/
├── body/
│   ├── body_data_me.json
│   └── body_data_wife.json
├── fit/
│   ├── body_me_<timestamp>_<seq>.fit
│   └── body_wife_<timestamp>_<seq>.fit
└── auth/
    ├── xiaomi_auth_me.json
    ├── xiaomi_auth_wife.json
    └── garmin/
        ├── me/
        └── wife/
```

Notes:

- **Don't duplicate `nickname`** (GUI blocks duplicates when adding); if manually duplicated, the display layer auto-appends a desensitized suffix to disambiguate (e.g. `wife·138****5678`).
- **Don't change `prefix` after creation**: filenames follow the prefix; changing it orphans old tokens/data and requires re-auth.
- If you don't want Chinese filenames, fill `prefix` with pinyin/English manually (keep `nickname` in Chinese for display).

---

## 5. Usage

### One-click sync

```bash
# Fetch data, generate FIT files, auto-upload to Garmin
python src/main.py --config users.json --sync
```

**First run** guides you through auth in the terminal as needed (not asked again afterward):

1. **Identity completion**: empty accounts/emails in `users.json` are prompted and written back.
2. **Mi auth**: enter Mi password (hidden echo); accounts with 2FA enabled need a 6-digit SMS code. On success, token saved to `data/auth/xiaomi_auth_{prefix}.json`.
3. **Garmin auth**: enter Garmin password before upload (hidden echo). On success, session saved to `data/auth/garmin/{prefix}/`.

**Subsequent runs**: zero-interaction while token/session is valid.

Sync flow:

1. Login to Mi (reuse stored token; re-auth when expired).
2. Fetch **all** historical body composition records (dual-source merge: old API real-time data + new API supplementing Zeeplife-imported data); terminal shows the latest 10 by default (`--limit` adjusts display count, doesn't affect actual fetch/upload).
3. Local backup to `data/body/body_data_{desensitized}.json`.
4. Generate FIT files in `data/fit/`.
5. Login to Garmin (reuse stored session) and upload.

### Auth only (no sync)

`src/xiaomi/login.py` is a standalone Mi auth tool, good for refreshing/verifying the Mi token without syncing:

```bash
python src/xiaomi/login.py --config users.json
```

- Flow is identical to `--sync` internally (identity completion → password → 2FA → token save); tokens are shared/reused between both.
- Only handles the Mi side; Garmin auth is only needed at upload time (not asked if session is valid).
- Mi auth carries account risk-control; don't run repeatedly while the token is valid.

---

## 6. Advanced

### CLI arguments

| Argument | Description |
|------|------|
| `--config PATH` | Config file path (default `users.json`) |
| `--limit N` | How many recent records to display in terminal (default 10; doesn't affect actual fetch) |
| `--fit` | Only generate local FIT files, no upload |
| `--sync` | Generate and upload (one-click sync mode) |
| `--output-dir PATH` | FIT output directory (default `data/fit`) |
| `--non-interactive` | Non-interactive mode; errors out if input is needed (for scheduled tasks/CI; unaffected while token is valid) |

### GUI (optional)

```bash
pip install -r requirements/gui.txt   # includes PyQt6 and other GUI deps
python src/gui/main.py users.json     # config path is a positional arg (default users.json)
```

The GUI supports multi-user management, sync progress display, and password popup input; auth flow is the same as CLI (first-time auth required).

### Scheduled auto-sync

```bash
# Linux/Mac: cron, every day at 2 AM (--non-interactive: unattended, errors out instead of hanging when input is needed)
0 2 * * * cd /project/path && .venv/bin/python src/main.py --sync --non-interactive
```

Windows Task Scheduler: see [docs/USAGE.md](docs/USAGE.md#4-自动化运行).

> Prerequisite: run `--sync` once manually in the terminal to complete auth. Scheduled tasks are zero-interaction while token/session is valid; on expiry the task errors out (doesn't hang) — run once manually to re-auth.

### Local packaging (developers)

```bash
pip install -r requirements/build.txt   # PyInstaller, etc.
python packaging/build.py gui           # GUI only (default onefile single file; --onedir switches to whole-folder zip)
python packaging/build.py cli           # CLI only (onefile single file)
python packaging/build.py all           # everything
python packaging/build.py all --release # output to dist/release/ (default dist/dev/)
```

Artifact directory is layered by "stage + platform" (platform auto-detected; PyInstaller doesn't cross-compile — Linux/macOS artifacts must be built on the corresponding system):

```
dist/
├── dev/                    # Dev verification artifacts (default)
│   ├── windows/  mi-scale-to-garmin-gui.exe (onefile)
│   │             mi-scale-to-garmin-gui-onedir.zip (onedir whole-folder, generated with --onedir)
│   │             mi-scale-to-garmin-cli.exe
│   └── linux/    mi-scale-to-garmin-cli (ELF, needs glibc; not Alpine-compatible)
└── release/                # Release candidates (--release)
    └── <platform>/...      # same structure
```

Distribution notes: GUI defaults to onefile single file for direct distribution; the `--onedir` form auto-packages into `mi-scale-to-garmin-gui-onedir.zip` (contains `onedirREAD.md`; after extraction use the whole folder together, don't copy the exe alone); CLI is a single file for direct distribution. Multi-platform releases go through CI (triggered by a `vX.Y.Z` tag; see `.github/workflows/build-release.yml`).

---

## 7. Docker Deployment

> ⚠️ **Currently unavailable**: image `zeronesun/mi-scale-to-garmin` not yet built/published (repo creation and CI publishing in progress); `docker compose pull` will 404. Use the Python method above for now; this section takes effect once the image is ready.

Use Docker when you don't want a local Python environment. Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop) (Windows/Mac) or `curl -fsSL https://get.docker.com | sh` (Linux); `docker --version` should output a version.

Full flow, directory structure, and troubleshooting: [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md). Core commands:

```bash
git clone git@github.com:zeronesun/mi-scale-to-garmin.git
cd mi-scale-to-garmin
cp config/users.json.example config/users.json   # template has // comments; remove after copying
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml --profile login run --rm login    # first time: Mi auth
docker compose -f docker/docker-compose.yml run --rm sync                     # sync
```

---

## 8. Data Filtering

Supports filtering body composition data by health metrics before syncing. Configured under each user's `garmin.filter`; see [docs/FILTER_CONFIG.md](docs/FILTER_CONFIG.md).

```json
"filter": {
    "enabled": true,
    "conditions": [
        { "field": "Weight", "operator": "between", "value": [60, 70] }
    ],
    "logic": "and"
}
```

- 9 supported metrics: `Weight`, `BMI`, `BodyFat`, `BodyWater`, `BoneMass`, `MetabolicAge`, `MuscleMass`, `VisceralFat`, `BasalMetabolism`
- Multiple conditions (AND/OR logic), configured independently per user
- If not configured, syncs all data; if config is invalid, skips filtering with a warning (doesn't interrupt sync)

---

## 9. FAQ

### Q: `ModuleNotFoundError: No module named 'requests'`?

Dependencies not installed or venv not activated. Activate the venv and run `pip install -r requirements/runtime.txt`.

### Q: Garmin upload keeps reporting `Duplicate`?

The record already exists on Garmin's server — normal dedup behavior, no action needed.

### Q: New computer / account changes?

Delete the entire `data/auth/` directory (Mi auth files + Garmin session), then re-run `python src/main.py --sync` and follow the prompts. `users.json` doesn't need changes (no password or token).

### Q: Which Mi scales are supported?

All body fat scales bound in Mi Fitness. If the default `model` can't fetch data, find an ID like `yunmai.scales.xxx` in the device info in the Mi Home / Mi Fitness app and fill it into the `model` field (see [docs/USAGE.md](docs/USAGE.md#1-如何查找体脂秤-model-id)).

---

## 🛡️ Security Notes

- `users.json` contains no password or token (only account/email identity), but it's still recommended not to share it publicly.
- Sensitive data lives under `data/auth/`: `xiaomi_auth_*.json` (Mi token), `garmin/` (Garmin OAuth token) — gitignored, **never commit or share them in any way (including `git add -f`)**.
- Password is only entered in the terminal during auth (hidden echo), discarded after auth, never stored.

---

## ✨ License

MIT License

Reference projects:

- [XiaomiGateway3](https://github.com/AlexxIT/XiaomiGateway3) — Mi protocol
- [garth](https://github.com/matin/garth) — Garmin OAuth library
- [garmin-weight-sync](https://github.com/XiaoSiHwang/garmin-weight-sync)
- [garmin-connect-plugin-for-dsh](https://github.com/Likenttt/garmin-connect-plugin-for-dsh)
