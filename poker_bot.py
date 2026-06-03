import random
import os
import json
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from treys import Card, Evaluator

# =========================
# CONFIG
# =========================
import os
TOKEN = os.environ["8081123271:AAEzxf2OgJ-sG3DtRGEoEMzlUSlFMmHjf9A"] 
DATA_FILE = "casino_data.json"

GRUPPI_AUTORIZZATI = [
    -1003664350829,
    -1002229066951,
]

OWNER_ID = 977247490

evaluator = Evaluator()

# =========================
# DB
# =========================
def load():
    if not os.path.exists(DATA_FILE):
        return {"games": {}, "users": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save(db):
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

db = load()
games = db["games"]
users = db["users"]

def save_all():
    db["games"] = games
    db["users"] = users
    save(db)

# =========================
# USER
# =========================
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"chips": 5000, "last_daily": None}
    return users[uid]

# =========================
# DECK
# =========================
def deck():
    s = ['s','h','d','c']
    r = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    d = [x+y for x in r for y in s]
    random.shuffle(d)
    return d

# =========================
# KEYBOARD
# =========================
def kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="join"),
            InlineKeyboardButton("🚪 ESCI", callback_data="leave"),
        ],
        [InlineKeyboardButton("🎲 START", callback_data="start")],
    ])

# =========================
# BASIC COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎰 Casino Poker Online ATTIVO")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Chips: {u['chips']}")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id)

    now = datetime.utcnow()
    last = u["last_daily"]

    if last:
        last_time = datetime.fromisoformat(last)
        if now - last_time < timedelta(hours=24):
            return await update.message.reply_text("⏳ Daily già preso")

    u["chips"] += 1000
    u["last_daily"] = now.isoformat()
    save_all()

    await update.message.reply_text("🎁 +1000 chips daily!")

# =========================
# POKER
# =========================
async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)

    if cid in games:
        return await update.message.reply_text("⚠️ Già attivo")

    games[cid] = {
        "players": [],
        "deck": [],
        "board": [],
        "phase": "lobby"
    }

    save_all()

    await update.message.reply_text("🃏 LOBBY APERTA", reply_markup=kb())

# =========================
# CALLBACK
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = str(q.message.chat.id)
    user = q.from_user

    if cid not in games:
        return await q.edit_message_text("❌ Nessuna partita")

    g = games[cid]

    if q.data == "join":
        if any(p["id"] == user.id for p in g["players"]):
            return await q.answer("Già dentro")

        g["players"].append({
            "id": user.id,
            "name": user.first_name,
            "chips": 5000,
            "hand": [],
            "fold": False
        })

        save_all()
        return await q.edit_message_text("✔️ Entrato")

    if q.data == "leave":
        g["players"] = [p for p in g["players"] if p["id"] != user.id]
        save_all()
        return await q.edit_message_text("🚪 Uscito")

    if q.data == "start":
        if len(g["players"]) < 2:
            return await q.answer("Min 2 player")

        g["deck"] = deck()
        g["board"] = []

        for p in g["players"]:
            p["hand"] = [g["deck"].pop(), g["deck"].pop()]
            p["fold"] = False

        save_all()
        return await q.edit_message_text("🟢 Partita iniziata")

# =========================
# MAIN (FIX RENDER SAFE)
# =========================
def main():
    print("🟢 BOT START")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("poker", poker))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("top", top))

    app.add_handler(CallbackQueryHandler(buttons))

    # FIX STABILE RENDER / TELEGRAM
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()
