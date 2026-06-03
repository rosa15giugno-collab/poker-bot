import random
import os
import json
import threading
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from treys import Card, Evaluator

# =========================
# CONFIG
# =========================
TOKEN = "8081123271:AAG4roWz5LRsD0SvxBoezCWG2TDvj_9zG50"
DATA_FILE = "casino_data.json"

GRUPPI_AUTORIZZATI = [
    -1003664350829,
    -1002229066951,
]

OWNER_ID = 977247490

evaluator = Evaluator()

# =========================
# DATA
# =========================
def load():
    if not os.path.exists(DATA_FILE):
        return {"games": {}, "users": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

db = load()
games = db["games"]
users = db["users"]

# =========================
# UTILS
# =========================
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"chips": 5000, "last_daily": None}
    return users[uid]

def deck():
    s = ['s','h','d','c']
    r = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    d = [x+y for x in r for y in s]
    random.shuffle(d)
    return d

def save_all():
    db["games"] = games
    db["users"] = users
    save(db)

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
        [
            InlineKeyboardButton("✔️ CALL", callback_data="call"),
            InlineKeyboardButton("⬆️ RAISE", callback_data="raise"),
        ],
        [
            InlineKeyboardButton("❌ FOLD", callback_data="fold"),
            InlineKeyboardButton("🔥 ALL-IN", callback_data="allin"),
        ],
        [InlineKeyboardButton("➡️ NEXT", callback_data="next")]
    ])

# =========================
# ACCESS
# =========================
async def access(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return user.id == OWNER_ID

    return chat.id in GRUPPI_AUTORIZZATI

# =========================
# COMMANDS BASIC
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
# TOP
# =========================
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]
    text = "🏆 TOP PLAYERS:\n\n"
    for i, (uid, u) in enumerate(ranking, 1):
        text += f"{i}. {uid} - {u['chips']} chips\n"
    await update.message.reply_text(text)

# =========================
# SLOT MACHINE
# =========================
async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id)

    if u["chips"] < 100:
        return await update.message.reply_text("❌ Non hai chips")

    u["chips"] -= 100

    symbols = ["🍒","🍋","🔔","💎","7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]

    win = 0
    if res.count(res[0]) == 3:
        win = 1000

    u["chips"] += win
    save_all()

    await update.message.reply_text(f"{' | '.join(res)}\n{'🏆 VINTO ' + str(win) if win else '😢 Perso'}")

# =========================
# ROULETTE
# =========================
async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = ensure_user(update.effective_user.id)

    if len(context.args) < 1:
        return await update.message.reply_text("Usa /roulette rosso o nero")

    bet = context.args[0].lower()

    if u["chips"] < 100:
        return await update.message.reply_text("❌ Non hai chips")

    u["chips"] -= 100

    result = random.choice(["rosso","nero","verde"])

    if bet == result:
        win = 200
        u["chips"] += win
        msg = f"🎉 VINTO {win}"
    else:
        msg = f"❌ Perso ({result})"

    save_all()
    await update.message.reply_text(msg)

# =========================
# POKER GAME
# =========================
async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await access(update):
        return

    cid = str(update.effective_chat.id)

    if cid in games:
        return await update.message.reply_text("⚠️ Già attivo")

    games[cid] = {
        "players": [],
        "deck": [],
        "board": [],
        "phase": "lobby",
        "turn": 0,
        "pot": 0
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

    # JOIN
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
        return await q.edit_message_text("✔️ Entrato")

    # LEAVE
    if q.data == "leave":
        g["players"] = [p for p in g["players"] if p["id"] != user.id]
        save_all()
        return await q.edit_message_text("🚪 Uscito")

    # START
    if q.data == "start":
        if len(g["players"]) < 2:
            return await q.answer("Min 2 player")

        g["deck"] = deck()
        g["board"] = []
        g["phase"] = "preflop"

        for p in g["players"]:
            p["hand"] = [g["deck"].pop(), g["deck"].pop()]
            p["fold"] = False

        save_all()
        return await q.edit_message_text("🟢 Partita iniziata")

    await q.edit_message_text("🎮 Azione base (versione estesa in arrivo)")

# =========================
# MAIN
# =========================
def main():
    print("🎰 CASINO ONLINE AVVIATO")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("roulette", roulette))
    app.add_handler(CommandHandler("poker", poker))

    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
