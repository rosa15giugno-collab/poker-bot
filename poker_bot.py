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

# =========================
# CONFIG
# =========================
TOKEN = os.environ.get("TOKEN")
DATA_FILE = "casino_data.json"

OWNER_ID = 977247490

# =========================
# DB
# =========================
def load():
    if not os.path.exists(DATA_FILE):
        return {"games": {}, "users": {}}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"games": {}, "users": {}}

def save(db):
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

db = load()
games = db.get("games", {})
users = db.get("users", {})

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
    s = ['♠️', '♥️', '♦️', '♣️']
    r = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
    d = [x+y for x in r for y in s]
    random.shuffle(d)
    return d

# =========================
# TASTIERA
# =========================
def kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="join"),
            InlineKeyboardButton("🚪 ESCI", callback_data="leave"),
        ],
        [InlineKeyboardButton("🎲 INIZIA PARTITA", callback_data="start")],
    ])

# =========================
# COMANDI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎰 Casinò Poker Online ATTIVO 🇮🇹")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Hai {u['chips']} chips")

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id)

    now = datetime.utcnow()
    last = u["last_daily"]

    if last:
        last_time = datetime.fromisoformat(last)
        if now - last_time < timedelta(hours=24):
            return await update.message.reply_text("⏳ Hai già preso il bonus oggi")

    u["chips"] += 1000
    u["last_daily"] = now.isoformat()
    save_all()

    await update.message.reply_text("🎁 Bonus giornaliero +1000 chips!")

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    text = "🏆 CLASSIFICA GIOCATORI:\n\n"
    for i, (uid, u) in enumerate(ranking, 1):
        text += f"{i}. {u.get('name','Player')} - {u['chips']} chips\n"

    await update.message.reply_text(text)

# =========================
# POKER
# =========================
async def gioca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)

    if cid in games:
        return await update.message.reply_text("⚠️ Partita già attiva")

    games[cid] = {
        "players": [],
        "deck": [],
        "board": [],
        "phase": "lobby"
    }

    save_all()
    await update.message.reply_text("🃏 Lobby aperta! Entra nella partita 🎲", reply_markup=kb())

# =========================
# CALLBACK BOTTONI
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = str(q.message.chat.id)
    user = q.from_user

    if cid not in games:
        return await q.edit_message_text("❌ Nessuna partita attiva")

    g = games[cid]

    if q.data == "join":
        if any(p["id"] == user.id for p in g["players"]):
            return await q.answer("Sei già dentro")

        g["players"].append({
            "id": user.id,
            "name": user.first_name,
            "chips": 5000,
            "hand": [],
            "fold": False
        })

        save_all()
        return await q.edit_message_text("✔️ Sei entrato nella partita")

    if q.data == "leave":
        g["players"] = [p for p in g["players"] if p["id"] != user.id]
        save_all()
        return await q.edit_message_text("🚪 Sei uscito dalla partita")

    if q.data == "start":
        if len(g["players"]) < 2:
            return await q.answer("Servono almeno 2 giocatori")

        g["deck"] = deck()
        g["board"] = []

        for p in g["players"]:
            p["hand"] = [g["deck"].pop(), g["deck"].pop()]
            p["fold"] = False

        save_all()
        return await q.edit_message_text("🟢 Partita iniziata!")

# =========================
# MAIN (WEBHOOK)
# =========================
def main():
    print("🟢 BOT AVVIATO")

    if not TOKEN:
        print("❌ TOKEN mancante")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # COMANDI ITALIANI
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gioca", gioca))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("bonus", bonus))
    app.add_handler(CommandHandler("classifica", classifica))

    app.add_handler(CallbackQueryHandler(buttons))

    # WEBHOOK (RENDER)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
