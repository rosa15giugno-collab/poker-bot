import os
import json
import random
import time

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
TOKEN = os.getenv("CASINO_TOKEN")
DATA_FILE = "casino.json"

print("🟢 CASINO PRO BOT STARTING")
print("TOKEN:", "OK" if TOKEN else "MISSING")

if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

# =========================
# DB
# =========================
def load():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "games": {}}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}, "games": {}}

def save(db):
    with open(DATA_FILE, "w") as f:
        json.dump(db, f)

db = load()
users = db["users"]
games = db["games"]

def save_all():
    db["users"] = users
    db["games"] = games
    save(db)

# =========================
# EVENT SYSTEM (🔥 PRO)
# =========================
ACTIVE_EVENT = None
EVENT_END = 0

def trigger_event():
    global ACTIVE_EVENT, EVENT_END

    roll = random.randint(1, 100)

    if roll < 70:
        ACTIVE_EVENT = None
        return None

    if roll < 80:
        ACTIVE_EVENT = ("💣 BLACKOUT", 0)   # niente vincite
        EVENT_END = time.time() + 60

    elif roll < 90:
        ACTIVE_EVENT = ("⚡ DOUBLE CHIPS", 2)
        EVENT_END = time.time() + 90

    else:
        ACTIVE_EVENT = ("🍀 LUCKY HOUR", 3)
        EVENT_END = time.time() + 60

    print("EVENT STARTED:", ACTIVE_EVENT)
    return ACTIVE_EVENT

def get_multiplier():
    global ACTIVE_EVENT, EVENT_END

    if ACTIVE_EVENT and time.time() > EVENT_END:
        ACTIVE_EVENT = None

    if not ACTIVE_EVENT:
        return 1

    return ACTIVE_EVENT[1]

# =========================
# USER SYSTEM
# =========================
def get_user(uid, name="Player"):
    uid = str(uid)

    if uid not in users:
        users[uid] = {
            "chips": 5000,
            "name": name,
            "last_daily": 0
        }
        save_all()

    return users[uid]

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    msg = "🎰 CASINO PRO BOT ONLINE\n\n"

    if ACTIVE_EVENT:
        msg += f"🔥 EVENTO ATTIVO: {ACTIVE_EVENT[0]}\n\n"

    msg += "Comandi:\n/start\n/saldo\n/daily\n/slot\n/blackjack"

    await update.message.reply_text(msg)

# =========================
# SALDO
# =========================
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(f"💰 Chips: {u['chips']}")

# =========================
# DAILY
# =========================
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    now = int(time.time())
    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Hai già preso il daily")

    reward = random.randint(500, 1500)
    reward *= get_multiplier()

    u["chips"] += reward
    u["last_daily"] = now
    save_all()

    await update.message.reply_text(f"🎁 Daily: +{reward} chips")

# =========================
# SLOT
# =========================
async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    if u["chips"] < 100:
        return await update.message.reply_text("❌ Non hai chips")

    u["chips"] -= 100

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]

    win = 0

    if ACTIVE_EVENT and ACTIVE_EVENT[0] == "💣 BLACKOUT":
        win = 0
    else:
        if result[0] == result[1] == result[2]:
            win = 2000
        elif len(set(result)) == 2:
            win = 500

        win *= get_multiplier()

    u["chips"] += win
    save_all()

    msg = f"🎰 SLOT\n\n{result[0]} | {result[1]} | {result[2]}\n\n"

    if ACTIVE_EVENT:
        msg += f"🔥 EVENTO: {ACTIVE_EVENT[0]}\n\n"

    msg += "🎉 VINTO +" + str(win) if win else "💀 PERSO"

    await update.message.reply_text(msg)

# =========================
# BLACKJACK (base)
# =========================
def deck():
    suits = ["♠️", "♥️", "♦️", "♣️"]
    ranks = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
    cards = [r + s for r in ranks for s in suits]
    random.shuffle(cards)
    return cards

def value(hand):
    vals = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,
            "10":10,"J":10,"Q":10,"K":10,"A":11}

    total = 0
    aces = 0

    for c in hand:
        r = "10" if c.startswith("10") else c[0]
        total += vals[r]
        if r == "A":
            aces += 1

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)

    d = deck()
    p = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    games[cid] = {"deck": d, "p": p, "d": dealer}
    save_all()

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="hit"),
        InlineKeyboardButton("STAND", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\n\nTu: {p} ({value(p)})\nDealer: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = str(q.message.chat.id)

    if cid not in games:
        return await q.message.reply_text("❌ Nessuna partita")

    g = games[cid]
    d = g["deck"]
    p = g["p"]
    dealer = g["d"]

    if q.data == "hit":
        p.append(d.pop())

        if value(p) > 21:
            games.pop(cid)
            save_all()
            return await q.message.reply_text("💥 Sballato!")

        return await q.message.reply_text(f"🃏 Tu: {p} ({value(p)})")

    if q.data == "stand":
        while value(dealer) < 17:
            dealer.append(d.pop())

        pv = value(p)
        dv = value(dealer)

        if dv > 21 or pv > dv:
            result = "🎉 VINCI"
        elif pv == dv:
            result = "🤝 PAREGGIO"
        else:
            result = "💀 PERDI"

        games.pop(cid)
        save_all()

        return await q.message.reply_text(
            f"🃏 RISULTATO\n\nTu: {p} ({pv})\nDealer: {dealer} ({dv})\n\n{result}"
        )

# =========================
# EVENT LOOP (🔥 IMPORTANT)
# =========================
def maybe_event():
    if random.randint(1, 5) == 1:
        trigger_event()

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO ONLINE")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
