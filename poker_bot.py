import os
import json
import random
import time
import tempfile

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

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante")

DATA_FILE = "casino.json"

print("🟢 CASINO BOT ONLINE PID =", os.getpid())

# =========================
# SAFE DB
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
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f)
    os.replace(tmp, DATA_FILE)

db = load()
users = db["users"]
games = db["games"]

def save_all():
    db["users"] = users
    db["games"] = games
    save(db)

# =========================
# USER
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    if uid not in users:
        users[uid] = {
            "chips": 5000,
            "name": name,
            "last_daily": 0,
            "wins": 0,
            "losses": 0,
            "best_win": 0
        }
        save_all()

    return users[uid]

# =========================
# CARDS
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
# GAME STATE
# =========================

def table(cid):
    cid = str(cid)

    if cid not in games:
        games[cid] = {"blackjack": {}}

    if "blackjack" not in games[cid]:
        games[cid]["blackjack"] = {}

    return games[cid]

# =========================
# MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 SLOT", callback_data="menu_slot")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_bj")],
        [InlineKeyboardButton("💰 SALDO", callback_data="menu_saldo")],
        [InlineKeyboardButton("🎁 DAILY", callback_data="menu_daily")],
        [InlineKeyboardButton("🏆 CLASSIFICA", callback_data="menu_top")]
    ]

    await update.message.reply_text(
        "🎰 CASINO PRO ULTIMATE\nScegli un gioco:",
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
        return await update.message.reply_text("⏳ Hai già preso il daily")

    reward = random.randint(500, 2000)
    u["chips"] += reward
    u["last_daily"] = now

    save_all()
    await update.message.reply_text(f"🎁 Daily +{reward}")

# =========================
# SLOT (BET)
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            bet = 100

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
# BLACKJACK (BET)
# =========================

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    t = table(cid)

    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            bet = 100

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida")

    u["chips"] -= bet

    d = deck()

    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    t["blackjack"][str(update.effective_user.id)] = {
        "deck": d,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    save_all()

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="bj_hit"),
        InlineKeyboardButton("STAND", callback_data="bj_stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\n"
        f"TU: {player} ({hand_value(player)})\n"
        f"Dealer: [{dealer[0]}, ?]\n"
        f"💰 Bet: {bet}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CLASSIFICA
# =========================

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 TOP PLAYERS\n\n"

    for i, (_, u) in enumerate(top, 1):
        msg += f"{i}. {u['name']} — {u['chips']} 💰\n"

    await update.message.reply_text(msg)

# =========================
# CALLBACK MENU + BJ
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    cid = str(q.message.chat.id)

    t = table(cid)

    # MENU
    if q.data == "menu_slot":
        return await q.message.reply_text("🎰 Usa: /slot 100")

    if q.data == "menu_bj":
        return await q.message.reply_text("🃏 Usa: /blackjack 100")

    if q.data == "menu_saldo":
        u = get_user(uid)
        return await q.message.reply_text(f"💰 {u['chips']}")

    if q.data == "menu_daily":
        return await daily(update, context)

    if q.data == "menu_top":
        return await classifica(update, context)

    # BLACKJACK LOGIC
    bj = t["blackjack"].get(uid)

    if not bj:
        return

    d = bj["deck"]
    p = bj["player"]
    dealer = bj["dealer"]
    bet = bj["bet"]

    u = get_user(uid)

    if q.data == "bj_hit":
        p.append(d.pop())

        if hand_value(p) > 21:
            t["blackjack"].pop(uid)
            u["losses"] += 1
            save_all()
            return await q.message.reply_text("💥 BUST! Hai perso")

        save_all()
        return await q.message.reply_text(f"{p} ({hand_value(p)})")

    if q.data == "bj_stand":
        while hand_value(dealer) < 17:
            dealer.append(d.pop())

        pv = hand_value(p)
        dv = hand_value(dealer)

        if pv > 21 or dv > pv:
            result = "💀 PERSO"
            u["losses"] += 1
        elif pv == dv:
            result = "⚖️ PAREGGIO"
            u["chips"] += bet
        else:
            win = bet * 2
            u["chips"] += win
            u["wins"] += 1
            result = f"🎉 VINTO +{win}"

        t["blackjack"].pop(uid)
        save_all()

        return await q.message.reply_text(
            f"TU: {p} ({pv})\n"
            f"DEALER: {dealer} ({dv})\n"
            f"{result}"
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
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("classifica", classifica))

    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO ULTIMATE ONLINE")

    app.run_polling()

if _name_ == "_main_":
    main()
