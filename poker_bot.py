import random
import os
import json
import threading
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
TOKEN = "8081123271:AAG4roWz5LRsD0SvxBoezCWG2TDvj_9zG50"
DATA_FILE = "data.json"

GRUPPI_AUTORIZZATI = [
    -1003664350829,
    -1002229066951,
]

OWNER_ID = 977247490

evaluator = Evaluator()

# =========================
# DATA LOAD/SAVE
# =========================
def carica_dati():
    if not os.path.exists(DATA_FILE):
        return {"partite": {}, "users": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def salva_dati(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = carica_dati()
partite = data["partite"]
users = data["users"]

# =========================
# ACCESSO
# =========================
async def accesso(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return user.id == OWNER_ID

    return chat.id in GRUPPI_AUTORIZZATI

# =========================
# MAZZO
# =========================
def crea_mazzo():
    semi = ['s', 'h', 'd', 'c']
    valori = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    mazzo = [v + s for v in valori for s in semi]
    random.shuffle(mazzo)
    return mazzo

def giocatori_attivi(p):
    return [g for g in p["giocatori"] if not g["fold"]]

def turno_corrente(p):
    attivi = giocatori_attivi(p)
    if not attivi:
        return None
    return attivi[p["turno"] % len(attivi)]

def next_turn(p):
    p["turno"] += 1

# =========================
# KEYBOARD
# =========================
def tastiera():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="join"),
            InlineKeyboardButton("🚪 ESCI", callback_data="leave"),
        ],
        [InlineKeyboardButton("🎲 START", callback_data="start")],
        [
            InlineKeyboardButton("✔️ CHIAMA", callback_data="call"),
            InlineKeyboardButton("⬆️ RILANCIA", callback_data="raise"),
        ],
        [
            InlineKeyboardButton("❌ FOLD", callback_data="fold"),
            InlineKeyboardButton("🔥 ALL-IN", callback_data="allin"),
        ],
        [InlineKeyboardButton("➡️ NEXT", callback_data="next")]
    ])

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Poker Casino Online 🇮🇹")

async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await accesso(update):
        return

    chat_id = str(update.effective_chat.id)

    if chat_id in partite:
        await update.message.reply_text("⚠️ Partita già attiva")
        return

    partite[chat_id] = {
        "giocatori": [],
        "mazzo": [],
        "comune": [],
        "piatto": 0,
        "turno": 0,
        "fase": "lobby",
        "puntata": 0
    }

    salva_dati(data)

    await update.message.reply_text("🃏 LOBBY APERTA", reply_markup=tastiera())

# =========================
# SALDO
# =========================
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in users:
        users[user_id] = {"chips": 5000, "last_daily": None}

    await update.message.reply_text(f"💰 Chips: {users[user_id]['chips']}")

# =========================
# DAILY
# =========================
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id not in users:
        users[user_id] = {"chips": 5000, "last_daily": None}

    now = datetime.utcnow()
    last = users[user_id]["last_daily"]

    if last:
        last_time = datetime.fromisoformat(last)
        if now - last_time < timedelta(hours=24):
            await update.message.reply_text("⏳ Hai già preso il daily oggi")
            return

    users[user_id]["chips"] += 1000
    users[user_id]["last_daily"] = now.isoformat()

    salva_dati(data)

    await update.message.reply_text("🎁 +1000 chips daily!")

# =========================
# CALLBACK
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat_id = str(q.message.chat.id)
    user = q.from_user

    if chat_id not in partite:
        await q.edit_message_text("❌ Nessuna partita")
        return

    p = partite[chat_id]

    # JOIN
    if q.data == "join":
        if any(x["id"] == user.id for x in p["giocatori"]):
            return await q.answer("Sei già dentro")

        p["giocatori"].append({
            "id": user.id,
            "nome": user.first_name,
            "chips": 5000,
            "mano": [],
            "fold": False,
            "puntata": 0
        })

        salva_dati(data)
        await q.edit_message_text("✔️ Entrato")
        return

    # LEAVE
    if q.data == "leave":
        p["giocatori"] = [x for x in p["giocatori"] if x["id"] != user.id]
        salva_dati(data)
        await q.edit_message_text("🚪 Uscito")
        return

    # START
    if q.data == "start":
        if len(p["giocatori"]) < 2:
            return await q.answer("Min 2 giocatori")

        p["mazzo"] = crea_mazzo()
        p["comune"] = []
        p["piatto"] = 0
        p["turno"] = 0
        p["fase"] = "preflop"

        for g in p["giocatori"]:
            g["mano"] = [p["mazzo"].pop(), p["mazzo"].pop()]
            g["fold"] = False

        salva_dati(data)
        await q.edit_message_text("🟢 Partita iniziata")
        return

    player = turno_corrente(p)

    if not player or player["id"] != user.id:
        return await q.answer("Non è il tuo turno")

    # FOLD
    if q.data == "fold":
        player["fold"] = True
        next_turn(p)
        salva_dati(data)
        await q.edit_message_text("❌ Fold")
        return

    # CALL
    if q.data == "call":
        next_turn(p)
        salva_dati(data)
        await q.edit_message_text("✔️ Call")
        return

    # RAISE
    if q.data == "raise":
        p["puntata"] += 100
        next_turn(p)
        salva_dati(data)
        await q.edit_message_text("⬆️ Raise")
        return

    # ALLIN
    if q.data == "allin":
        player["chips"] = 0
        next_turn(p)
        salva_dati(data)
        await q.edit_message_text("🔥 ALL-IN")
        return

    # NEXT
    if q.data == "next":
        await q.edit_message_text(f"Fase: {p['fase']} ➡️ avanzamento base")

# =========================
# MAIN
# =========================
def main():
    print("🃏 Poker Bot ONLINE")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("poker", poker))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("daily", daily))

    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
