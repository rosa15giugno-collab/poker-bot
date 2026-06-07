import os
import json
import random
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIGURAZIONE
# =========================

TOKEN = os.getenv("CASINO_TOKEN")

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante su Railway")

DATA_FILE = "casino_db.json"

print("🟢 CASINO BOT ONLINE PID:", os.getpid())

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
users = db["users"]

def save_all():
    db["users"] = users
    save(db)

# =========================
# UTENTI
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
# START MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 SLOT", callback_data="slot")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 ROULETTE", callback_data="roulette")],
        [InlineKeyboardButton("💰 SALDO", callback_data="saldo")],
        [InlineKeyboardButton("🎁 DAILY", callback_data="daily")],
        [InlineKeyboardButton("🏆 CLASSIFICA", callback_data="top")]
    ]

    await update.message.reply_text(
        "🎰 CASINO BOT PRO\nScegli un gioco:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        return await update.message.reply_text("⏳ Hai già preso il bonus giornaliero")

    reward = random.randint(500, 2500)
    u["chips"] += reward
    u["last_daily"] = now

    save_all()
    await update.message.reply_text(f"🎁 Bonus +{reward} chips")

# =========================
# SLOT
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            pass

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida")

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

    await update.message.reply_text(
        f"🎰 SLOT\n{r[0]} | {r[1]} | {r[2]}\n"
        f"{'🎉 VINTO +' + str(win) if win else '💀 PERSO'}"
    )

# =========================
# BLACKJACK
# =========================

def deck():
    suits = ["♠️","♥️","♦️","♣️"]
    ranks = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
    d = [r+s for r in ranks for s in suits]
    random.shuffle(d)
    return d

def value(hand):
    vals = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":10,"Q":10,"K":10,"A":11}
    total = 0
    aces = 0

    for c in hand:
        r = c[:-1]
        total += vals[r]
        if r == "A":
            aces += 1

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

blackjack = {}

async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    u = get_user(uid, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            pass

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida")

    u["chips"] -= bet

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    blackjack[uid] = {"deck": d, "player": player, "dealer": dealer, "bet": bet}

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="hit"),
        InlineKeyboardButton("STAND", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\nTU: {player} ({value(player)})\n"
        f"DEALER: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ROULETTE
# =========================

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            pass

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida")

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

    await update.message.reply_text(
        f"🎲 ROULETTE\nNumero: {result}\n"
        f"{'🎉 VINTO +' + str(win) if win else '💀 PERSO'}"
    )

# =========================
# CLASSIFICA
# =========================

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA\n\n"
    for i, (_, u) in enumerate(top_users, 1):
        msg += f"{i}. {u['name']} — {u['chips']}\n"

    await update.message.reply_text(msg)

# =========================
# CALLBACK
# =========================

blackjack = {}

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    data = q.data

    if data == "slot":
        return await q.message.reply_text("Usa /slot 100")
    if data == "blackjack":
        return await q.message.reply_text("Usa /blackjack 100")
    if data == "roulette":
        return await q.message.reply_text("Usa /roulette 100")
    if data == "saldo":
        return await q.message.reply_text(f"{u['chips']}")
    if data == "daily":
        return await daily(update, context)
    if data == "top":
        return await top(update, context)

    if uid not in blackjack:
        return

    game = blackjack[uid]
    d = game["deck"]
    p = game["player"]
    dealer = game["dealer"]
    bet = game["bet"]

    if data == "hit":
        if d:
            p.append(d.pop())

        if value(p) > 21:
            blackjack.pop(uid)
            u["losses"] += 1
            save_all()
            return await q.message.reply_text("💥 BUST")

        return await q.message.reply_text(f"{p} ({value(p)})")

    if data == "stand":
        while value(dealer) < 17 and d:
            dealer.append(d.pop())

        pv = value(p)
        dv = value(dealer)

        if pv > 21 or dv > pv:
            res = "💀 PERSO"
        elif pv == dv:
            res = "⚖️ PAREGGIO"
            u["chips"] += bet
        else:
            win = bet * 2
            u["chips"] += win
            res = f"🎉 VINTO +{win}"

        blackjack.pop(uid)
        save_all()

        return await q.message.reply_text(
            f"TU: {p} ({pv})\nDEALER: {dealer} ({dv})\n{res}"
        )

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("blackjack", blackjack_cmd))
    app.add_handler(CommandHandler("roulette", roulette))
    app.add_handler(CommandHandler("classifica", top))

    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
