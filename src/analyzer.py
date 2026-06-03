"""
analyzer.py — AI-powered email analysis using Claude (Anthropic).

For each email it returns:
  category  : Important | Work | Personal | Newsletter | Spam
  urgency   : High | Medium | Low
  summary   : 1-2 sentence plain-English summary
  action    : keep | archive | move_to_folder
  folder    : target Gmail label (only when action == move_to_folder)
  key_info  : critical deadline / action / date extracted from the email
  reasoning : brief explanation of the classification
"""

import json
import re
import logging
import os
from typing import Dict

import anthropic

from src.config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

# ── Model ─────────────────────────────────────────────────────────────────────
# Use CLAUDE_MODEL env variable to override; default to Haiku (fast + cheap).
# Valid model strings (June 2026):
#   claude-haiku-4-5-20251001   ← fast, cheap, good for triage
#   claude-sonnet-4-6           ← more accurate, higher cost
#   claude-opus-4-7             ← most capable
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _make_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is missing. "
            "Add it to your .env file and restart."
        )
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# Lazily instantiated so startup errors are visible
_client: anthropic.Anthropic = None  # type: ignore


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


CATEGORIES     = ["Important", "Work", "Personal", "Newsletter", "Spam"]
URGENCY_LEVELS = ["High", "Medium", "Low"]
ACTIONS        = ["keep", "archive", "move_to_folder"]

_PROMPT_TEMPLATE = """\
You are an intelligent email triage assistant. Analyse the email below and respond
with a single valid JSON object — no markdown fences, no extra text.

=== EMAIL ===
From    : {sender}
Subject : {subject}
Body    : {body_preview}
=============

Return exactly this JSON structure:
{{
  "category"  : "<Important | Work | Personal | Newsletter | Spam>",
  "urgency"   : "<High | Medium | Low>",
  "summary"   : "<1-2 sentence plain-English summary>",
  "action"    : "<keep | archive | move_to_folder>",
  "folder"    : "<Gmail label name, or null>",
  "key_info"  : "<deadline / required action / key date, or null>",
  "reasoning" : "<one sentence explaining category + urgency choice>"
}}

--- Classification rules ---
Category:
  Important  - requires the recipient's direct action or decision
  Work       - professional / business email, no urgent action required yet
  Personal   - friends, family, personal services
  Newsletter - marketing, subscriptions, digests, automated notifications
  Spam       - unsolicited, irrelevant, potentially malicious

Urgency:
  High   - deadline within 48 h, emergency, critical blocker
  Medium - needs a response or action within the week
  Low    - informational, no action required, FYI only

Recommended action:
  keep             - leave in INBOX (use for Important / urgent Work)
  archive          - move to All Mail (processed, informational)
  move_to_folder   - move to a specific label (Newsletters, Spam, etc.)
"""


def analyze_email(email_data: Dict) -> Dict:
    """
    Call Claude to analyse one email.

    :param email_data: dict with keys sender, subject, body, date
    :returns: analysis dict (category, urgency, summary, action, folder,
              key_info, reasoning)
    """
    body_preview = (email_data.get("body") or "")[:1500]

    prompt = _PROMPT_TEMPLATE.format(
        sender=email_data.get("sender", "Unknown"),
        subject=email_data.get("subject", "(No Subject)"),
        body_preview=body_preview or "(empty body)",
    )

    try:
        client = _get_client()
        logger.info("    Using model: %s", CLAUDE_MODEL)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip accidental markdown fences
        raw = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        analysis: Dict = json.loads(raw)

    except json.JSONDecodeError as exc:
        logger.error("JSON parse error in AI response: %s | raw=%r", exc, raw if 'raw' in dir() else "N/A")
        return _fallback(f"JSON parse error: {exc}")
    except anthropic.AuthenticationError as exc:
        logger.error("Authentication failed — check ANTHROPIC_API_KEY in .env: %s", exc)
        return _fallback(f"Invalid API key: {exc}")
    except anthropic.NotFoundError as exc:
        logger.error("Model not found (%s). Check CLAUDE_MODEL in .env: %s", CLAUDE_MODEL, exc)
        return _fallback(f"Model not found ({CLAUDE_MODEL})")
    except anthropic.APIError as exc:
        logger.error("Anthropic API error [%s]: %s", type(exc).__name__, exc)
        return _fallback(f"API error: {exc}")
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return _fallback(str(exc))
    except Exception as exc:
        logger.error("Unexpected error during analysis [%s]: %s", type(exc).__name__, exc)
        return _fallback(f"Unexpected error: {exc}")

    # ── Normalise / guard values ──────────────────────────────────────────────
    if analysis.get("category") not in CATEGORIES:
        analysis["category"] = "Personal"
    if analysis.get("urgency") not in URGENCY_LEVELS:
        analysis["urgency"] = "Low"
    if analysis.get("action") not in ACTIONS:
        analysis["action"] = "keep"

    analysis.setdefault("summary",   "No summary available.")
    analysis.setdefault("folder",    None)
    analysis.setdefault("key_info",  None)
    analysis.setdefault("reasoning", "")

    return analysis


def _fallback(error_msg: str = "AI analysis failed.") -> Dict:
    """Safe defaults returned when analysis cannot be completed."""
    return {
        "category":  "Personal",
        "urgency":   "Low",
        "summary":   "Analysis unavailable — manual review required.",
        "action":    "keep",
        "folder":    None,
        "key_info":  None,
        "reasoning": f"AI analysis failed: {error_msg}",
    }
