"""
dashboard.py — Streamlit UI for the Smart Gmail Agent.

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import subprocess
import sys
import threading
from datetime import datetime

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Smart Gmail Agent",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialise DB before any query ────────────────────────────────────────────
from src import database as db
db.init_database()


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ───────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background: #0f1117;
}
[data-testid="stSidebar"] {
    background: #161b27;
    border-right: 1px solid #1e2636;
}
h1, h2, h3, h4, p, label, span {
    color: #e2e8f0 !important;
}

/* ── Metric cards ─────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #1a2035;
    border: 1px solid #2a3550;
    border-radius: 12px;
    padding: 18px 22px !important;
}
[data-testid="metric-container"] > div:first-child {
    color: #94a3b8 !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: .06em;
}
[data-testid="stMetricValue"] {
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #e2e8f0 !important;
}

/* ── Run-agent button ─────────────────────────────────────── */
.run-btn > button {
    background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.45rem 1.2rem !important;
    width: 100%;
}
.run-btn > button:hover {
    opacity: 0.9 !important;
}

/* ── Email cards ──────────────────────────────────────────── */
.email-card {
    background: #1a2035;
    border: 1px solid #2a3550;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    transition: border-color 0.15s;
}
.email-card:hover {
    border-color: #3b82f6;
    cursor: pointer;
}
.email-card .subject {
    font-weight: 600;
    font-size: 0.96rem;
    color: #e2e8f0;
    margin-bottom: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.email-card .sender {
    font-size: 0.82rem;
    color: #94a3b8;
}
.email-card .summary {
    font-size: 0.83rem;
    color: #64748b;
    margin-top: 6px;
    line-height: 1.45;
}

/* ── Badges ───────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: .04em;
    margin-right: 5px;
}
.badge-high       { background:#7f1d1d; color:#fca5a5; }
.badge-medium     { background:#78350f; color:#fcd34d; }
.badge-low        { background:#14532d; color:#86efac; }
.badge-important  { background:#1e3a5f; color:#93c5fd; }
.badge-work       { background:#312e81; color:#c4b5fd; }
.badge-personal   { background:#134e4a; color:#6ee7b7; }
.badge-newsletter { background:#374151; color:#d1d5db; }
.badge-spam       { background:#1f2937; color:#6b7280; }

/* ── Detail panel ─────────────────────────────────────────── */
.detail-box {
    background: #1a2035;
    border: 1px solid #2a3550;
    border-radius: 12px;
    padding: 24px 28px;
}
.detail-meta {
    font-size: 0.8rem;
    color: #64748b;
    margin-bottom: 4px;
}
.detail-body {
    background: #0f1117;
    border: 1px solid #2a3550;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 0.83rem;
    color: #94a3b8;
    line-height: 1.6;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: monospace;
}
.key-info-box {
    background: #1e2f1e;
    border: 1px solid #14532d;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 0.85rem;
    color: #86efac;
    margin-top: 12px;
}
.reasoning-box {
    background: #1e2740;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 0.82rem;
    color: #93c5fd;
    margin-top: 8px;
    font-style: italic;
}

/* ── Section headings ─────────────────────────────────────── */
.section-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: #64748b !important;
    margin-bottom: 10px;
}

/* ── Dividers ─────────────────────────────────────────────── */
hr { border-color: #1e2636 !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

URGENCY_BADGE = {
    "High":   '<span class="badge badge-high">🔴 HIGH</span>',
    "Medium": '<span class="badge badge-medium">🟡 MEDIUM</span>',
    "Low":    '<span class="badge badge-low">🟢 LOW</span>',
}

CATEGORY_BADGE = {
    "Important":  '<span class="badge badge-important">⭐ Important</span>',
    "Work":       '<span class="badge badge-work">💼 Work</span>',
    "Personal":   '<span class="badge badge-personal">👤 Personal</span>',
    "Newsletter": '<span class="badge badge-newsletter">📰 Newsletter</span>',
    "Spam":       '<span class="badge badge-spam">🚫 Spam</span>',
}


def fmt_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str[:19])
        return dt.strftime("%b %d, %H:%M")
    except Exception:
        return iso_str[:16] if iso_str else "—"


def _run_agent_thread():
    """Run the agent in a background thread so Streamlit stays responsive."""
    from src.agent import run_agent
    try:
        run_agent()
    except Exception as exc:
        st.session_state["agent_error"] = str(exc)
    finally:
        st.session_state["agent_running"] = False


# ── Session state ─────────────────────────────────────────────────────────────
if "selected_uid" not in st.session_state:
    st.session_state["selected_uid"] = None
if "agent_running" not in st.session_state:
    st.session_state["agent_running"] = False
if "agent_error" not in st.session_state:
    st.session_state["agent_error"] = None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📧 Smart Gmail Agent")
    st.markdown("---")

    # ── Run agent button ──────────────────────────────────────────────────────
    st.markdown('<p class="section-title">Agent</p>', unsafe_allow_html=True)
    st.markdown('<div class="run-btn">', unsafe_allow_html=True)
    if st.button(
        "⚡ Run Agent Now" if not st.session_state["agent_running"] else "⏳ Running…",
        disabled=st.session_state["agent_running"],
        key="run_btn",
    ):
        st.session_state["agent_running"] = True
        st.session_state["agent_error"] = None
        t = threading.Thread(target=_run_agent_thread, daemon=True)
        t.start()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state["agent_error"]:
        st.error(f"Agent error: {st.session_state['agent_error']}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = db.get_stats()
    last_run = stats.get("last_run")
    if last_run:
        st.caption(f"Last run: {fmt_date(last_run['run_at'])}  |  {last_run['emails_fetched']} fetched")

    st.markdown("---")

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown('<p class="section-title">Filters</p>', unsafe_allow_html=True)

    category_filter = st.selectbox(
        "Category",
        ["All", "Important", "Work", "Personal", "Newsletter", "Spam"],
        key="cat_filter",
    )
    urgency_filter = st.selectbox(
        "Urgency",
        ["All", "High", "Medium", "Low"],
        key="urg_filter",
    )
    processed_filter = st.selectbox(
        "Status",
        ["All", "Analysed", "Pending"],
        key="proc_filter",
    )

    st.markdown("---")

    # ── Category breakdown ────────────────────────────────────────────────────
    st.markdown('<p class="section-title">Category breakdown</p>', unsafe_allow_html=True)
    by_cat = stats.get("by_category", {})
    for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
        badge = CATEGORY_BADGE.get(cat, f'<span class="badge">{cat}</span>')
        st.markdown(
            f'{badge} <span style="color:#94a3b8;font-size:.82rem">{cnt}</span>',
            unsafe_allow_html=True,
        )


# ── Main area ─────────────────────────────────────────────────────────────────

# Header
col_title, col_space = st.columns([3, 1])
with col_title:
    st.markdown("# 📧 Smart Gmail Agent")
    st.caption("AI-powered inbox triage — powered by Claude")

st.markdown("---")

# ── KPI metrics ───────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📬 Total Emails",      stats.get("total", 0))
c2.metric("🔴 High Urgency",      stats.get("high_unactioned", 0))
c3.metric("⏳ Pending Analysis",  stats.get("unprocessed", 0))
c4.metric("✅ Actioned",          stats.get("by_category", {}).get("Spam", 0), help="Emails moved/archived")

by_urg = stats.get("by_urgency", {})
c5.metric("📊 Analysed",
          sum(by_urg.values()),
          help="Emails with AI analysis")

st.markdown("---")

# ── Build column layout ───────────────────────────────────────────────────────
list_col, detail_col = st.columns([5, 4], gap="large")

# ── Email list ────────────────────────────────────────────────────────────────
with list_col:
    # Convert filter selections to DB parameters
    is_proc = None
    if processed_filter == "Analysed":
        is_proc = True
    elif processed_filter == "Pending":
        is_proc = False

    emails = db.get_emails(
        category=category_filter,
        urgency=urgency_filter,
        is_processed=is_proc,
        limit=100,
    )

    st.markdown(
        f'<p class="section-title">{len(emails)} email(s)</p>',
        unsafe_allow_html=True,
    )

    if not emails:
        st.info("No emails match the current filters. Run the agent to fetch new emails.")
    else:
        for em in emails:
            uid       = em["uid"]
            subject   = em["subject"] or "(No Subject)"
            sender    = em["sender"] or "Unknown"
            date_str  = fmt_date(em.get("date", ""))
            summary   = em.get("summary") or ""
            category  = em.get("category", "—")
            urgency   = em.get("urgency", "—")
            processed = em.get("is_processed", 0)

            u_badge = URGENCY_BADGE.get(urgency, "")
            c_badge = CATEGORY_BADGE.get(category, "")

            # Highlight selected
            border = "border-color:#3b82f6;" if uid == st.session_state["selected_uid"] else ""

            st.markdown(
                f"""
                <div class="email-card" style="{border}">
                  <div class="subject">{subject[:80]}</div>
                  <div class="sender">From: {sender[:60]}  ·  {date_str}</div>
                  <div style="margin-top:6px">{u_badge}{c_badge}</div>
                  {"<div class='summary'>" + summary[:120] + "…</div>" if summary and processed else ""}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("View →", key=f"sel_{uid}", use_container_width=True):
                st.session_state["selected_uid"] = uid
                st.rerun()

# ── Detail panel ──────────────────────────────────────────────────────────────
with detail_col:
    selected_uid = st.session_state.get("selected_uid")

    if not selected_uid:
        st.markdown(
            """
            <div style="text-align:center;padding:80px 0;color:#2a3550;">
              <div style="font-size:3rem">📩</div>
              <div style="margin-top:12px;color:#4a5568;">
                Select an email on the left to view details
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        em = db.get_email_by_uid(selected_uid)
        if not em:
            st.error("Email not found.")
        else:
            category = em.get("category", "—")
            urgency  = em.get("urgency", "—")
            processed = em.get("is_processed", 0)

            # ── Subject + badges ──────────────────────────────────────────────
            st.markdown(
                f"""
                <div class="detail-box">
                  <div style="font-size:1.1rem;font-weight:700;margin-bottom:10px;color:#e2e8f0">
                    {em.get('subject','(No Subject)')}
                  </div>
                  <div class="detail-meta">From: {em.get('sender','—')}</div>
                  <div class="detail-meta">Date: {fmt_date(em.get('date',''))}</div>
                  <div style="margin-top:10px">
                    {URGENCY_BADGE.get(urgency,'')}
                    {CATEGORY_BADGE.get(category,'')}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if processed:
                st.markdown("#### 🤖 AI Analysis")

                # Summary
                summary = em.get("summary") or "—"
                st.info(f"**Summary:** {summary}")

                # Key info (deadline / action)
                key_info = em.get("key_info")
                if key_info:
                    st.markdown(
                        f'<div class="key-info-box">⏰ <strong>Key info:</strong> {key_info}</div>',
                        unsafe_allow_html=True,
                    )

                # Recommended action
                action = em.get("action", "keep")
                folder = em.get("folder")
                action_label = {
                    "keep":             "📥 Keep in Inbox",
                    "archive":          "📁 Archive",
                    "move_to_folder":   f"📂 Move to '{folder}'",
                }.get(action, action)
                st.markdown(f"**Recommended action:** {action_label}")

                # Reasoning
                reasoning = em.get("reasoning", "")
                if reasoning:
                    st.markdown(
                        f'<div class="reasoning-box">💡 {reasoning}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.warning("⏳ This email has not been analysed yet. Run the agent to analyse it.")

            # ── Raw body ──────────────────────────────────────────────────────
            with st.expander("📄 View raw email body"):
                body = em.get("body") or "(No plain-text body)"
                st.markdown(
                    f'<div class="detail-body">{body[:3000]}</div>',
                    unsafe_allow_html=True,
                )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Smart Gmail Agent · Powered by Claude (Anthropic) · Data stored locally in SQLite")
