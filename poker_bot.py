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

print("🟢 CASINO BOT STARTING")
print("TOKEN:", "OK" if TOKEN else "MISSING")

if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

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
            "last_daily": 0,
            "cooldown": 0
        }
        save_all()

    return users[uid]

# =========================
# COOLDOWN
# =========================
def check_cooldown(u, seconds=3):
    now = time.time()
    if now - u.get("cooldown", 0) < seconds:
        return False
    u["cooldown"] = now
    return True

# =========================
# DECK (BLACKJACK)
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

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(
        "🎰 CASINO PRO BOT ONLINE\n\n"
        "Comandi:\n"
        "/blackjack\n"
        "/slot\n"
        "/roulette\n"
        "/saldo\n"
        "/daily\n"
        "/pay @user amount\n"
        "/classifica"
    )

# =========================
# SALDO
# =========================
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(f"💰 Chips: {u['chips']}")

# =========================
# CLASSIFICA
# =========================
async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA\n\n"
    for i, (uid, u) in enumerate(top, 1):
        msg += f"{i}. {u['name']} - {u['chips']}\n"

    await update.message.reply_text(msg)

# =========================
# DAILY
# =========================
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    now = time.time()
    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Daily già preso!")

    reward = random.randint(500, 2000)
    u["chips"] += reward
    u["last_daily"] = now
    save_all()

    await update.message.reply_text(f"🎁 Daily +{reward} chips")

# =========================
# SLOT
# =========================
async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    if not check_cooldown(u): return await update.message.reply_text("⏳ Cooldown!")

    if u["chips"] < 100:
        return await update.message.reply_text("❌ Non hai chips")

    u["chips"] -= 100

    symbols = ["🍒","🍋","🍇","💎","7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 3000
    elif len(set(r)) == 2:
        win = 700

    u["chips"] += win
    save_all()

    await update.message.reply_text(
        f"🎰 SLOT\n{r[0]} | {r[1]} | {r[2]}\n\n"
        f"{'🎉 +'+str(win) if win else '💀 LOSS'}"
    )

# =========================
# ROULETTE
# =========================
async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    if not check_cooldown(u): return await update.message.reply_text("⏳ Cooldown!")

    if len(context.args) < 2:
        return await update.message.reply_text("Uso: /roulette red 100")

    color = context.args[0].lower()
    bet = int(context.args[1])

    if u["chips"] < bet:
        return await update.message.reply_text("❌ Non hai chips")

    result = random.choice(["red", "black", "green"])

    u["chips"] -= bet

    if color == result:
        win = bet * (14 if result == "green" else 2)
        u["chips"] += win
        msg = f"🎉 VINTO {win}"
    else:
        msg = "💀 PERSO"

    save_all()

    await update.message.reply_text(f"🎲 Roulette: {result}\n{msg}")

# =========================
# PAY
# =========================
async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Uso: /pay user amount")

    sender = get_user(update.effective_user.id, update.effective_user.first_name)

    try:
        amount = int(context.args[1])
    except:
        return await update.message.reply_text("Numero non valido")

    if sender["chips"] < amount:
        return await update.message.reply_text("❌ Non hai chips")

    sender["chips"] -= amount

    receiver_id = context.args[0].replace("@","")
    receiver = None

    for uid, u in users.items():
        if u["name"].lower() == receiver_id.lower():
            receiver = u
            break

    if not receiver:
        return await update.message.reply_text("Utente non trovato")

    receiver["chips"] += amount
    save_all()

    await update.message.reply_text("💸 Trasferimento completato")

# =========================
# BLACKJACK
# =========================
async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    games[cid] = {"deck": d, "player": player, "dealer": dealer}
    save_all()

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="hit"),
        InlineKeyboardButton("STAND", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\nTu: {player} ({hand_value(player)})\nDealer: [{dealer[0]}, ?]",
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
        return await q.message.reply_text("❌ Nessun gioco")

    g = games[cid]
    d = g["deck"]
    p = g["player"]
    dealer = g["dealer"]

    if q.data == "hit":
        p.append(d.pop())
        if hand_value(p) > 21:
            games.pop(cid)
            save_all()
            return await q.message.reply_text("💥 Sballato")
        save_all()
        return await q.message.reply_text(f"Tu: {p} ({hand_value(p)})")

    if q.data == "stand":
        while hand_value(dealer) < 17:
            dealer.append(d.pop())

        pv, dv = hand_value(p), hand_value(dealer)

        if dv > 21 or pv > dv:
            res = "🎉 VINCI"
        elif pv == dv:
            res = "🤝 PAREGGIO"
        else:
            res = "💀 PERDI"

        games.pop(cid)
        save_all()

        return await q.message.reply_text(
            f"RISULTATO\nTu: {p} ({pv})\nDealer: {dealer} ({dv})\n{res}"
        )

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("roulette", roulette))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO BOT ONLINE")
    app.bot.delete_webhook(drop_pending_updates=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
