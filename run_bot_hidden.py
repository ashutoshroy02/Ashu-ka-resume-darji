"""
run_bot_hidden.py — silent/background launcher for telegram_bot.py.

Run this with pythonw.exe (not python.exe) and there is NO console window
at all — it starts fully invisibly. Since there's no console to print to,
all output (from tailor.py's print() calls and python-telegram-bot's own
logging) is redirected to a rotating log file instead, so you can still
check logs/bot.log if something goes wrong.

This is what Task Scheduler should point at (see setup notes at bottom).
"""

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bot.log"

# Redirect stdout/stderr to the log file BEFORE importing tailor_bot/tailor,
# so tailor.py's stdout rewrap (which checks hasattr(sys.stdout, "buffer"))
# sees a plain file object and skips itself safely.
_log_fp = open(LOG_FILE, "a", encoding="utf-8", buffering=1)  # line-buffered
sys.stdout = _log_fp
sys.stderr = _log_fp

# Route python-telegram-bot's internal logging (warnings, connection info,
# etc.) into the same file instead of the console that doesn't exist here.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )],
)

print("=" * 60)
print("Starting resume-tailor Telegram bot (background/hidden mode)")
print("=" * 60)

import telegram_bot  # noqa: E402  (import after redirect is intentional)

if __name__ == "__main__":
    try:
        telegram_bot.main()
    except Exception:
        logging.exception("Bot crashed")
        raise
