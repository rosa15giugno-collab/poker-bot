import os
import random
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================
TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "casino.json"

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
users = db.get("users", {})
games = db.get("games", {})

def save_all():
    db["users"] = users
    db["games"] = games
    save(db)

# =========================
# USERS
# =========================
def get_user(uid, name=None):
    uid = str(uid)

    if uid not in users:
        users[uid] = {
            "chips": 5000,
            "name": name or "Player"
        }
        save_all()

    return users[uid]

# =========================
# CARDS
# =========================
def deck():
    suits = ['♠️', '♥️', '♦️', '♣️']
    ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
    cards = [r + s for r in ranks for s in suits]
    random.shuffle(cards)
    return cards

# =========================
# BLACKJACK LOGIC
# =========================
def hand_value(hand):
    values = {
        '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
        '10':10,'J':10,'Q':10,'K':10,'A':11
    }

    total = 0
    aces = 0

    for c in hand:
        r = c[:-1]
        total += values[r]
        if r == "A":
            aces += 1

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🎰 Casino Bot ONLINE")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(f"💰 Chips: {u['chips']}")

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA\n\n"
    for i, (uid, u) in enumerate(top, 1):
        msg += f"{i}. {u['name']} - {u['chips']}\n"

    await update.message.reply_text(msg)

# =========================
# BLACKJACK
# =========================
async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    games[cid] = {
        "type": "blackjack",
        "deck": d,
        "player": player,
        "dealer": dealer
    }

    save_all()

    await update.message.reply_text(
        f"🃏 BLACKJACK\n\n"
        f"Tu: {player} ({hand_value(player)})\n"
        f"Dealer: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("HIT", callback_data="hit"),
                InlineKeyboardButton("STAND", callback_data="stand")
            ]
        ])
    )

# =========================
# CALLBACKS
# =========================
async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = str(q.message.chat.id)

    if cid not in games:
        return await q.edit_message_text("❌ Nessun gioco attivo")

    g = games[cid]

    if g["type"] != "blackjack":
        return

    d = g["deck"]
    p = g["player"]
    dealer = g["dealer"]

    if q.data == "hit":
        p.append(d.pop())

        if hand_value(p) > 21:
            games.pop(cid, None)
            save_all()
            return await q.edit_message_text(f"💥 Sballato!\n{p}")

        save_all()

        return await q.edit_message_text(
            f"🃏 BLACKJACK\n\nTu: {p} ({hand_value(p)})"
        )

    if q.data == "stand":
        while hand_value(dealer) < 17:
            dealer.append(d.pop())

        pv = hand_value(p)
        dv = hand_value(dealer)

        if dv > 21 or pv > dv:
            result = "🎉 VINCI!"
        elif pv == dv:
            result = "🤝 PAREGGIO"
        else:
            result = "💀 PERDI"

        games.pop(cid, None)
        save_all()

        return await q.edit_message_text(
            f"🃏 RISULTATO\n\n"
            f"Tu: {p} ({pv})\n"
            f"Dealer: {dealer} ({dv})\n\n"
            f"{result}"
        )

# =========================
# MAIN
# =========================
def main():
    print("🟢 CASINO BOT ONLINE")

    if not TOKEN:
        raise ValueError("❌ BOT_TOKEN mancante nelle variabili ambiente")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CallbackQueryHandler(cb))

    app.run_polling()

if __name__ == "__main__":
    main()
