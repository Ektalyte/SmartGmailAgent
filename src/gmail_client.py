"""
gmail_client.py — IMAP wrapper for Gmail.

Handles: connect / disconnect, fetching unread emails,
archiving, moving to labels, and flagging as important.
"""

import imaplib
import email
import email.message
import logging
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from datetime import datetime
from typing import Dict, List, Optional

from src.config import GMAIL_USER, GMAIL_APP_PASSWORD

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decode_header(raw: Optional[str]) -> str:
    """Decode an RFC-2047 encoded email header into a plain string."""
    if not raw:
        return ""
    parts = []
    for fragment, charset in decode_header(raw):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(fragment))
    return " ".join(parts)


def _extract_body(msg: Message) -> str:
    """Return the plain-text body of an email (first text/plain part)."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="replace").strip()
                except Exception:
                    pass
    else:
        if msg.get_content_type() == "text/plain":
            try:
                charset = msg.get_content_charset() or "utf-8"
                return msg.get_payload(decode=True).decode(charset, errors="replace").strip()
            except Exception:
                pass
    return ""


# ── Client class ──────────────────────────────────────────────────────────────

class GmailClient:
    """Context-manager-friendly IMAP client for Gmail."""

    def __init__(self):
        self.imap: Optional[imaplib.IMAP4_SSL] = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Open an authenticated IMAP-over-SSL connection to Gmail."""
        try:
            self.imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            self.imap.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            logger.info("✓ Connected to Gmail IMAP as %s", GMAIL_USER)
            return True
        except imaplib.IMAP4.error as exc:
            logger.error("IMAP authentication failed: %s", exc)
            return False
        except Exception as exc:
            logger.error("Connection error: %s", exc)
            return False

    def disconnect(self):
        """Gracefully close the IMAP connection."""
        if self.imap:
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None

    # ── Fetching ──────────────────────────────────────────────────────────────

    def fetch_unread_emails(self, max_count: int = 20) -> List[Dict]:
        """
        Return up to *max_count* unread emails from INBOX, newest first.

        Each dict contains:
            uid, imap_id, sender, subject, body, date (ISO-8601)
        """
        if not self.imap:
            logger.error("Not connected.")
            return []

        results: List[Dict] = []
        try:
            self.imap.select("INBOX")
            _, data = self.imap.search(None, "UNSEEN")
            ids = data[0].split()

            # Limit and reverse so newest come first
            ids = ids[-max_count:]
            ids = list(reversed(ids))

            for seq_id in ids:
                try:
                    _, raw_data = self.imap.fetch(seq_id, "(RFC822)")
                    msg = email.message_from_bytes(raw_data[0][1])

                    # Stable UID
                    _, uid_resp = self.imap.fetch(seq_id, "(UID)")
                    uid_str = uid_resp[0].decode()
                    uid = uid_str.split("UID ")[1].split(")")[0].strip()

                    # Date
                    try:
                        date = parsedate_to_datetime(msg.get("Date", "")).isoformat()
                    except Exception:
                        date = datetime.now().isoformat()

                    results.append({
                        "uid":     uid,
                        "imap_id": seq_id.decode(),
                        "sender":  _decode_header(msg.get("From")),
                        "subject": _decode_header(msg.get("Subject")) or "(No Subject)",
                        "body":    _extract_body(msg),
                        "date":    date,
                    })
                except Exception as exc:
                    logger.warning("Could not parse email seq=%s: %s", seq_id, exc)

        except Exception as exc:
            logger.error("Failed to fetch emails: %s", exc)

        return results

    # ── Actions ───────────────────────────────────────────────────────────────

    def archive_email(self, uid: str) -> bool:
        """Archive an email: copy to All Mail, then remove from INBOX."""
        try:
            self.imap.select("INBOX")
            res, _ = self.imap.uid("COPY", uid, "[Gmail]/All Mail")
            if res == "OK":
                self.imap.uid("STORE", uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                logger.info("📁 Archived UID %s", uid)
                return True
        except Exception as exc:
            logger.error("Archive failed for UID %s: %s", uid, exc)
        return False

    def move_to_label(self, uid: str, label: str) -> bool:
        """Move an email to a Gmail label (creates label if absent)."""
        try:
            self.imap.select("INBOX")
            self.imap.create(label)          # no-op if already exists
            res, _ = self.imap.uid("COPY", uid, label)
            if res == "OK":
                self.imap.uid("STORE", uid, "+FLAGS", "\\Deleted")
                self.imap.expunge()
                logger.info("📂 Moved UID %s → %s", uid, label)
                return True
        except Exception as exc:
            logger.error("Move to label failed for UID %s: %s", uid, exc)
        return False

    def mark_as_important(self, uid: str) -> bool:
        """Flag (star) an email in Gmail."""
        try:
            self.imap.select("INBOX")
            self.imap.uid("STORE", uid, "+FLAGS", "\\Flagged")
            return True
        except Exception as exc:
            logger.error("Flag failed for UID %s: %s", uid, exc)
        return False

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
