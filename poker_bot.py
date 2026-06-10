import os
import random
import sqlite3
import time
import threading
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

GRUPPI = [-1003664350829, -1002229066951]

def allowed(chat_id):
    return chat_id in GRUPPI


# =========================
# DATABASE
# =========================

conn = sqlite3.connect("casino.db", check_same_thread=False)
cur = conn.cursor()
lock = threading.Lock()

cur.execute("""
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
# UTENTI
# =========================

def user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cur.fetchone()

        if not r:
            cur.execute("""
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

        cur.execute("UPDATE users SET name=? WHERE user_id=?", (name, uid))
        conn.commit()

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


def save(u):
    with lock:
        cur.execute("""
        UPDATE users SET name=?, chips=?, wins=?, losses=?, xp=?, streak=?, last_daily=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["xp"], u["streak"], u["last_daily"], u["user_id"]
        ))
        conn.commit()


def rank(xp):
    return "👑 LEGGENDA" if xp>=5000 else \
           "💎 PRO" if xp>=2500 else \
           "⭐ ESPERTO" if xp>=1000 else \
           "🎲 PLAYER" if xp>=300 else "🪙 NEW"


# =========================
# MENU ULTRA ITALIANO
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("⚔️ PvP Blackjack", callback_data="pvp")],

        [InlineKeyboardButton("🎡 Ruota VIP", callback_data="ruota"),
         InlineKeyboardButton("🎁 Bonus", callback_data="bonus")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("💰 Saldo", callback_data="saldo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])


# =========================
# CARTE
# =========================

def card():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

def score(hand):
    s = sum(hand)
    aces = hand.count(11)
    while s > 21 and aces:
        s -= 10
        aces -= 1
    return s


import random
import time

# =========================
# SLOT ULTRA
# =========================

async def slot(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    s = ["🍒","🍋","🔔","💎","7️⃣"]
    r = [random.choice(s) for _ in range(3)]

    win = 2000 if r[0]==r[1]==r[2] else 0

    u["chips"] += win
    u["wins"] += 1 if win else 0
    u["losses"] += 0 if win else 1

    save(u)

    await q.edit_message_text(f"🎰 SLOT\n\n{' | '.join(r)}\n💰 {win}", reply_markup=menu())


# =========================
# ROULETTE
# =========================

async def roulette(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    n = random.randint(0,36)
    win = 1200 if n==0 else 400 if n%2==0 else 0

    u["chips"] += win
    u["wins"] += 1 if win else 0
    u["losses"] += 0 if win else 1

    save(u)

    await q.edit_message_text(f"🎲 {n} → {win}", reply_markup=menu())


# =========================
# RUOTA VIP
# =========================

async def ruota(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    pool = [(0,"💀"),(150,"🥉"),(300,"🥈"),(700,"🥇"),(1500,"💎"),(3000,"👑")]
    win, icon = random.choice(pool)

    u["chips"] += win
    u["wins"] += 1 if win else 0
    u["losses"] += 0 if win else 1

    save(u)

    await q.edit_message_text(f"🎡 RUOTA VIP\n\n{icon} +{win}", reply_markup=menu())


# =========================
# BONUS ULTRA
# =========================

async def bonus(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await q.edit_message_text("⏳ già preso oggi", reply_markup=menu())

    u["streak"] = u["streak"] + 1 if now - u["last_daily"] < 172800 else 1

    reward = random.randint(800, 2500) + u["streak"] * 150

    u["chips"] += reward
    u["last_daily"] = now
    u["xp"] += 80

    save(u)

    await q.edit_message_text(f"🎁 BONUS\n+{reward}\n🔥 streak {u['streak']}", reply_markup=menu())


# =========================
# BLACKJACK BASE
# =========================

hands = {}

async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    hands[u["user_id"]] = [card(), card()]

    await q.edit_message_text(
        f"🃏 BLACKJACK\n\nCarte: {hands[u['user_id']]}\nTotale: {score(hands[u['user_id']])}",
        reply_markup=menu()
    )


async def hit(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    if u["user_id"] not in hands:
        return

    hands[u["user_id"]].append(card())
    s = score(hands[u["user_id"]])

    if s > 21:
        u["losses"] += 1
        save(u)
        return await q.edit_message_text(f"💥 BUST! {s}", reply_markup=menu())

    await q.edit_message_text(f"🃏 HIT\n{s}\n{hands[u['user_id']]}", reply_markup=menu())


async def stand(update, context):
    q = update.callback_query
    await q.answer()

    u = user(q.from_user.id)

    s = score(hands.get(u["user_id"], []))

    win = 1500 if s <= 21 and s >= 17 else 0

    u["chips"] += win
    u["wins"] += 1 if win else 0
    u["losses"] += 0 if win else 1

    save(u)

    hands.pop(u["user_id"], None)

    await q.edit_message_text(f"🏁 STAND\n{s}\n💰 {win}", reply_markup=menu())    

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not allowed(chat_id):
        await update.message.reply_text("❌ Gruppo non autorizzato")
        return

    user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO ULTRA ATTIVO\n🎮 Benvenuto!",
        reply_markup=menu()
    )


# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat.id

    if not allowed(chat_id):
        await q.answer("❌ non autorizzato", show_alert=True)
        return

    await q.answer()

    d = q.data

    if d == "slot":
        return await slot(update, context)

    if d == "roulette":
        return await roulette(update, context)

    if d == "ruota":
        return await ruota(update, context)

    if d == "bonus":
        return await bonus(update, context)

    if d == "blackjack":
        return await blackjack(update, context)

    if d == "hit":
        return await hit(update, context)

    if d == "stand":
        return await stand(update, context)

    await q.edit_message_text("🚧 in sviluppo", reply_markup=menu())


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO ULTRA ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
