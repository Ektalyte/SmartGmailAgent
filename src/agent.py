"""
agent.py — Main orchestration pipeline.

Steps executed on every run:
  1. Connect to Gmail via IMAP and pull unread emails.
  2. Skip UIDs that are already in the local database.
  3. Analyse each new email with Claude.
  4. Persist the analysis to SQLite.
  5. Optionally execute inbox actions (archive / move / flag) when AUTO_ARCHIVE=true.
"""

import logging
from typing import Dict

from src.gmail_client import GmailClient
from src.analyzer    import analyze_email
from src             import database as db
from src.config      import MAX_EMAILS_PER_RUN, AUTO_ARCHIVE

logger = logging.getLogger(__name__)

DIVIDER = "─" * 56


def run_agent() -> Dict:
    """
    Execute one full agent cycle.

    Returns a stats dict:
        fetched   – emails pulled from Gmail
        new       – emails not yet in the database
        analyzed  – emails successfully analysed by AI
        actioned  – emails acted on in Gmail (archive / move / flag)
        errors    – processing failures
    """
    logger.info(DIVIDER)
    logger.info("🤖  Smart Gmail Agent  —  starting run")
    logger.info("    AUTO_ARCHIVE = %s | MAX_EMAILS = %d", AUTO_ARCHIVE, MAX_EMAILS_PER_RUN)

    stats = {"fetched": 0, "new": 0, "analyzed": 0, "actioned": 0, "errors": 0}

    try:
        with GmailClient() as gmail:
            if not gmail.imap:
                raise ConnectionError("Could not connect to Gmail — check credentials in .env")

            # ── 1. Fetch unread emails ────────────────────────────────────────
            emails = gmail.fetch_unread_emails(max_count=MAX_EMAILS_PER_RUN)
            stats["fetched"] = len(emails)
            logger.info("📧  Fetched %d unread email(s)", stats["fetched"])

            # ── 2. Filter already-known emails ────────────────────────────────
            new_emails = []
            for e in emails:
                if not db.email_exists(e["uid"]):
                    db.upsert_email(e)
                    new_emails.append(e)

            stats["new"] = len(new_emails)
            logger.info("✨  %d new email(s) to analyse", stats["new"])

            # ── 3-5. Analyse + persist + act ─────────────────────────────────
            for email_data in new_emails:
                uid     = email_data["uid"]
                subject = email_data["subject"][:55]

                try:
                    logger.info("🔍  Analysing: %s", subject)
                    analysis = analyze_email(email_data)
                    db.update_analysis(uid, analysis)
                    stats["analyzed"] += 1

                    cat     = analysis["category"]
                    urgency = analysis["urgency"]
                    action  = analysis["action"]
                    folder  = analysis.get("folder")

                    logger.info(
                        "    → %-12s | urgency=%-6s | action=%s",
                        cat, urgency, action,
                    )

                    if AUTO_ARCHIVE:
                        if action == "archive":
                            if gmail.archive_email(uid):
                                db.mark_actioned(uid)
                                stats["actioned"] += 1

                        elif action == "move_to_folder" and folder:
                            if gmail.move_to_label(uid, folder):
                                db.mark_actioned(uid)
                                stats["actioned"] += 1

                        if urgency == "High" and action == "keep":
                            gmail.mark_as_important(uid)

                except Exception as exc:
                    logger.error("    ✗ Failed for UID %s: %s", uid, exc)
                    stats["errors"] += 1

        # ── Log the run ───────────────────────────────────────────────────────
        db.log_agent_run(
            stats["fetched"],
            stats["analyzed"],
            stats["actioned"],
        )

        logger.info("✅  Run complete — %s", stats)
        return stats

    except Exception as exc:
        logger.error("🔴  Agent run failed: %s", exc)
        db.log_agent_run(0, 0, 0, status="error", error=str(exc))
        raise
