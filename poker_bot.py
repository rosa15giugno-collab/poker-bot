import os
import random
import sqlite3
import time
import threading

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

GRUPPI_AUTORIZZATI = [-1003664350829, -1002229066951]

def is_allowed(chat_id):
    return chat_id in GRUPPI_AUTORIZZATI


# =========================
# DATABASE GOD MODE
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
    last_daily INTEGER,
    multiplier REAL
)
""")
conn.commit()


# =========================
# UTILS
# =========================

def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

def calc(mano):
    t = sum(mano)
    a = mano.count(11)
    while t > 21 and a:
        t -= 10
        a -= 1
    return t


# =========================
# USER SYSTEM GOD FIX
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if not r:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0, 0, 1.0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "xp": 0,
                "streak": 0,
                "last_daily": 0,
                "multiplier": 1.0
            }

        return {
            "user_id": r[0],
            "name": name,
            "chips": r[2],
            "wins": r[3],
            "losses": r[4],
            "xp": r[5],
            "streak": r[6],
            "last_daily": r[7],
            "multiplier": r[8]
        }


def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, wins=?, losses=?, xp=?, streak=?, last_daily=?, multiplier=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["xp"], u["streak"], u["last_daily"], u["multiplier"],
            u["user_id"]
        ))
        conn.commit()


# =========================
# RANK
# =========================

def rank(xp):
    if xp >= 5000: return "👑 LEGGENDA"
    if xp >= 2500: return "💎 PRO"
    if xp >= 1000: return "⭐ ESPERTO"
    if xp >= 300: return "🎲 PLAYER"
    return "🪙 NOVIZIO"


# =========================
# MENU GOD ITALIANO
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("🆚 PvP Blackjack", callback_data="pvp")],

        [InlineKeyboardButton("🎡 Ruota", callback_data="ruota"),
         InlineKeyboardButton("🎁 Bonus", callback_data="bonus")],

        [InlineKeyboardButton("💰 Shop", callback_data="shop"),
         InlineKeyboardButton("👤 Profilo", callback_data="profilo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

import random
import time

from core import get_user, update_user, calc


# =========================
# ANTI SPAM BASE
# =========================
cooldowns = {}

def check_cd(uid):
    now = time.time()
    if uid in cooldowns and now - cooldowns[uid] < 2:
        return False
    cooldowns[uid] = now
    return True
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from core import menu, get_user, is_allowed
from games import slot, blackjack, hit, stand, shop


async def start(update, context):
    chat_id = update.effective_chat.id

    if not is_allowed(chat_id):
        return await update.message.reply_text("❌ Non autorizzato")

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text("🟢 CASINO GOD MODE ATTIVO", reply_markup=menu())


async def cb(update, context):
    q = update.callback_query
    await q.answer()

    d = q.data

    if d == "slot":
        return await slot(update, context)

    if d == "blackjack":
        return await blackjack(update, context)

    if d == "hit":
        return await hit(update, context)

    if d == "stand":
        return await stand(update, context)

    if d == "shop":
        return await shop(update, context)

    await q.message.reply_text("🚧 Funzione in sviluppo")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO GOD MODE ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()

# =========================
# SLOT GOD MODE
# =========================

async def slot(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    if not check_cd(uid):
        return

    u = get_user(uid)

    reels = ["🍒","🍋","🔔","💎","7️⃣"]
    r = [random.choice(reels) for _ in range(3)]

    base = 0
    if r[0] == r[1] == r[2]:
        base = 3000
    elif r[0] == r[1] or r[1] == r[2]:
        base = 800

    win = int(base * u["multiplier"])

    u["chips"] += win
    u["xp"] += 25 if win else 5

    update_user(u)

    await q.message.reply_text(f"🎰 {' | '.join(r)}\n💰 +{win}")


# =========================
# BLACKJACK FIX GOD
# =========================

games = {}

async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    u = get_user(uid)

    games[uid] = {
        "player": [random.randint(2,11), random.randint(2,11)],
        "dealer": [random.randint(2,11), random.randint(2,11)]
    }

    await q.message.reply_text(
        f"🃏 BLACKJACK\nMano: {games[uid]['player']} ({calc(games[uid]['player'])})",
        reply_markup=blackjack_menu()
    )


def blackjack_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Carta", callback_data="hit"),
         InlineKeyboardButton("🛑 Stai", callback_data="stand")]
    ])


async def hit(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    g = games.get(uid)
    if not g:
        return

    g["player"].append(random.randint(2,11))

    if calc(g["player"]) > 21:
        del games[uid]
        return await q.message.reply_text("💥 Sballato!")

    await q.message.reply_text(f"🃏 {g['player']} ({calc(g['player'])})")


async def stand(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    g = games.get(uid)
    if not g:
        return

    p = calc(g["player"])
    d = calc(g["dealer"])

    u = get_user(uid)

    if p > d:
        u["chips"] += 800
        u["wins"] += 1
        result = "🏆 VINTO"
    elif p < d:
        u["losses"] += 1
        result = "💀 PERSO"
    else:
        result = "🤝 PAREGGIO"

    update_user(u)
    del games[uid]

    await q.message.reply_text(f"🃏 Tu: {p} vs Dealer: {d}\n{result}")


# =========================
# SHOP GOD MODE
# =========================

async def shop(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text(
        "💰 SHOP\n\n1) x2 moltiplicatore → 5000 chips\n2) x3 moltiplicatore → 12000 chips\n\nUsa /buy 1 o /buy 2"
    )


async def buy(update, context):
    uid = update.effective_user.id
    u = get_user(uid)

    try:
        opt = int(context.args[0])
    except:
        return await update.message.reply_text("Uso: /buy 1 o /buy 2")

    if opt == 1 and u["chips"] >= 5000:
        u["chips"] -= 5000
        u["multiplier"] = 2.0
    elif opt == 2 and u["chips"] >= 12000:
        u["chips"] -= 12000
        u["multiplier"] = 3.0
    else:
        return await update.message.reply_text("❌ Non puoi acquistare")

    update_user(u)
    await update.message.reply_text("✅ Acquisto effettuato!")
    
