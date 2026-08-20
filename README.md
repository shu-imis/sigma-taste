# Sigma Taste

Sigma Taste is a community recipe-sharing platform with local AI-assisted recipe drafting.

## Core Features

- Account system with `member` and `steward` roles
- Recipe creation and publishing
- AI recipe draft generation (local Ollama)
- Recipe detail, review, and emoji reactions
- Community leaderboards
- Human-centered UI with unified design tokens

## Tech Stack

- Python 3.10+
- Django 5.2 (LTS)
- SQLite (default)
- Local static assets (fonts/CSS/JS)
- Optional local Ollama service for AI features

## Quick Start

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

If PowerShell blocks execution of `Activate.ps1`, use Command Prompt instead, or run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### Windows (Command Prompt)

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The project also includes Windows helper scripts:

- `scripts/windows/start.bat` — start the development server
- `scripts/windows/reset.bat` — reset the database to its initial state

## Local Testing Flow

Start the server, then walk through:

1. Discover feed: `http://127.0.0.1:8000/discover/`
2. Create account: `http://127.0.0.1:8000/create-account/`
3. Sign in: `http://127.0.0.1:8000/sign-in/`
4. Recipe Studio: `http://127.0.0.1:8000/recipe-studio/`
5. AI Recipe Studio: `http://127.0.0.1:8000/ai-recipe-studio/`
6. Leaderboards: `http://127.0.0.1:8000/boards/`

## Create Steward Account

```bash
python manage.py create_steward
```

This command uses the same profile fields as normal registration and only grants `steward` privileges.

## AI Setup (Optional)

AI pages require a local Ollama instance. If Ollama is unavailable, manual recipe creation still works.

### macOS / Linux

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_TIMEOUT=180
```

### Windows (PowerShell)

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_TIMEOUT = "180"
```

### Windows (Command Prompt)

```bat
set OLLAMA_BASE_URL=http://localhost:11434
set OLLAMA_TIMEOUT=180
```

## Reset to Clean State

### macOS / Linux

```bash
rm -f db.sqlite3
python manage.py migrate
```

### Windows (PowerShell)

```powershell
if (Test-Path .\db.sqlite3) { Remove-Item .\db.sqlite3 }
python manage.py migrate
```

### Windows (Command Prompt)

```bat
if exist db.sqlite3 del db.sqlite3
python manage.py migrate
```

## Quality Verification

```bash
python manage.py check
python manage.py test
```

## Known Limitations

- AI generation depends on local Ollama models
- No initial data is pre-seeded by default
- SQLite is used for simplicity in single-node local demos
- Helper scripts are intended for local development only, not production deployment

## License

MIT License — see [LICENSE](LICENSE).
