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

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante")

print("🟢 CASINO PRO FINAL ONLINE")

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
# USERS SYSTEM
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
# CARDS ENGINE
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
# GAME STORAGE
# =========================

def table(cid):
    cid = str(cid)

    if cid not in games:
        games[cid] = {
            "blackjack": None,
            "texas": None
        }

    if games[cid]["blackjack"] is None:
        games[cid]["blackjack"] = {}

    if games[cid]["texas"] is None:
        games[cid]["texas"] = {
            "players": {},
            "deck": [],
            "board": [],
            "started": False,
            "pot": 0,
            "stage": "WAITING",
            "turn": []
        }

    return games[cid]

# =========================
# BASIC COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🎰 CASINO PRO FINAL\n\n"
        "/saldo\n"
        "/daily\n"
        "/slot\n"
        "/blackjack\n"
        "/texas_join\n"
        "/texas_start\n"
        "/texas_board\n"
        "/classifica"
    )

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(f"💰 Chips: {u['chips']}")

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA\n\n"
    for i, (_, u) in enumerate(top, 1):
        msg += f"{i}. {u['name']} — {u['chips']}\n"

    await update.message.reply_text(msg)

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Daily già preso")

    reward = random.randint(500, 1500)
    u["chips"] += reward
    u["last_daily"] = now

    save_all()

    await update.message.reply_text(f"🎁 +{reward} chips")

# =========================
# SLOT MACHINE
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    if u["chips"] < 100:
        return await update.message.reply_text("❌ Non hai chips")

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

    await update.message.reply_text(f"{r[0]} | {r[1]} | {r[2]}\n{'WIN +' + str(win) if win else 'LOSE'}")

# =========================
# BLACKJACK
# =========================

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    t = table(cid)

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    t["blackjack"] = {
        "deck": d,
        "player": player,
        "dealer": dealer
    }

    save_all()

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="bj_hit"),
        InlineKeyboardButton("STAND", callback_data="bj_stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\nTU: {player} ({hand_value(player)})\nDealer: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# TEXAS POKER
# =========================

async def texas_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    t = table(cid)

    if t["texas"]["started"]:
        return await update.message.reply_text("❌ Partita già iniziata")

    uid = str(update.effective_user.id)

    t["texas"]["players"][uid] = {
        "name": update.effective_user.first_name,
        "hand": [],
        "folded": False
    }

    save_all()

    await update.message.reply_text(f"🟢 {update.effective_user.first_name} joined Texas")

async def texas_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    t = table(cid)

    if len(t["texas"]["players"]) < 2:
        return await update.message.reply_text("❌ Min 2 player")

    t["texas"]["deck"] = deck()
    t["texas"]["board"] = []
    t["texas"]["started"] = True

    for p in t["texas"]["players"].values():
        p["hand"] = [t["texas"]["deck"].pop(), t["texas"]["deck"].pop()]

    save_all()

    await update.message.reply_text("🃏 TEXAS STARTED")

async def texas_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    t = table(cid)

    if not t["texas"]["started"]:
        return await update.message.reply_text("❌ Nessuna partita")

    if len(t["texas"]["board"]) == 0:
        t["texas"]["board"] = [t["texas"]["deck"].pop() for _ in range(3)]
        stage = "FLOP"
    elif len(t["texas"]["board"]) == 3:
        t["texas"]["board"].append(t["texas"]["deck"].pop())
        stage = "TURN"
    elif len(t["texas"]["board"]) == 4:
        t["texas"]["board"].append(t["texas"]["deck"].pop())
        stage = "RIVER"
    else:
        stage = "END"

    save_all()

    await update.message.reply_text(f"🃏 {stage}\n{t['texas']['board']}")

# =========================
# CALLBACK BLACKJACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = str(q.message.chat.id)
    t = table(cid)

    bj = t["blackjack"]

    if not bj:
        return

    d = bj["deck"]
    p = bj["player"]
    dealer = bj["dealer"]

    if q.data == "bj_hit":
        p.append(d.pop())

        if hand_value(p) > 21:
            t["blackjack"] = {}
            save_all()
            return await q.message.reply_text("💥 Sballato")

        save_all()
        return await q.message.reply_text(f"{p} ({hand_value(p)})")

    if q.data == "bj_stand":
        while hand_value(dealer) < 17:
            dealer.append(d.pop())

        pv = hand_value(p)
        dv = hand_value(dealer)

        if pv > 21 or dv > pv:
            res = "PERDI"
        elif pv == dv:
            res = "PAREGGIO"
        else:
            res = "VINCI"

        t["blackjack"] = {}
        save_all()

        return await q.message.reply_text(f"TU:{p}\nDEALER:{dealer}\n{res}")

# =========================
# MAIN
# =========================
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

def main():
    app = ApplicationBuilder()\
        .token(TOKEN)\
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("texas_join", texas_join))
    app.add_handler(CommandHandler("texas_start", texas_start))
    app.add_handler(CommandHandler("texas_board", texas_board))
    app.add_handler(CommandHandler("classifica", classifica))

    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO FINAL ONLINE")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
