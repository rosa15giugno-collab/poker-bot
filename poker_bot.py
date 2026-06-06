import os
import random
import json
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

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))

print("🟢 CASINO BOT STARTING")
print("TOKEN:", "OK" if TOKEN else "MISSING")

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante")

# =========================
# DATABASE
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
    await update.message.reply_text(
        "🎰 CASINO BOT ONLINE\n\nComandi:\n/start\n/saldo\n/blackjack\n/slot\n/daily\n/classifica"
    )

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
        return await update.message.reply_text("⏳ Hai già preso il daily!")

    reward = random.randint(500, 1500)
    u["chips"] += reward
    u["last_daily"] = now
    save_all()

    await update.message.reply_text(f"🎁 Daily: +{reward} chips")

# =========================
# CLASSIFICA
# =========================
async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA\n\n"
    for i, (uid, u) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🎯"
        msg += f"{medal} {i}. {u['name']} — {u['chips']}\n"

    await update.message.reply_text(msg)

# =========================
# SLOT
# =========================
async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    if u["chips"] < 100:
        return await update.message.reply_text("❌ Non hai abbastanza chips")

    u["chips"] -= 100

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 2000
    elif len(set(r)) == 2:
        win = 500

    u["chips"] += win
    save_all()

    await update.message.reply_text(
        f"🎰 SLOT\n\n{r[0]} | {r[1]} | {r[2]}\n\n"
        f"{'🎉 VINTO +' + str(win) if win else '💀 PERSO'}"
    )

# =========================
# BLACKJACK
# =========================
def deck():
    suits = ["♠️", "♥️", "♦️", "♣️"]
    ranks = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
    cards = [r + s for r in ranks for s in suits]
    random.shuffle(cards)
    return cards

def hand_value(hand):
    values = {
        "2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,
        "10":10,"J":10,"Q":10,"K":10,"A":11
    }

    total = 0
    aces = 0

    for c in hand:
        r = "10" if c.startswith("10") else c[0]
        total += values[r]
        if r == "A":
            aces += 1

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    games[cid] = {
        "deck": d,
        "player": player,
        "dealer": dealer
    }

    save_all()

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="hit"),
        InlineKeyboardButton("STAND", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\n\n"
        f"Tu: {player} ({hand_value(player)})\n"
        f"Dealer: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK
# =========================
async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = str(q.message.chat.id)

    if cid not in games:
        return await q.message.reply_text("❌ Nessun gioco attivo")

    g = games[cid]
    d = g["deck"]
    p = g["player"]
    dealer = g["dealer"]

    if q.data == "hit":
        p.append(d.pop())

        if hand_value(p) > 21:
            games.pop(cid)
            save_all()
            return await q.message.reply_text(f"💥 Sballato!\n{p}")

        save_all()
        return await q.message.reply_text(f"🃏 Tu: {p} ({hand_value(p)})")

    if q.data == "stand":
        while hand_value(dealer) < 17:
            dealer.append(d.pop())

        pv = hand_value(p)
        dv = hand_value(dealer)

        if pv > 21:
            result = "💀 PERDI"
        elif dv > 21 or pv > dv:
            result = "🎉 VINCI"
        elif pv == dv:
            result = "🤝 PAREGGIO"
        else:
            result = "💀 PERDI"

        games.pop(cid)
        save_all()

        return await q.message.reply_text(
            f"🃏 RISULTATO\n\n"
            f"Tu: {p} ({pv})\n"
            f"Dealer: {dealer} ({dv})\n\n"
            f"{result}"
        )

# =========================
# MAIN WEBHOOK
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO BOT WEBHOOK ONLINE")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
