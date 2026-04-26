# Procurement Audit Webapp — Setup & Run Guide

Single-page Streamlit app that runs the FYP procurement-audit
experiment. Three stages of work:

1. **Local dev** — run on your laptop, no internet auth.
2. **Google Sheets backend** — set up service account, share sheet.
3. **Streamlit Cloud deploy** — push to GitHub, configure secrets.

---

## 1. Local dev

```powershell
cd code\webapp
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

For local dev you still need `secrets.toml` with valid Google Sheets
credentials (see Section 2). Place it at
`code\webapp\.streamlit\secrets.toml`.

---

## 2. Google Sheets backend

### 2.1 Create the service account

1. Open <https://console.cloud.google.com>, create a new project (or
   reuse one). Note the **Project ID**.
2. Navigate to **APIs & Services → Library** and enable both:
   - **Google Sheets API**
   - **Google Drive API**
3. Navigate to **APIs & Services → Credentials**.
4. Click **Create Credentials → Service account**.
   - Name: `experiment-bot` (anything will do).
   - Skip the optional permission grant steps.
5. Open the new service account, go to **Keys → Add Key → Create
   new key → JSON**. A file `XXX.json` is downloaded — save it as
   `code\webapp\credentials.json`. **Never commit this file.**

### 2.2 Create the spreadsheet

1. In Google Drive create a new Google Sheet, e.g. *FYP Experiment
   Data*. Copy its ID from the URL (`/d/<THIS_PART>/edit`).
2. Open the sheet → **Share** → paste the service account's
   `client_email` (looks like
   `experiment-bot@your-project.iam.gserviceaccount.com`) → set
   **Editor** access. The bot must be able to read AND write.

### 2.3 Initialise sheets and shuffle the assignment queue

```powershell
cd code\webapp
python init_sheets.py --spreadsheet-id <YOUR_SHEET_ID> --slots 12 --seed 42
```

This creates two worksheets in the spreadsheet:

- `assignment_queue` — 12 rows, group labels pre-shuffled (4 G1, 4 G2,
  4 G3) with deterministic seed 42.
- `sessions` — empty, headers only.

Re-run with `--reset` if you need to wipe and regenerate.

### 2.4 Local secrets file

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and
fill in:

- `spreadsheet_id` — same ID as above.
- `[gcp_service_account]` — paste fields from `credentials.json`
  one-for-one. The `private_key` field uses TOML's triple-quoted
  multi-line string syntax (see the example file).

You can verify locally with:

```powershell
streamlit run app.py
```

Submit a test name and confirm a row appears in `assignment_queue`.

---

## 3. Streamlit Cloud deploy

1. Push the repo to GitHub. Make sure both
   `code/webapp/credentials.json` and
   `code/webapp/.streamlit/secrets.toml` are listed in
   `.gitignore` so they never reach the remote.
2. Visit <https://share.streamlit.io>, sign in with GitHub, click
   **New app**.
3. Repository: your repo. Branch: `main`. Main file path:
   `code/webapp/app.py`.
4. Open **Advanced settings → Secrets**. Paste the entire content of
   your local `secrets.toml` directly (TOML format, no JSON
   conversion needed).
5. Click **Deploy**. The first build takes ~3 minutes.

The app spins down after ~7 days of idle. The first visitor after a
spin-down sees a 5–30 second wake-up screen — schedule a manual visit
shortly before each experiment session.

---

## 4. File map

| File | Purpose |
| ---- | ------- |
| `app.py` | Entry point. State machine across the participant flow. |
| `data_loader.py` | Loads the latest Stage 3 + Stage 4 frozen artefacts. |
| `sheets_backend.py` | gspread wrapper: claim slot, log responses. |
| `init_sheets.py` | One-time setup of the two worksheets. |
| `briefing_common.md` | Common participant briefing (all groups). |
| `briefing_g1.md` | G1-specific addendum. |
| `briefing_g2.md` | G2-specific addendum. |
| `briefing_g3.md` | G3-specific addendum. |
| `requirements.txt` | Python deps. |
| `.streamlit/secrets.toml.example` | Template for secrets. Copy and fill. |

---

## 5. Roadmap

- ✅ M0 — briefing markdown
- ✅ M1 — landing + briefing + background + Google Sheets backend
- ⏳ M2 — order card render (Section A/B/E natural-language sentences)
- ⏳ M3 — practice flow (2 Q with feedback)
- ⏳ M4 — main experiment flow (32 Q, no back, per-Q logging)
- ⏳ M5 — trust survey (5 items, G2/G3 only) + thank-you
- ⏳ M6 — researcher self-test
