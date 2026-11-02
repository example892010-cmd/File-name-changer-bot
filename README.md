# Anime Filename Generator Bot

A Telegram bot that creates three filename variants (480p, 720p, 1080p) from an anime name, season, and episode. Templates are stored in SQLite and survive restarts.

## Features

- Accepts three separate messages (`Naruto`, `Season 1`, `03`) or all three lines in one message.
- Generates 480p, 720p, and 1080p filenames every time.
- Saves, lists, selects, and deletes named filename templates.
- Uses bold Telegram formatting and coloured emoji quality markers.
- Keeps each user's templates separate in a local SQLite database.

> Telegram Bot API text messages do not support arbitrary font colours. The bot uses coloured emoji markers and bold text instead.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Install Python 3.10 or newer.
3. Copy `.env.example` to `.env` and add your token.
4. Install dependencies and run:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
python bot.py
```

Set the token in your environment if you do not use a `.env` loader:

```bash
# macOS / Linux
export BOT_TOKEN="YOUR_TOKEN"
python bot.py

# Windows PowerShell
$env:BOT_TOKEN="YOUR_TOKEN"
python bot.py
```

## Commands

- `/start` — instructions
- `/settemplate` — save/update the `default` template
- `/settemplate web` — save/update a template named `web`
- `/templates` — list saved templates
- `/default web` — make `web` the active template
- `/deletetemplate web` — delete a template
- `/help` — instructions

When prompted by `/settemplate`, send the template as the next message.

## Supported placeholders

| Placeholder | Example |
|---|---|
| `{anime}` | `Naru` |
| `{season}` | `01` |
| `{episode}` | `03` |
| `{quality}` | `480p`, `720p`, or `1080p` |
| `{language}` | `Tamil` |
| `{ext}` | `mkv` |

Default template:

```text
@ANIFLIXANIMETAMIL -{anime} S{season} E{episode} [{quality}][ {language} ].{ext}
```

## Example

Input:

```text
Naru
Season 1
03
```

Output:

```text
@ANIFLIXANIMETAMIL -Naru S01 E03 [480p][ Tamil ].mkv
@ANIFLIXANIMETAMIL -Naru S01 E03 [720p][ Tamil ].mkv
@ANIFLIXANIMETAMIL -Naru S01 E03 [1080p][ Tamil ].mkv
```

## Notes

- Keep the bot process running for the bot to respond.
- Back up `bot.db` if you want to preserve your templates when moving servers.
- Do not share your bot token. If it is exposed, revoke it through BotFather and create a new one.
