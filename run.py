#!/usr/bin/env python3
"""
run.py — Entry point for the Smart Gmail Agent.

Usage:
    python run.py              # Run the agent once and exit
    python run.py --schedule   # Run continuously on CHECK_INTERVAL_MINUTES cadence
    python run.py --init-db    # Initialise the database and exit
"""

import argparse
import logging
import schedule
import time
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _check_config():
    from src.config import GMAIL_USER, GMAIL_APP_PASSWORD, ANTHROPIC_API_KEY
    missing = []
    if not GMAIL_USER:          missing.append("GMAIL_USER")
    if not GMAIL_APP_PASSWORD:  missing.append("GMAIL_APP_PASSWORD")
    if not ANTHROPIC_API_KEY:   missing.append("ANTHROPIC_API_KEY")
    if missing:
        logger.error("Missing required env variables: %s", ", ".join(missing))
        logger.error("Copy .env.example → .env and fill in your credentials.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Smart Gmail Agent")
    parser.add_argument("--schedule", action="store_true",
                        help="Run continuously using CHECK_INTERVAL_MINUTES")
    parser.add_argument("--init-db", action="store_true",
                        help="Initialise the SQLite database and exit")
    args = parser.parse_args()

    # Always initialise the database
    from src import database as db
    db.init_database()

    if args.init_db:
        logger.info("Database initialised.")
        sys.exit(0)

    _check_config()

    from src.agent  import run_agent
    from src.config import CHECK_INTERVAL_MINUTES

    if args.schedule:
        logger.info("⏰  Scheduler mode — running every %d minute(s)", CHECK_INTERVAL_MINUTES)
        run_agent()   # Run immediately on start
        schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_agent)
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped.")
    else:
        run_agent()


if __name__ == "__main__":
    main()
