import os
import random
import sqlite3
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

print("🟢 CASINO CASINO PRO ONLINE")

# =========================
# DATABASE SQLITE
# =========================

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
# UTENTE
# =========================

def get_user(uid, name="Giocatore"):
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
# START MENU
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 SLOT MACHINE", callback_data="menu_slot")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")],
        [InlineKeyboardButton("🎲 ROULETTE", callback_data="menu_roulette")],
        [InlineKeyboardButton("💰 SALDO", callback_data="saldo")],
        [InlineKeyboardButton("🏆 CLASSIFICA", callback_data="classifica")]
    ]

    await update.message.reply_text(
        f"🎰 CASINO ROYALE\n💰 Chips: {u['chips']}\n\nScegli un gioco:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# SALDO
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Hai {u['chips']} chips")

# =========================
# SLOT MENU
# =========================

async def menu_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    keyboard = [
        [InlineKeyboardButton("🎲 GIOCA 100", callback_data="slot_100")],
        [InlineKeyboardButton("🎲 GIOCA 500", callback_data="slot_500")],
        [InlineKeyboardButton("🎲 GIOCA 1000", callback_data="slot_1000")]
    ]

    await q.message.reply_text(
        "🎰 SLOT MACHINE\nScegli la puntata:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# SLOT GAME
# =========================

async def slot_play(update: Update, context: ContextTypes.DEFAULT_TYPE, bet: int):
    q = update.callback_query
    uid = str(q.from_user.id)
    u = get_user(uid)

    if u["chips"] < bet:
        return await q.message.reply_text("❌ Non hai abbastanza chips")

    u["chips"] -= bet

    simboli = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
    r = [random.choice(simboli) for _ in range(3)]

    vincita = 0
    if r[0] == r[1] == r[2]:
        vincita = bet * 15
    elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
        vincita = bet * 3

    u["chips"] += vincita
    update_user(u)

    await q.message.reply_text(
        f"🎰 RISULTATO SLOT\n\n"
        f"{r[0]} | {r[1]} | {r[2]}\n\n"
        f"{'🎉 HAI VINTO +' + str(vincita) if vincita else '💀 HAI PERSO'}\n"
        f"💰 Saldo: {u['chips']}"
    )

# =========================
# BLACKJACK (SEMPLICE)
# =========================

games = {}

def deck():
    d = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] * 4
    random.shuffle(d)
    return d

def value(hand):
    v = 0
    aces = 0

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

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    u = get_user(uid)

    bet = 100

    if u["chips"] < bet:
        return await update.message.reply_text("❌ Non hai chips")

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
        f"🃏 BLACKJACK\n\nTU: {player} ({value(player)})\nMAZZIERE: [{dealer[0]}, ?]",
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

    if data == "menu_slot":
        return await menu_slot(update, context)

    if data == "saldo":
        return await q.message.reply_text(f"💰 {u['chips']}")

    if data == "classifica":
        cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
        top = cursor.fetchall()

        msg = "🏆 CLASSIFICA TOP 10\n\n"
        for i, (name, chips) in enumerate(top, 1):
            msg += f"{i}. {name} - {chips}\n"

        return await q.message.reply_text(msg)

    if data == "slot_100":
        return await slot_play(update, context, 100)

    if data == "slot_500":
        return await slot_play(update, context, 500)

    if data == "slot_1000":
        return await slot_play(update, context, 1000)

    if uid not in games:
        return

    g = games[uid]

    if data == "hit":
        g["p"].append(g["d"].pop())

        if value(g["p"]) > 21:
            games.pop(uid)
            u["losses"] += 1
            update_user(u)
            return await q.message.reply_text("💀 Sballato")

        return await q.message.reply_text(f"{g['p']} ({value(g['p'])})")

    if data == "stand":
        while value(g["dl"]) < 17:
            g["dl"].append(g["d"].pop())

        pv = value(g["p"])
        dv = value(g["dl"])

        if pv > dv:
            u["chips"] += g["bet"] * 2
            msg = "🎉 HAI VINTO"
        elif pv == dv:
            u["chips"] += g["bet"]
            msg = "⚖️ PAREGGIO"
        else:
            msg = "💀 HAI PERSO"

        update_user(u)
        games.pop(uid)

        return await q.message.reply_text(msg)

# =========================
# CLASSIFICA
# =========================

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 CLASSIFICA TOP 10\n\n"
    for i, (name, chips) in enumerate(top, 1):
        msg += f"{i}. {name} - {chips}\n"

    await update.message.reply_text(msg)

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("slot", slot_play))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()

