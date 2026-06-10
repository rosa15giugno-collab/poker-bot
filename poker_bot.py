# =========================
# MODULO 1 - CORE
# =========================

import logging
logging.basicConfig(level=logging.INFO)

import os
import random
import sqlite3
import time
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

print("🟢 CASINO ULTRA PRO 7 ONLINE")

GRUPPI_AUTORIZZATI = [-1003664350829, -1002229066951]

def is_allowed(chat_id):
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
    last_bonus INTEGER,
    xp INTEGER,
    streak INTEGER,
    last_daily INTEGER
)
""")
conn.commit()


# =========================
# USER SYSTEM
# =========================

def get_user(uid, name="Giocatore"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if not r:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "last_bonus": 0,
                "xp": 0,
                "streak": 0,
                "last_daily": 0
            }

        cursor.execute("UPDATE users SET name=? WHERE user_id=?", (name, uid))
        conn.commit()

        return {
            "user_id": r[0],
            "name": name,
            "chips": r[2],
            "wins": r[3],
            "losses": r[4],
            "last_bonus": r[5],
            "xp": r[6],
            "streak": r[7],
            "last_daily": r[8]
        }


def save_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, wins=?, losses=?, last_bonus=?, xp=?, streak=?, last_daily=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["last_bonus"], u["xp"], u["streak"], u["last_daily"],
            u["user_id"]
        ))
        conn.commit()


def rank(xp):
    if xp >= 5000: return "👑 LEGGENDA"
    if xp >= 2500: return "💎 PRO"
    if xp >= 1000: return "⭐ ESPERTO"
    if xp >= 300: return "🎲 GIOCATORE"
    return "🪙 PRINCIPIANTE"
# =========================
# MODULO 2 - UI + GIOCHI BASE
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("🎡 Ruota", callback_data="ruota")],

        [InlineKeyboardButton("🎁 Bonus Giornaliero", callback_data="bonus")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("💰 Saldo", callback_data="saldo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not is_allowed(chat_id):
        await update.message.reply_text("❌ Gruppo non autorizzato")
        return

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO ULTRA ATTIVO\n🎮 Benvenuto!",
        reply_markup=menu()
    )


# =========================
# ROULETTE
# =========================

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    n = random.randint(0, 36)
    win = 1000 if n == 0 else 300 if n % 2 == 0 else 0

    u["chips"] += win
    u["wins"] += win > 0
    u["losses"] += win == 0

    save_user(u)

    await q.edit_message_text(f"🎲 Numero: {n}\n💰 Vincita: {win}", reply_markup=menu())


# =========================
# RUOTA
# =========================

async def ruota(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    rewards = [(0,"💀"),(100,"🥉"),(250,"🥈"),(500,"🥇"),(1000,"💎")]
    premio, icon = random.choice(rewards)

    u["chips"] += premio
    u["wins"] += premio > 0
    u["losses"] += premio == 0

    save_user(u)

    await q.edit_message_text(f"{icon} +{premio} chips", reply_markup=menu())


# =========================
# BONUS
# =========================

async def bonus(update, context):
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

    save_user(u)

    await q.edit_message_text(f"🎁 Bonus: +{reward}", reply_markup=menu())


# =========================
# MODULO 3 - PROFILO + CALLBACK
# =========================

async def saldo(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    await q.edit_message_text(f"💰 Chips: {u['chips']}", reply_markup=menu())


async def profilo(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    tot = u["wins"] + u["losses"]
    wr = round(u["wins"] / tot * 100, 2) if tot else 0

    await q.edit_message_text(f"""
👤 {u['name']}
💰 {u['chips']}
🏆 {rank(u['xp'])}
📊 Winrate: {wr}%
⭐ XP: {u['xp']}
🔥 Streak: {u['streak']}
""", reply_markup=menu())


async def classifica(update, context):
    q = update.callback_query
    await q.answer()

    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    txt = "🏆 CLASSIFICA\n\n"
    for i,(n,c) in enumerate(top,1):
        txt += f"{i}. {n} - {c}\n"

    await q.edit_message_text(txt, reply_markup=menu())


# =========================
# CALLBACK ROUTER
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat.id

    if not is_allowed(chat_id):
        await q.answer("❌ Non autorizzato", show_alert=True)
        return

    await q.answer()
    d = q.data

    if d == "roulette": return await roulette(update, context)
    if d == "ruota": return await ruota(update, context)
    if d == "bonus": return await bonus(update, context)
    if d == "saldo": return await saldo(update, context)
    if d == "profilo": return await profilo(update, context)
    if d == "classifica": return await classifica(update, context)

    if d in ["slot", "blackjack"]:
        return await q.edit_message_text("🚧 Modalità in sviluppo", reply_markup=menu())


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE ULTRA")
    app.run_polling()


if __name__ == "__main__":
    main()
