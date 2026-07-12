"""
telegram_bot.py — runs locally on your laptop, no server/hosting needed.

Send it a job posting URL or pasted JD text, it runs tailor.py's full
pipeline (fetch -> analyze -> rewrite with one-page retry -> compile) and
sends the tailored PDF back in the same chat.

Uses long-polling (bot reaches OUT to Telegram), so nothing needs to be
publicly exposed — your laptop just needs internet access and this script
running.

SETUP
-----
1. Message @BotFather on Telegram -> /newbot -> follow prompts -> copy the
   token it gives you.
2. Message @userinfobot on Telegram to get YOUR numeric Telegram user ID.
3. Add to your .env (same file tailor.py already loads from ROOT/.env):
     TELEGRAM_BOT_TOKEN=<token from BotFather>
     TELEGRAM_ALLOWED_USER_ID=<your numeric user id>
4. pip install python-telegram-bot --upgrade
5. Make sure tectonic/pdflatex and Playwright's Chromium are installed
   locally (same requirements tailor.py's CLI already needs).
6. Run:  python telegram_bot.py
   Leave this running (see README notes on keeping it alive 24/7).

ACCESS CONTROL
---------------
There's no TAILOR_API_KEY / HTTP auth here — the bot itself just refuses
to act on messages from anyone whose Telegram user ID isn't
TELEGRAM_ALLOWED_USER_ID. Your bot's username being public doesn't matter;
strangers messaging it just get ignored.
"""

import asyncio
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import tailor  # your existing tailor.py, imported as a module

load_dotenv(tailor.ROOT / ".env")

BOT_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = os.getenv("TELEGRAM_ALLOWED_USER_ID")  # comma-separated, e.g. "111111,222222"

if not BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN not set in .env")
if not ALLOWED_USER_IDS:
    raise RuntimeError("❌ TELEGRAM_ALLOWED_USER_ID not set in .env — required so strangers can't use your bot")

try:
    ALLOWED_USER_IDS = {int(uid.strip()) for uid in ALLOWED_USER_IDS.split(",") if uid.strip()}
except ValueError:
    raise RuntimeError(
        "❌ TELEGRAM_ALLOWED_USER_ID must be numeric ID(s), comma-separated if more than one "
        "(e.g. TELEGRAM_ALLOWED_USER_ID=111111,222222) — got: " + os.getenv("TELEGRAM_ALLOWED_USER_ID", "")
    )

if not ALLOWED_USER_IDS:
    raise RuntimeError("❌ TELEGRAM_ALLOWED_USER_ID resolved to an empty set — check your .env")

MAX_PAGE_ATTEMPTS = 4


def _run_pipeline_sync(jd_input: str, company_override: str | None) -> tuple[Path, dict]:
    """
    Blocking pipeline call — same steps as tailor.py's main(), factored out
    so it can be run in a background thread (see tailor_resume() below).
    Returns (pdf_path, info_dict) or raises.
    """
    jd_text, company_auto = tailor.fetch_jd(jd_input)
    company      = company_override or company_auto
    company_slug = re.sub(r"[^a-zA-Z0-9]+", "-", company).strip("-").lower() or "company"

    analysis      = tailor.analyze_jd(jd_text)
    archetype     = analysis["role_archetype"]
    template_name = tailor.TEMPLATE_MAP.get(archetype, tailor.TEMPLATE_MAP["ML_AI"])

    tpl_path = tailor.TEMPLATES / template_name
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    tex_content = tpl_path.read_text(encoding="utf-8")

    from datetime import date
    today       = date.today().strftime("%Y-%m-%d")
    output_stem = f"cv-{company_slug}-{today}"

    word_buffer = 3
    pdf_path    = None
    page_count  = None

    for attempt in range(1, MAX_PAGE_ATTEMPTS + 1):
        rewrites     = tailor.get_rewrites(tex_content, jd_text, analysis, word_buffer=word_buffer)
        tex_tailored = tailor.apply_changes(tex_content, analysis, rewrites)
        pdf_path, page_count = tailor.compile_latex(tex_tailored, output_stem)
        if page_count <= 1:
            break
        word_buffer -= 4

    return pdf_path, {
        "company": company,
        "archetype": archetype,
        "page_count": page_count,
        "keywords": len(analysis["keywords"]),
    }


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or user.id not in ALLOWED_USER_IDS:
        # Silently ignore anyone who isn't in the allowed list — no error
        # message, so a stranger poking the bot doesn't even learn it does
        # anything.
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    status_msg = await update.message.reply_text("🤖 Tailoring your resume — this can take ~30-90s...")

    try:
        # tailor.py's fetch/analyze/rewrite/compile calls are all blocking
        # (Playwright sync API, subprocess LaTeX compile) — run in a thread
        # so the bot's event loop stays responsive to other messages.
        pdf_path, info = await asyncio.to_thread(_run_pipeline_sync, text, None)

        caption = (
            f"✅ {info['company']} · {info['archetype']} · "
            f"{info['page_count']} page{'s' if info['page_count'] != 1 else ''} · "
            f"{info['keywords']} keywords targeted"
        )
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(document=f, filename=pdf_path.name, caption=caption)

    except SystemExit as e:
        await update.message.reply_text(f"❌ Failed: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Unexpected error: {e}")
    finally:
        await status_msg.delete()


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot running (long-polling). Send it a JD URL or pasted JD text on Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()