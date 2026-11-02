import html
import logging
import os
import re
import sqlite3
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "bot.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
QUALITIES = ("480p", "720p", "1080p")
QUALITY_BADGES = {"480p": "🟢", "720p": "🔵", "1080p": "🟣"}
VALID_FIELDS = {"anime", "season", "episode", "quality", "language", "ext"}
DEFAULT_TEMPLATE = (
    "@ANIFLIXANIMETAMIL -{anime} S{season} E{episode} "
    "[{quality}][ {language} ].{ext}"
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            body TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, name)
        )
    """)
    conn.commit()
    return conn


def ensure_default_template(user_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM templates WHERE user_id=? LIMIT 1", (user_id,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO templates(user_id,name,body,is_default) VALUES(?,?,?,1)",
                (user_id, "default", DEFAULT_TEMPLATE),
            )


def get_default_template(user_id: int):
    ensure_default_template(user_id)
    with db() as conn:
        row = conn.execute(
            "SELECT name, body FROM templates WHERE user_id=? AND is_default=1",
            (user_id,),
        ).fetchone()
        if row:
            return row
        row = conn.execute(
            "SELECT name, body FROM templates WHERE user_id=? ORDER BY name LIMIT 1",
            (user_id,),
        ).fetchone()
        return row


def validate_template(template: str):
    fields = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", template))
    unknown = fields - VALID_FIELDS
    if unknown:
        return False, "Unknown placeholder(s): " + ", ".join(sorted(unknown))
    if not {"anime", "season", "episode", "quality"}.issubset(fields):
        return False, "Template must include {anime}, {season}, {episode}, and {quality}."
    try:
        template.format(
            anime="Anime", season="01", episode="03",
            quality="720p", language="Tamil", ext="mkv"
        )
    except (KeyError, ValueError, IndexError):
        return False, "Template formatting is invalid."
    return True, ""


def parse_input(text: str):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 3:
        return None
    anime = lines[0]
    season_match = re.search(r"(\d+)", lines[1])
    episode_match = re.search(r"(\d+)", lines[2])
    if not anime or not season_match or not episode_match:
        return None
    season_num = int(season_match.group(1))
    episode_num = int(episode_match.group(1))
    if season_num < 0 or episode_num < 0:
        return None
    return {
        "anime": anime,
        "season": f"{season_num:02d}",
        "episode": f"{episode_num:02d}",
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_default_template(user_id)
    await update.message.reply_text(
        "✨ <b>Anime Filename Generator</b>\n\n"
        "Send these as three messages:\n"
        "<code>Naruto</code>\n<code>Season 1</code>\n<code>03</code>\n\n"
        "Or send all three lines in one message.\n\n"
        "<b>Commands</b>\n"
        "/settemplate — save a template\n"
        "/templates — view saved templates\n"
        "/deletetemplate name — delete a template\n"
        "/default name — choose the default template\n"
        "/help — show help",
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def settemplate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.args[0].strip().lower() if context.args else "default"
    if not re.fullmatch(r"[a-z0-9_-]{1,30}", name):
        await update.message.reply_text("Use a simple template name: letters, numbers, _ or -.")
        return
    context.user_data["awaiting_template"] = name
    await update.message.reply_text(
        f"Send the filename template for <b>{html.escape(name)}</b> now.\n\n"
        "Example:\n"
        "<code>@ANIFLIXANIMETAMIL -{anime} S{season} E{episode} "
        "[{quality}][ {language} ].{ext}</code>\n\n"
        "Placeholders: {anime}, {season}, {episode}, {quality}, "
        "{language}, {ext}",
        parse_mode=ParseMode.HTML,
    )


async def templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_default_template(user_id)
    with db() as conn:
        rows = conn.execute(
            "SELECT name, body, is_default FROM templates WHERE user_id=? ORDER BY name",
            (user_id,),
        ).fetchall()
    lines = ["📚 <b>Your saved templates</b>"]
    for name, body, is_default in rows:
        marker = " ⭐ <i>default</i>" if is_default else ""
        lines.append(f"\n<b>{html.escape(name)}</b>{marker}\n<code>{html.escape(body)}</code>")
    lines.append("\nUse /default name to select one.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def deletetemplate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /deletetemplate template_name")
        return
    name = context.args[0].strip().lower()
    user_id = update.effective_user.id
    with db() as conn:
        row = conn.execute(
            "SELECT is_default FROM templates WHERE user_id=? AND name=?",
            (user_id, name),
        ).fetchone()
        if not row:
            await update.message.reply_text("That template was not found. Use /templates.")
            return
        conn.execute("DELETE FROM templates WHERE user_id=? AND name=?", (user_id, name))
        if row[0]:
            next_row = conn.execute(
                "SELECT name FROM templates WHERE user_id=? ORDER BY name LIMIT 1",
                (user_id,),
            ).fetchone()
            if next_row:
                conn.execute(
                    "UPDATE templates SET is_default=1 WHERE user_id=? AND name=?",
                    (user_id, next_row[0]),
                )
    await update.message.reply_text(f"🗑️ Deleted template: {html.escape(name)}", parse_mode=ParseMode.HTML)


async def set_default(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /default template_name")
        return
    name = context.args[0].strip().lower()
    user_id = update.effective_user.id
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM templates WHERE user_id=? AND name=?", (user_id, name)
        ).fetchone()
        if not row:
            await update.message.reply_text("Template not found. Use /templates.")
            return
        conn.execute("UPDATE templates SET is_default=0 WHERE user_id=?", (user_id,))
        conn.execute(
            "UPDATE templates SET is_default=1 WHERE user_id=? AND name=?",
            (user_id, name),
        )
    await update.message.reply_text(f"⭐ Default template set to <b>{html.escape(name)}</b>.", parse_mode=ParseMode.HTML)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    # The next message after /settemplate is treated as the template body.
    if context.user_data.get("awaiting_template"):
        name = context.user_data.pop("awaiting_template")
        valid, error = validate_template(text)
        if not valid:
            await update.message.reply_text(
                f"❌ {html.escape(error)}\nPlease run /settemplate and try again.",
                parse_mode=ParseMode.HTML,
            )
            return
        user_id = update.effective_user.id
        with db() as conn:
            conn.execute(
                "INSERT INTO templates(user_id,name,body,is_default) VALUES(?,?,?,0) "
                "ON CONFLICT(user_id,name) DO UPDATE SET body=excluded.body",
                (user_id, name, text),
            )
            count = conn.execute(
                "SELECT COUNT(*) FROM templates WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            if count == 1:
                conn.execute(
                    "UPDATE templates SET is_default=1 WHERE user_id=? AND name=?",
                    (user_id, name),
                )
        await update.message.reply_text(
            f"✅ Template <b>{html.escape(name)}</b> saved.\n"
            f"Use /default {html.escape(name)} to make it active.",
            parse_mode=ParseMode.HTML,
        )
        return

    parsed = parse_input(text)
    if parsed:
        await generate(update, context, parsed)
        return

    # Support the three-step input: anime name, season, episode.
    stage = context.user_data.get("input_stage", 0)
    if stage == 0:
        context.user_data["anime_name"] = text
        context.user_data["input_stage"] = 1
        await update.message.reply_text("📺 Anime name saved. Now send the season, e.g. <code>Season 1</code>.", parse_mode=ParseMode.HTML)
    elif stage == 1:
        match = re.search(r"\d+", text)
        if not match:
            await update.message.reply_text("Please send a season like <code>Season 1</code>.", parse_mode=ParseMode.HTML)
            return
        context.user_data["season_num"] = int(match.group())
        context.user_data["input_stage"] = 2
        await update.message.reply_text("🔢 Now send the episode number, e.g. <code>03</code>.", parse_mode=ParseMode.HTML)
    else:
        match = re.search(r"\d+", text)
        if not match:
            await update.message.reply_text("Please send an episode number, e.g. <code>03</code>.", parse_mode=ParseMode.HTML)
            return
        parsed = {
            "anime": context.user_data.pop("anime_name"),
            "season": f"{context.user_data.pop('season_num'):02d}",
            "episode": f"{int(match.group()):02d}",
        }
        context.user_data["input_stage"] = 0
        await generate(update, context, parsed)


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE, data):
    name, template = get_default_template(update.effective_user.id)
    blocks = []
    for quality in QUALITIES:
        try:
            filename = template.format(
                anime=data["anime"],
                season=data["season"],
                episode=data["episode"],
                quality=quality,
                language="Tamil",
                ext="mkv",
            )
        except Exception:
            await update.message.reply_text("❌ The active template has a formatting problem. Check /templates.")
            return
        blocks.append(
            f"{QUALITY_BADGES[quality]} <b>{quality}</b>\n"
            f"<b>{html.escape(filename)}</b>"
        )
    await update.message.reply_text(
        "✨ <b>Generated filenames</b>\n\n" + "\n\n".join(blocks),
        parse_mode=ParseMode.HTML,
    )


def main():
    if not BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in your .env file first.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settemplate", settemplate))
    app.add_handler(CommandHandler("templates", templates))
    app.add_handler(CommandHandler("deletetemplate", deletetemplate))
    app.add_handler(CommandHandler("default", set_default))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot is running.")
    app.run_polling()


if __name__ == "__main__":
    main()
