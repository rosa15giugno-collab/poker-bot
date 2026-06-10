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

print("🟢 CASINO GOD MODE ONLINE")


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

def calc(hand):
    total = sum(hand)
    aces = hand.count(11)

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total


# =========================
# USER SYSTEM
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


def rank(xp):
    if xp >= 5000: return "👑 LEGGENDA"
    if xp >= 2500: return "💎 PRO"
    if xp >= 1000: return "⭐ ESPERTO"
    if xp >= 300: return "🎲 GIOCATORE"
    return "🪙 NOVIZIO"


# =========================
# MENU ITALIANO
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],

        [InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
         InlineKeyboardButton("💰 Shop", callback_data="shop")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not is_allowed(chat_id):
        return await update.message.reply_text("❌ Gruppo non autorizzato")

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO GOD MODE ATTIVO\n🎮 Scegli un gioco:",
        reply_markup=menu()
    )


# =========================
# SLOT
# =========================
async def slot(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    symbols = ["🍒","🍋","🔔","💎","7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 3000
    elif r[0] == r[1] or r[1] == r[2]:
        win = 800

    win = int(win * u["multiplier"])

    u["chips"] += win
    u["xp"] += 10

    update_user(u)

    await q.message.reply_text(f"🎰 {' | '.join(r)}\n💰 +{win}")


# =========================
# BLACKJACK (FIXATO)
# =========================
games = {}

async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    games[uid] = {
        "p": [random.randint(2,11), random.randint(2,11)],
        "d": [random.randint(2,11), random.randint(2,11)]
    }

    await q.message.reply_text(
        f"🃏 BLACKJACK\nMano: {games[uid]['p']} ({calc(games[uid]['p'])})",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Carta", callback_data="hit"),
             InlineKeyboardButton("🛑 Stai", callback_data="stand")]
        ])
    )


async def hit(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    g = games.get(uid)
    if not g:
        return

    g["p"].append(random.randint(2,11))

    if calc(g["p"]) > 21:
        del games[uid]
        return await q.message.reply_text("💥 Sballato!")

    await q.message.reply_text(f"🃏 {g['p']} ({calc(g['p'])})")


async def stand(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    g = games.get(uid)
    if not g:
        return

    p = calc(g["p"])
    d = calc(g["d"])

    u = get_user(uid)

    if p > d:
        u["chips"] += 800
        u["wins"] += 1
        res = "🏆 VINTO"
    elif p < d:
        u["losses"] += 1
        res = "💀 PERSO"
    else:
        res = "🤝 PAREGGIO"

    update_user(u)
    del games[uid]

    await q.message.reply_text(f"🃏 Tu {p} vs Dealer {d}\n{res}")


# =========================
# BONUS
# =========================
async def bonus(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await q.message.reply_text("⏳ già preso oggi")

    u["streak"] = u["streak"] + 1 if now - u["last_daily"] < 172800 else 1

    reward = random.randint(500,1500)

    u["chips"] += reward
    u["last_daily"] = now

    update_user(u)

    await q.message.reply_text(f"🎁 +{reward}")


# =========================
# CALLBACK ROUTER
# =========================
async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    d = q.data

    if d == "slot":
        return await slot(update, context)

    if d == "roulette":
        return await q.message.reply_text("🚧 Roulette in sviluppo")

    if d == "blackjack":
        return await blackjack(update, context)

    if d == "hit":
        return await hit(update, context)

    if d == "stand":
        return await stand(update, context)

    if d == "bonus":
        return await bonus(update, context)

    await q.message.reply_text("🚧 In sviluppo")


# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO GOD MODE ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
