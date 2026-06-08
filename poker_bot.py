import os
import random
import sqlite3
import time
import threading

lock = threading.Lock()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

print("🟢 CASINO PRO BOT ONLINE")

conn = sqlite3.connect("casino.db", check_same_thread=False)
cursor = conn.cursor()

lock = threading.Lock()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    chips INTEGER,
    wins INTEGER,
    losses INTEGER,
    best_win INTEGER,
    last_daily INTEGER
)
""")
conn.commit()

# =========================
# GET USER
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "best_win": 0,
                "last_daily": 0
            }

        return {
            "user_id": row[0],
            "name": row[1],
            "chips": row[2],
            "wins": row[3],
            "losses": row[4],
            "best_win": row[5],
            "last_daily": row[6]
        }

# =========================
# UPDATE USER
# =========================

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            wins=?,
            losses=?,
            best_win=?,
            last_daily=?
        WHERE user_id=?
        """, (
            u["name"],
            u["chips"],
            u["wins"],
            u["losses"],
            u["best_win"],
            u["last_daily"],
            u["user_id"]
        ))
        conn.commit()
# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 Slot", callback_data="slot")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ]

    await update.message.reply_text(
        "🎰 CASINO PRO V2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# SALDO
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Chips: {u['chips']}")

# =========================
# SLOT MIGLIORATA
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = int(context.args[0]) if context.args else 100

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida")

    u["chips"] -= bet

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = bet * 15
    elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
        win = bet * 3

    u["chips"] += win
    u["wins"] += int(win > 0)
    u["losses"] += int(win == 0)

    update_user(u)

    await update.message.reply_text(
        f"{r[0]} | {r[1]} | {r[2]}\n"
        f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
        f"💰 {u['chips']}"
    )

# =========================
# BLACKJACK SEMPLIFICATO MA STABILE
# =========================

games = {}

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

# =========================
# BLACKJACK START
# =========================

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    u = get_user(uid)

    bet = int(context.args[0]) if context.args else 100

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida")

    u["chips"] -= bet

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    games[uid] = {"d": d, "p": player, "dl": dealer, "bet": bet}

    keyboard = [[
        InlineKeyboardButton("HIT", callback_data="hit"),
        InlineKeyboardButton("STAND", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"TU: {player} ({value(player)})\nMAZZIERE: [{dealer[0]}, ?]",
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

    if q.data == "saldo":
        return await q.message.reply_text(f"{u['chips']}")

    if uid not in games:
        return

    g = games[uid]

    if q.data == "hit":
        g["p"].append(g["d"].pop())

        if value(g["p"]) > 21:
            games.pop(uid)
            u["losses"] += 1
            update_user(u)
            return await q.message.reply_text("💀 Sballato")

        return await q.message.reply_text(f"{g['p']}")

    if q.data == "stand":
        while value(g["dl"]) < 17:
            g["dl"].append(g["d"].pop())

        pv = value(g["p"])
        dv = value(g["dl"])

        if pv > dv:
            u["chips"] += g["bet"] * 2
            msg = "🎉 VINTO"
        elif pv == dv:
            u["chips"] += g["bet"]
            msg = "⚖️ PAREGGIO"
        else:
            msg = "💀 PERSO"

        update_user(u)
        games.pop(uid)

        return await q.message.reply_text(msg)

# =========================
# CLASSIFICA
# =========================

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 TOP 10\n\n"
    for i, (name, chips) in enumerate(top, 1):
        msg += f"{i}. {name} - {chips}\n"

    await update.message.reply_text(msg)

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(CommandHandler("classifica", classifica))

    print("🟢 BOT PRO ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

