import os
import json
import random
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

DATA_FILE = "casino_db.json"

print("🟢 CASINO PRO ULTIMATE ONLINE PID:", os.getpid())

# =========================
# SAFE DB
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
# USER SYSTEM
# =========================

def get_user(uid, name="Player"):
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
# MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 SLOT", callback_data="slot")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="bj")],
        [InlineKeyboardButton("🎲 ROULETTE", callback_data="roulette")],
        [InlineKeyboardButton("💰 SALDO", callback_data="saldo")],
        [InlineKeyboardButton("🎁 DAILY", callback_data="daily")],
        [InlineKeyboardButton("🏆 CLASSIFICA", callback_data="top")]
    ]

    await update.message.reply_text(
        "🎰 CASINO PRO ULTIMATE\nScegli:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# BALANCE
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
        return await update.message.reply_text("⏳ Daily già preso")

    reward = random.randint(500, 2500)
    u["chips"] += reward
    u["last_daily"] = now

    save_all()
    await update.message.reply_text(f"🎁 +{reward} chips")

# =========================
# SLOT MACHINE
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
    elif len(set(r)) == 2:
        win = bet * 3

    u["chips"] += win

    if win > u["best_win"]:
        u["best_win"] = win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    save_all()

    await update.message.reply_text(
        f"{r[0]} | {r[1]} | {r[2]}\n"
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
        r = "10" if c.startswith("10") else c[0]
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

    blackjack[uid] = {
        "deck": d,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="hit"),
        InlineKeyboardButton("STAND", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\nTU: {player} ({value(player)})\nDealer: [{dealer[0]}, ?]",
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

    await update.message.reply_text(f"🎲 Roulette: {result}\n{'WIN +' + str(win) if win else 'LOSE'}")

# =========================
# CLASSIFICA
# =========================

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 TOP CASINO\n\n"

    for i, (_, u) in enumerate(top_users, 1):
        msg += f"{i}. {u['name']} — {u['chips']} 💰\n"

    await update.message.reply_text(msg)

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    data = q.data

    # MENU
    if data == "slot":
        return await q.message.reply_text("🎰 Usa /slot 100")

    if data == "bj":
        return await q.message.reply_text("🃏 Usa /blackjack 100")

    if data == "roulette":
        return await q.message.reply_text("🎲 Usa /roulette 100")

    if data == "saldo":
        return await q.message.reply_text(f"💰 {u['chips']}")

    if data == "daily":
        return await daily(update, context)

    if data == "top":
        return await top(update, context)

    # BLACKJACK LOGIC
    if uid not in blackjack:
        return

    game = blackjack[uid]
    d = game["deck"]
    p = game["player"]
    dealer = game["dealer"]
    bet = game["bet"]

    if data == "hit":
        p.append(d.pop())

        if value(p) > 21:
            blackjack.pop(uid)
            u["losses"] += 1
            save_all()
            return await q.message.reply_text("💥 BUST")

        return await q.message.reply_text(f"{p} ({value(p)})")

    if data == "stand":
        while value(dealer) < 17:
            dealer.append(d.pop())

        pv = value(p)
        dv = value(dealer)

        if pv > 21 or dv > pv:
            res = "💀 PERSO"
            u["losses"] += 1
        elif pv == dv:
            res = "⚖️ PAREGGIO"
            u["chips"] += bet
        else:
            win = bet * 2
            u["chips"] += win
            u["wins"] += 1
            res = f"🎉 VINTO +{win}"

        blackjack.pop(uid)
        save_all()

        return await q.message.reply_text(
            f"TU: {p} ({pv})\n"
            f"DEALER: {dealer} ({dv})\n"
            f"{res}"
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

    print("🟢 CASINO PRO ULTIMATE READY")

    app.run_polling()

if __name__ == "__main__":
    main()
