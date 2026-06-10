import logging 
logging.basicConfig(level=logging.INFO)

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

print("🟢 CASINO ULTRA PRO 7 ONLINE")

GRUPPI_AUTORIZZATI = [-1003664350829, -1002229066951]

def autorizzato(chat_id):
    return chat_id in GRUPPI_AUTORIZZATI


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
    xp INTEGER,
    streak INTEGER,
    last_daily INTEGER
)
""")
conn.commit()


# =========================
# UTILS
# =========================

def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])


def calc(mano):
    totale = sum(mano)
    assi = mano.count(11)

    while totale > 21 and assi:
        totale -= 10
        assi -= 1

    return totale


def get_rank(xp):
    if xp >= 5000: return "👑 LEGGENDARIO"
    if xp >= 2500: return "💎 PROFESSIONISTA"
    if xp >= 1000: return "⭐ ESPERTO"
    if xp >= 300: return "🎲 GIOCATORE"
    return "🪙 PRINCIPIANTE"
# =========================
# UTENTE
# =========================

def get_user(uid, name="Giocatore"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if not r:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "xp": 0,
                "streak": 0,
                "last_daily": 0
            }

        return {
            "user_id": r[0],
            "name": name,
            "chips": r[2],
            "wins": r[3],
            "losses": r[4],
            "xp": r[5],
            "streak": r[6],
            "last_daily": r[7]
        }


def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, wins=?, losses=?, xp=?, streak=?, last_daily=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["xp"], u["streak"], u["last_daily"],
            u["user_id"]
        ))
        conn.commit()


# =========================
# MENU ITALIANO
# =========================

def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎰 Slot", callback_data="slot"),
            InlineKeyboardButton("🎲 Roulette", callback_data="roulette")
        ],
        [
            InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
            InlineKeyboardButton("🎡 Ruota Fortuna", callback_data="ruota")
        ],
        [
            InlineKeyboardButton("🎁 Bonus Giornaliero", callback_data="bonus"),
            InlineKeyboardButton("👤 Profilo", callback_data="profilo")
        ],
        [
            InlineKeyboardButton("💰 Saldo", callback_data="saldo"),
            InlineKeyboardButton("🏆 Classifica", callback_data="classifica")
        ]
    ])


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not autorizzato(chat_id):
        await update.message.reply_text("❌ Gruppo non autorizzato")
        return

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO ULTRA PRO 7\n🎮 Benvenuto nel casinò!",
        reply_markup=menu()
    )


# =========================
# SLOT MACHINE
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    simboli = ["🍒", "🍋", "🔔", "💎", "7️⃣"]
    r = [random.choice(simboli) for _ in range(3)]

    if r[0] == r[1] == r[2]:
        win = 2000
    elif r[0] == r[1] or r[1] == r[2]:
        win = 500
    else:
        win = 0

    u["chips"] += win
    u["wins"] += 1 if win > 0 else 0
    u["losses"] += 0 if win > 0 else 1

    update_user(u)

    await q.edit_message_text(
        f"🎰 SLOT\n\n{' | '.join(r)}\n💰 Vincita: {win}",
        reply_markup=menu()
    )


# =========================
# ROULETTE
# =========================

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    num = random.randint(0, 36)
    win = 1000 if num == 0 else 300 if num % 2 == 0 else 0

    u["chips"] += win
    u["wins"] += 1 if win > 0 else 0
    u["losses"] += 0 if win > 0 else 1

    update_user(u)

    await q.edit_message_text(
        f"🎲 Roulette\nNumero: {num}\n💰 Vincita: {win}",
        reply_markup=menu()
    )

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)
    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await q.edit_message_text("⏳ Bonus già preso oggi")

    if now - u["last_daily"] < 172800:
        u["streak"] += 1
    else:
        u["streak"] = 1

    reward = random.randint(500, 2000) + u["streak"] * 100

    u["chips"] += reward
    u["last_daily"] = now
    u["xp"] += 50

    update_user(u)

    await q.edit_message_text(f"🎁 Bonus ricevuto: +{reward}", reply_markup=menu())


async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)
    await q.edit_message_text(f"💰 Saldo: {u['chips']} chips", reply_markup=menu())


async def profilo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    tot = u["wins"] + u["losses"]
    wr = round(u["wins"] / tot * 100, 2) if tot else 0

    rank = get_rank(u["xp"])

    await q.edit_message_text(f"""
👤 {u['name']}
💰 Chips: {u['chips']}
🏆 Rank: {rank}
📊 Winrate: {wr}%
⭐ XP: {u['xp']}
🔥 Streak: {u['streak']}
""", reply_markup=menu())


async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    text = "🏆 CLASSIFICA TOP\n\n"
    for i, (n, c) in enumerate(top, 1):
        text += f"{i}. {n} → {c}\n"

    await q.edit_message_text(text, reply_markup=menu())


# =========================
# CALLBACK ROUTER
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat.id

    if not autorizzato(chat_id):
        await q.answer("❌ Non autorizzato", show_alert=True)
        return

    await q.answer()
    d = q.data

    if d == "slot":
        return await slot(update, context)

    if d == "roulette":
        return await roulette(update, context)

    if d == "bonus":
        return await bonus(update, context)

    if d == "saldo":
        return await saldo(update, context)

    if d == "profilo":
        return await profilo(update, context)

    if d == "classifica":
        return await classifica(update, context)

    await q.edit_message_text("🚧 In sviluppo", reply_markup=menu())


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
