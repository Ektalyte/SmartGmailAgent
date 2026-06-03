import os
from dotenv import load_dotenv

load_dotenv()

# ── Gmail credentials ────────────────────────────────────────────────────────
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")   # Gmail App Password (not your real password)

# ── Anthropic / Claude ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "smart_gmail.db")

# ── Agent behaviour ──────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))
MAX_EMAILS_PER_RUN    = int(os.getenv("MAX_EMAILS_PER_RUN", "20"))

# Set AUTO_ARCHIVE=true to let the agent actually move/archive emails in Gmail.
# When false (default) the agent only analyses and stores results — no inbox changes.
AUTO_ARCHIVE = os.getenv("AUTO_ARCHIVE", "false").lower() == "true"
