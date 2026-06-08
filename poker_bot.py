import os
import json
import random
import time


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

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante")

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
# START MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 Slot", callback_data="slot")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
        [InlineKeyboardButton("🎁 Bonus", callback_data="bonus")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ]

    await update.message.reply_text(
        "🎰 CASINO BOT PRO",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# SALDO
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Saldo: {u['chips']} chips")

# =========================
# BONUS
# =========================

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    now = int(time.time())
    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Bonus già preso oggi")

    reward = random.randint(500, 2500)
    u["chips"] += reward
    u["last_daily"] = now
    save_all()

    await update.message.reply_text(f"🎁 +{reward} chips")

# =========================
# SLOT
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    try:
        bet = int(context.args[0]) if context.args else 100
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
    elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
        win = bet * 3

    u["chips"] += win
    save_all()

    await update.message.reply_text(
        f"🎰 {r[0]} | {r[1]} | {r[2]}\n"
        f"{'🎉 Vinci ' + str(win) if win else '💀 Perso'}\n"
        f"💰 {u['chips']}"
    )

# =========================
# BLACKJACK
# =========================

blackjack = {}

def deck():
    d = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] * 4
    random.shuffle(d)
    return d

def value(hand):
    v, aces = 0, 0

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
        f"🃏 TU: {player} ({value(player)})\nMAZZIERE: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    data = q.data

    if data == "saldo":
        return await q.message.reply_text(f"💰 {u['chips']}")

    if data == "slot":
        return await q.message.reply_text("Usa /slot 100")

    if data == "blackjack":
        return await q.message.reply_text("Usa /blackjack 100")

    if data == "roulette":
        return await q.message.reply_text("Usa /roulette 100")

    if data == "bonus":
        return await bonus(update, context)

    if data == "classifica":
        top = sorted(users.values(), key=lambda x: x["chips"], reverse=True)[:10]
        msg = "🏆 TOP 10\n\n"
        for i, x in enumerate(top, 1):
            msg += f"{i}. {x['name']} - {x['chips']}\n"
        return await q.message.reply_text(msg)

    if uid not in blackjack:
        return

    g = blackjack[uid]

    if data == "hit":
        g["player"].append(g["deck"].pop())

        if value(g["player"]) > 21:
            blackjack.pop(uid)
            return await q.message.reply_text("💀 Sballato!")

        return await q.message.reply_text(f"TU: {g['player']}")

    if data == "stand":
        while value(g["dealer"]) < 17:
            g["dealer"].append(g["deck"].pop())

        pv = value(g["player"])
        dv = value(g["dealer"])

        if pv > dv:
            u["chips"] += g["bet"] * 2
            msg = "🎉 VINTO"
        elif pv == dv:
            u["chips"] += g["bet"]
            msg = "⚖️ PAREGGIO"
        else:
            msg = "💀 PERSO"

        blackjack.pop(uid)
        save_all()

        return await q.message.reply_text(msg)

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
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()


