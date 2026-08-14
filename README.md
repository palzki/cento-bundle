# Seal Centoria Daily Login — Setup & Usage

This README explains how to set up a Python virtual environment, configure the project, and run `login_bot.py` safely.

**Prerequisites**
- Python 3.10+ installed and on PATH
- Windows / macOS / Linux terminal access

**Files of interest**
- [login_bot.py](login_bot.py)
- [requirements.txt](requirements.txt)
- [env.sample](env.sample)
- [accounts.sample.json](accounts.sample.json) — editable account template
- `.gitignore` already contains `accounts.json` and `.env`

**1) Create and activate a virtual environment**

PowerShell (Windows):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Command Prompt (Windows):

```cmd
python -m venv venv
.\venv\Scripts\activate
```

macOS / Linux (bash/zsh):

```bash
python3 -m venv venv
source venv/bin/activate
```

**2) Install dependencies**

```bash
pip install -r requirements.txt
```

**3) Configure environment variables**

- Copy the global env template:

```powershell
copy env.sample .env
# or on Unix: cp env.sample .env
```

- Edit `.env` to set global toggles such as `ENABLE_DISCORD`, `DISCORD_WEBHOOK_URL`, and `DISCORD_USER_ID`.
  - Keep secrets out of VCS. `.env` is in `.gitignore` by default.

**4) Configure per-account credentials**

- Copy the sample accounts file and edit it for each account you want to automate:

```powershell
copy accounts.sample.json accounts.json
# or on Unix: cp accounts.sample.json accounts.json
```

- Edit `accounts.json` with credentials and desired flags per account. See the sample for key names like `username`, `password`, `bank_pass` (or `bank_password`), and boolean flags like `want_bundle_shop`, `want_normal_daily`, etc.

- Important: `accounts.json` contains secrets. Do NOT commit it. The repo already ignores `accounts.json`.

**5) Quick validation (config-only check)**

Run a quick check that the script can parse your accounts without launching browsers:

```powershell
python -c "from login_bot import load_accounts; print(load_accounts())"
```

This prints the validated account objects (sensitive fields may appear — run locally only).

**6) Run the automation**

Run the main script (opens Chromium with persistent profile by default):

```powershell
python .\login_bot.py
```

Notes:
- The script uses a persistent profile directory named `playwright_stealth_profile` in the repo folder. You can remove or back it up if needed.
- The browser is launched non-headless by default so you can observe actions. To run headless, edit `headless=False` to `headless=True` in `login_bot.py` under the `launch_persistent_context` call.
