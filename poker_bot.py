import os
import random
import sqlite3
import time
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

print("🟢 CASINO PRO V3 ONLINE")

# =========================
# DATABASE
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
    last_daily INTEGER
)
""")
conn.commit()

# =========================
# ARENE
# =========================

arenas = {}

# =========================
# USER SYSTEM
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "last_daily": 0
            }

        return {
            "user_id": row[0],
            "name": row[1],
            "chips": row[2],
            "wins": row[3],
            "losses": row[4],
            "last_daily": row[5]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            wins=?,
            losses=?,
            last_daily=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["last_daily"], u["user_id"]
        ))
        conn.commit()

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],

        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette"),
         InlineKeyboardButton("🎡 Ruota", callback_data="ruota")],

        [InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
         InlineKeyboardButton("👤 Profilo", callback_data="profilo")],

        [InlineKeyboardButton("⚔️ Arena", callback_data="arena"),
         InlineKeyboardButton("💰 Saldo", callback_data="saldo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🎰 CASINO PRO V3\nScegli un gioco:",
        reply_markup=menu()
    )

# =========================
# SLOT
# =========================

async def slot(update, context):
    u = get_user(update.effective_user.id)

    symbols = ["🍒","🍋","🍇","💎","7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 1500
    elif r[0] == r[1] or r[1] == r[2]:
        win = 300

    u["chips"] += win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    update_user(u)

    await update.message.reply_text(
        f"🎰 {r[0]} | {r[1]} | {r[2]}\n💰 +{win}",
        reply_markup=menu()
    )

# =========================
# ROULETTE
# =========================

async def roulette(update, context):
    u = get_user(update.effective_user.id)

    n = random.randint(0, 36)

    win = 0
    if n == 0:
        win = 2000
    elif n % 2 == 0:
        win = 300

    u["chips"] += win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1
        
    update_user(u)

    await update.message.reply_text(
        f"🎲 Numero: {n}\n💰 +{win}",
        reply_markup=menu()
    )

# =========================
# RUOTA BONUS
# =========================

async def ruota(update, context):
    u = get_user(update.effective_user.id)

    prizes = [0, 100, 200, 500, 1000, 2000]
    win = random.choice(prizes)

    u["chips"] += win

    if win > 0:
        u["wins"] += 1

    update_user(u)

    await update.message.reply_text(
        f"🎡 Ruota: +{win}",
        reply_markup=menu()
    )

# =========================
# BONUS GIORNALIERO
# =========================

async def bonus(update, context):
    u = get_user(update.effective_user.id)

    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Bonus già preso oggi", reply_markup=menu())

    reward = random.randint(500, 2000)

    u["chips"] += reward
    u["last_daily"] = now

    update_user(u)

    await update.message.reply_text(
        f"🎁 Bonus +{reward}",
        reply_markup=menu()
    )

# =========================
# SALDO + CLASSIFICA
# =========================

async def saldo(update, context):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 {u['chips']}", reply_markup=menu())

async def classifica(update, context):
    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 TOP 10\n\n"
    for i, (n, c) in enumerate(top, 1):
        msg += f"{i}. {n} - {c}\n"

    await update.message.reply_text(msg, reply_markup=menu())

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "slot":
        return await slot(update, context)

    if q.data == "roulette":
        return await roulette(update, context)

    if q.data == "ruota":
        return await ruota(update, context)

    if q.data == "bonus":
        return await bonus(update, context)

    if q.data == "saldo":
        return await saldo(update, context)

    if q.data == "classifica":
        return await classifica(update, context)

    

    if q.data == "profilo":

        uid = str(q.from_user.id)

        u = get_user(uid, q.from_user.first_name)

        partite = u["wins"] + u["losses"]

        livello = max(1, partite // 10 + 1)

        if livello < 5:
            grado = "🥉 Bronzo"
        elif livello < 10:
            grado = "🥈 Argento"
        elif livello < 20:
            grado = "🥇 Oro"
        else:
            grado = "💎 Diamante"

        await q.message.reply_text(
            f"👤 PROFILO GIOCATORE\n\n"
            f"🧑 Nome: {u['name']}\n"
            f"💰 Chips: {u['chips']}\n"
            f"🏆 Vittorie: {u['wins']}\n"
            f"💀 Sconfitte: {u['losses']}\n"
            f"🎮 Partite giocate: {partite}\n"
            f"⭐ Livello: {livello}\n"
            f"🎖️ Grado: {grado}",
            reply_markup=menu()
        )
        return

    if q.data == "blackjack":
        await q.message.reply_text("🃏 Blackjack in arrivo upgrade")

    if q.data == "arena":
        await q.message.reply_text("⚔️ Arena in upgrade successivo")

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
