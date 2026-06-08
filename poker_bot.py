import os
import json
import random
import time
print ("MODULO MODIFICATO")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")

PORT = int(os.getenv("PORT", 8080))

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante")


DATA_FILE = "casino_db.json"

print("🟢 CASINO BOT ONLINE PID:", os.getpid())

# =========================
# HEALTH SERVER (RAILWAY FIX)
# =========================



# =========================
# DATABASE
# =========================

def load():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}}

def save(db):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f)
    os.replace(tmp, DATA_FILE)

db = load()
users = db.get("users", {})
db["users"] = users

def save_all():
    db["users"] = users
    save(db)

# =========================
# UTENTE
# =========================

def get_user(uid, name="Giocatore"):
    uid = str(uid)

    if uid not in users:
        users[uid] = {
            "name": name,
            "chips": 5000,
            "wins": 0,
            "losses": 0,
            "best_win": 0,
            "last_daily": 0
        }
        save_all()

    return users[uid]

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 Slot Machine", callback_data="slot")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("💰 Il mio saldo", callback_data="saldo")],
        [InlineKeyboardButton("🎁 Bonus giornaliero", callback_data="bonus")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ]

    await update.message.reply_text(
        "🎰 CASINO BOT PRO\n\nScegli un gioco:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# SALDO
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Saldo: {u['chips']} chips", parse_mode="Markdown")

# =========================
# BONUS
# =========================

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    now = int(time.time())
    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Hai già preso il bonus giornaliero oggi")

    reward = random.randint(500, 2500)
    u["chips"] += reward
    u["last_daily"] = now
    save_all()

    await update.message.reply_text(f"🎁 Hai ricevuto {reward} chips!", parse_mode="Markdown")

# =========================
# SLOT
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    bet = int(context.args[0]) if context.args else 100

    if bet <= 0:
        return await update.message.reply_text("❌ Puntata non valida")

    if u["chips"] < bet:
        return await update.message.reply_text("❌ Non hai abbastanza chips")

    u["chips"] -= bet

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = bet * 10
    elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
        win = bet * 3

    u["chips"] += win
    save_all()

    msg = (
        "🎰 SLOT MACHINE\n\n"
        f"{r[0]} | {r[1]} | {r[2]}\n\n"
        + ("🎉 Hai vinto " + str(win) + " chips!" if win else "💀 Hai perso")
        + f"\n💰 Saldo: {u['chips']} chips"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

# =========================
# BLACKJACK
# =========================

blackjack_games = {}

def deck():
    cards = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
    d = cards * 4
    random.shuffle(d)
    return d

def value(hand):
    v = 0
    aces = 0

    for c in hand:
        if c in ["J","Q","K"]:
            v += 10
        elif c == "A":
            v += 11
            aces += 1
        else:
            v += int(c)

    while v > 21 and aces:
        v -= 10
        aces -= 1

    return v

async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    u = get_user(uid)

    bet = int(context.args[0]) if context.args else 100

    if bet <= 0:
        return await update.message.reply_text("❌ Puntata non valida")

    if u["chips"] < bet:
        return await update.message.reply_text("❌ Non hai abbastanza chips")

    u["chips"] -= bet

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    blackjack_games[uid] = {
        "deck": d,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    keyboard = [[
        InlineKeyboardButton("CARTA (HIT)", callback_data="hit"),
        InlineKeyboardButton("STAI (STAND)", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\n\nTU: {player} ({value(player)})\nMAZZIERE: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ROULETTE
# =========================

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    bet = int(context.args[0]) if context.args else 100

    if bet <= 0:
        return await update.message.reply_text("❌ Puntata non valida")

    if u["chips"] < bet:
        return await update.message.reply_text("❌ Non hai abbastanza chips")

    u["chips"] -= bet

    result = random.randint(0, 36)

    if result == 0:
        win = bet * 14
    elif result % 2 == 0:
        win = bet * 2
    else:
        win = 0

    u["chips"] += win
    save_all()

    msg = (
        "🎲 ROULETTE\n\n"
        f"Numero uscito: {result}\n\n"
        + ("🎉 Hai vinto " + str(win) + " chips!" if win else "💀 Hai perso")
        + f"\n💰 Saldo: {u['chips']}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")

# =========================
# CLASSIFICA
# =========================

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.values(), key=lambda x: x["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA TOP 10\n\n"

    for i, u in enumerate(top, 1):
        msg += f"{i}. {u['name']} — {u['chips']} chips\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    if q.data == "saldo":
        return await q.message.reply_text(f"💰 Saldo: {u['chips']} chips")

    if q.data == "slot":
        return await q.message.reply_text("🎰 Usa: /slot 100")

    if q.data == "blackjack":
        return await q.message.reply_text("🃏 Usa: /blackjack 100")

    if q.data == "roulette":
        return await q.message.reply_text("🎲 Usa: /roulette 100")

    if q.data == "bonus":
        return await bonus(update, context)

    if q.data == "classifica":
        return await classifica(update, context)

# =========================
# MAIN
# =========================

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("bonus", bonus))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("blackjack", blackjack_cmd))
    app.add_handler(CommandHandler("roulette", roulette))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
