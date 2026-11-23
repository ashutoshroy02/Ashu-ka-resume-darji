"""
telegram_bot.py — runs locally on your laptop, no server/hosting needed.

Send it a job posting URL or pasted JD text, then:
  1. it suggests a base resume (⭐) — tap one of the 6 bases
  2. it ranks your projects for that JD and pre-ticks the best ones —
     tap to add/remove, then 🚀 Build (or 🤖 Skip to keep the AI picks)
  3. it runs tailor.run_tailor (swap projects -> fit one page -> keyword
     rewrite with one-page retry -> compile) and sends the PDF back.
Projects come from templates/projects.yml.

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
from datetime import date
from itertools import count
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

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

# ── Conversation state ──────────────────────────────────────────────────
# One session per user in context.user_data["session"]. Every button carries
# the session id, so taps on an old message (an earlier JD) are rejected
# instead of acting on the wrong job.
_session_ids = count(1)


def _allowed(update: Update) -> bool:
    # Anyone not in the allowed list is silently ignored, so a stranger
    # poking the bot doesn't even learn it does anything.
    user = update.effective_user
    return user is not None and user.id in ALLOWED_USER_IDS


# ── Blocking steps (run in a thread: Playwright, LLM calls, LaTeX) ─────
def _prepare_sync(jd_input: str) -> dict:
    jd_text, company = tailor.fetch_jd(jd_input)
    analysis = tailor.analyze_jd(jd_text)
    return {"jd_text": jd_text, "company": company, "analysis": analysis}


def _rank_sync(s: dict) -> dict:
    library = tailor.load_projects()
    tex = (tailor.TEMPLATES / tailor.TEMPLATE_MAP[s["base"]]).read_text(encoding="utf-8")
    info = tailor.base_project_info(tex, library)
    ranked = tailor.rank_projects(s["jd_text"], s["analysis"], s["base"], info, library)
    return {"info": info, **ranked}


def _build_sync(s: dict) -> tuple[Path, dict]:
    # "01_ML_AI_Engineer_Ashutosh.tex" -> "ML_AI_Engineer_Ashutosh-2026-11-23"
    role_title  = re.sub(r"^\d+_", "", Path(tailor.TEMPLATE_MAP[s["base"]]).stem)
    output_stem = f"{role_title}-{date.today():%Y-%m-%d}"
    ids = [i for i in s["ranking"] if i in s["selected"]]  # best-ranked first
    return tailor.run_tailor(s["jd_text"], s["analysis"], s["base"], ids, output_stem)


# ── Keyboards ──────────────────────────────────────────────────────────
def _base_keyboard(s: dict) -> InlineKeyboardMarkup:
    rec = s["analysis"].get("role_archetype")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(("⭐ " if key == rec else "") + label, callback_data=f"b|{s['sid']}|{key}")]
        for key, label in tailor.BASE_LABELS.items()
    ])


def _project_keyboard(s: dict) -> InlineKeyboardMarkup:
    names = s["info"]["names"]
    rows = [
        [InlineKeyboardButton(("✅ " if pid in s["selected"] else "⬜ ") + names[pid], callback_data=f"p|{s['sid']}|{n}")]
        for n, pid in enumerate(s["ranking"])
    ]
    rows.append([
        InlineKeyboardButton("🚀 Build", callback_data=f"d|{s['sid']}"),
        InlineKeyboardButton("🤖 Skip (AI picks)", callback_data=f"s|{s['sid']}"),
    ])
    return InlineKeyboardMarkup(rows)


def _project_text(s: dict) -> str:
    reason = f"💡 {s['reason']}\n" if s.get("reason") else ""
    return (
        f"📄 Base: {tailor.BASE_LABELS[s['base']]}\n{reason}\n"
        "Tap projects to include / exclude (✅ = AI picks, best match first).\n"
        "If it can't fit one page, the lowest ticked ones get dropped.\n"
        "Then tap 🚀 Build — or 🤖 Skip to just use the AI picks."
    )


# ── Handlers ───────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    status = await update.message.reply_text("🔎 Reading the JD…")
    try:
        prep = await asyncio.to_thread(_prepare_sync, text)
    except SystemExit as e:
        await status.edit_text(f"❌ Failed: {e}")
        return
    except Exception as e:
        await status.edit_text(f"❌ Unexpected error: {e}")
        return

    # A new JD replaces any previous session.
    s = {"sid": next(_session_ids), **prep}
    context.user_data["session"] = s
    a = prep["analysis"]
    rec = tailor.BASE_LABELS.get(a.get("role_archetype"), "—")
    reason = f"💡 {a['archetype_reason']}\n" if a.get("archetype_reason") else ""
    await status.edit_text(
        f"📄 {prep['company']}\n⭐ AI suggests: {rec}\n{reason}\nChoose the base resume:",
        reply_markup=_base_keyboard(s),
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not _allowed(update):
        await q.answer()
        return

    kind, sid, *rest = q.data.split("|")
    s = context.user_data.get("session")
    if not s or str(s["sid"]) != sid:
        await q.answer("That's from an older JD — send the JD again.", show_alert=True)
        return
    if s.get("busy"):
        await q.answer("Still working on it…")
        return

    if kind == "b":                                   # base chosen -> rank projects
        await q.answer()
        s["base"] = rest[0]
        s["busy"] = True
        await q.edit_message_text(f"📄 Base: {tailor.BASE_LABELS[s['base']]}\n🤖 Ranking your projects for this JD…")
        try:
            s.update(await asyncio.to_thread(_rank_sync, s))
        except Exception as e:
            await q.edit_message_text(f"❌ Could not rank projects: {e}")
            return
        finally:
            s["busy"] = False
        s["selected"] = set(s["picks"])
        await q.edit_message_text(_project_text(s), reply_markup=_project_keyboard(s))

    elif kind == "p" and "ranking" in s:              # toggle one project
        pid = s["ranking"][int(rest[0])]
        s["selected"] ^= {pid}
        await q.answer(("Added: " if pid in s["selected"] else "Removed: ") + s["info"]["names"][pid])
        await q.edit_message_reply_markup(reply_markup=_project_keyboard(s))

    elif kind in ("d", "s") and "ranking" in s:       # build (nothing ticked = AI picks)
        await q.answer()
        if kind == "s" or not s["selected"]:
            s["selected"] = set(s["picks"])
        chosen = [s["info"]["names"][i] for i in s["ranking"] if i in s["selected"]]
        s["busy"] = True
        await q.edit_message_text(
            f"🛠 Building: {tailor.BASE_LABELS[s['base']]}\n"
            f"📂 Projects: {', '.join(chosen)}\n⏳ This can take ~30-90s…"
        )
        try:
            pdf_path, info = await asyncio.to_thread(_build_sync, s)
        except SystemExit as e:
            await q.edit_message_text(f"❌ Failed: {e}")
            return
        except Exception as e:
            await q.edit_message_text(f"❌ Unexpected error: {e}")
            return
        finally:
            s["busy"] = False

        pages = info["page_count"]
        caption = (
            f"✅ {s['company']} · {tailor.BASE_LABELS[s['base']]} · "
            f"{pages} page{'s' if pages != 1 else ''} · {len(s['analysis']['keywords'])} keywords\n"
            f"📂 {', '.join(info['kept'])}"
        )
        if info["dropped"]:
            caption += f"\n✂️ Dropped to fit one page: {', '.join(info['dropped'])}"
        await q.delete_message()
        with open(pdf_path, "rb") as f:
            await context.bot.send_document(chat_id=q.message.chat_id, document=f,
                                            filename=pdf_path.name, caption=caption)
    else:
        await q.answer()


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_button))
    print("🤖 Bot running (long-polling). Send it a JD URL or pasted JD text on Telegram.")
    # app.run_polling(drop_pending_updates=False)  
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()