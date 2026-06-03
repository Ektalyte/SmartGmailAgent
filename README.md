# 📧 Smart Gmail Agent

Smart Gmail Agent is an autonomous AI assistant that connects to your Gmail 
inbox via IMAP, analyses every unread email with Claude (Anthropic), and 
classifies it by category and urgency — so you only focus on what matters.

---

## What it does

| Step | Description |
|------|-------------|
| 🔌 Connect | Connects to your Gmail inbox via IMAP (SSL) |
| 📥 Fetch   | Retrieves unread emails (sender, subject, body, date) |
| 🤖 Analyse | Classifies each email using Claude AI |
| 💾 Store   | Persists results in a local SQLite database |
| 📊 Display | Visualises everything in a Streamlit dashboard |
| ⚙️ Act     | Optionally archives / moves emails automatically |

### AI analysis output (per email)

| Field | Values |
|-------|--------|
| `category` | Important · Work · Personal · Newsletter · Spam |
| `urgency`  | High · Medium · Low |
| `summary`  | 1–2 sentence plain-English summary |
| `action`   | keep · archive · move_to_folder |
| `key_info` | Critical deadline / required action extracted from body |
| `reasoning`| Brief explanation of the classification |

---

## Project structure

```
smart_gmail_agent/
├── run.py               ← CLI entry point (run once or schedule)
├── dashboard.py         ← Streamlit UI  (streamlit run dashboard.py)
├── requirements.txt
├── .env.example         ← Copy to .env and fill in credentials
└── src/
    ├── config.py        ← Loads env variables
    ├── gmail_client.py  ← IMAP connection & actions
    ├── analyzer.py      ← Claude AI analysis
    ├── database.py      ← SQLite persistence
    └── agent.py         ← Orchestration pipeline
```

---

## Quick start

### 1. Prerequisites

- Python 3.10+
- A Gmail account with **IMAP enabled**
  - Gmail settings → See all settings → Forwarding and POP/IMAP → Enable IMAP
- A **Gmail App Password** (required since Google disabled "less secure app" access)
  - Visit <https://myaccount.google.com/apppasswords> (requires 2-Step Verification)
  - Create an app password for "Mail" / "Windows Computer"
  - You will get a 16-character code like `abcd efgh ijkl mnop`
- An **Anthropic API key**
  - Visit <https://console.anthropic.com/> → API Keys

### 2. Install

```bash
git clone <this-repo>
cd smart_gmail_agent

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Open .env in your editor and fill in:
#   GMAIL_USER, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY
```

### 4. Initialise the database

```bash
python run.py --init-db
```

### 5. Run the agent once

```bash
python run.py
```

### 6. Open the dashboard

```bash
streamlit run dashboard.py
```

The dashboard opens at **http://localhost:8501**.  
Click **⚡ Run Agent Now** in the sidebar to fetch and analyse new emails.

### 7. (Optional) Run continuously

```bash
python run.py --schedule
# Checks for new emails every CHECK_INTERVAL_MINUTES (default: 5)
```

---

## Configuration reference (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GMAIL_USER` | — | Your Gmail address |
| `GMAIL_APP_PASSWORD` | — | 16-character Gmail App Password |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `CHECK_INTERVAL_MINUTES` | `5` | Polling interval for scheduler mode |
| `MAX_EMAILS_PER_RUN` | `20` | Max emails fetched per run |
| `AUTO_ARCHIVE` | `false` | Set `true` to let the agent move/archive emails |
| `DATABASE_PATH` | `smart_gmail.db` | SQLite database file path |

> ⚠️ **`AUTO_ARCHIVE=false` (default):** The agent only analyses emails — nothing is moved or deleted in Gmail. Set to `true` only once you trust the classifications.

---

## Dashboard walkthrough

```
┌──────────────────────────────────────────────────────────────────┐
│ Sidebar                  │ Main area                              │
│ ─────────                │ ─────────────────────────────────────  │
│ ⚡ Run Agent Now          │ KPI cards (total / urgency / status)   │
│                          │                                        │
│ Filters:                 │ ┌─────────────────┬──────────────────┐ │
│  Category ▾              │ │ Email list       │ Detail panel     │ │
│  Urgency  ▾              │ │                  │                  │ │
│  Status   ▾              │ │ [subject]        │ Subject          │ │
│                          │ │ From · date      │ From / Date      │ │
│ Category breakdown       │ │ 🔴 HIGH ⭐ Imp.  │ 🤖 AI Analysis   │ │
│  ⭐ Important  12         │ │ Summary…         │  Summary         │ │
│  💼 Work        8         │ │                  │  Key info        │ │
│  …                       │ │ [View →]         │  Reasoning       │ │
│                          │ │                  │  Raw body ▸      │ │
└──────────────────────────┴─┴──────────────────┴──────────────────┘
```

---

## Architecture

```
┌─────────────┐    IMAP/SSL   ┌──────────────┐
│  Gmail      │◄─────────────►│ gmail_client │
│  Inbox      │               └──────┬───────┘
└─────────────┘                      │
                                      ▼
                              ┌──────────────┐     Anthropic API
                              │    agent     │────────────────────►
                              │ (pipeline)   │◄──── Claude analysis
                              └──────┬───────┘
                                      │
                            ┌─────────▼──────────┐
                            │      SQLite DB      │
                            │  emails + runs      │
                            └─────────┬───────────┘
                                      │
                              ┌───────▼────────┐
                              │   Streamlit    │
                              │   Dashboard    │
                              └────────────────┘
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `IMAP authentication failed` | Check App Password — it's the 16-char code, not your Google password. Ensure IMAP is enabled in Gmail settings. |
| `Anthropic API error` | Verify your API key in `.env`. Check your Anthropic account has credits. |
| Dashboard shows no emails | Click **⚡ Run Agent Now** in the sidebar, or run `python run.py`. |
| Emails not being moved even with `AUTO_ARCHIVE=true` | Gmail IMAP labels (folders) are case-sensitive. Verify the label names in Gmail settings. |
| `ModuleNotFoundError` | Activate your virtual environment: `source .venv/bin/activate` |

---

## Security notes

- Your Gmail password is **never used** — only the App Password.
- The App Password gives access to your email. Keep `.env` out of version control (it is listed in `.gitignore` by default).
- Email bodies are sent to the Anthropic API for analysis. Do not use this agent on inboxes containing highly sensitive/confidential data without reviewing Anthropic's data-use policy.

---

## License

MIT — see `LICENSE` for details.
