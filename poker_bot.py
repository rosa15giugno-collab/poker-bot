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

GRUPPI_AUTORIZZATI = [-1003664350829, -1002229066951]

def allowed(chat_id):
    return chat_id in GRUPPI_AUTORIZZATI


# =========================
# DATABASE
# =========================

conn = sqlite3.connect("casino_pro.db", check_same_thread=False)
cursor = conn.cursor()
lock = threading.Lock()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    chips INTEGER,
    xp INTEGER,
    wins INTEGER,
    losses INTEGER,
    last_bonus INTEGER,
    multiplier REAL
)
""")
conn.commit()


# =========================
# MMO STATE
# =========================

games = {}
pvp_queue = []


# =========================
# UTILS
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if not r:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0, 1.0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "xp": 0,
                "wins": 0,
                "losses": 0,
                "last_bonus": 0,
                "multiplier": 1.0
            }

        return {
            "user_id": r[0],
            "name": r[1],
            "chips": r[2],
            "xp": r[3],
            "wins": r[4],
            "losses": r[5],
            "last_bonus": r[6],
            "multiplier": r[7]
        }


def save(u):
    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, xp=?, wins=?, losses=?, last_bonus=?, multiplier=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["xp"], u["wins"], u["losses"],
            u["last_bonus"], u["multiplier"], u["user_id"]
        ))
        conn.commit()


# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("🆚 PvP", callback_data="pvp")],

        [InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
         InlineKeyboardButton("💰 Shop", callback_data="shop")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        return await update.message.reply_text("❌ Gruppo non autorizzato")

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO PRO SERVER ONLINE",
        reply_markup=menu()
    )


# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    reels = ["🍒","🍋","🔔","💎","7️⃣"]
    r = [random.choice(reels) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 3000
    elif r[0] == r[1] or r[1] == r[2]:
        win = 800

    win = int(win * u["multiplier"])

    u["chips"] += win
    u["xp"] += win // 20

    save(u)

    await q.message.reply_text(f"🎰 {' | '.join(r)}\n💰 +{win}", reply_markup=menu())


# =========================
# ROULETTE
# =========================

async def roulette(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    n = random.randint(0, 36)

    if n == 0:
        win = 1500
    elif n % 2 == 0:
        win = 300
    else:
        win = 0

    u["chips"] += win
    u["xp"] += win // 30

    save(u)

    await q.message.reply_text(f"🎲 Numero: {n}\n💰 +{win}", reply_markup=menu())


# =========================
# BLACKJACK
# =========================

def hand():
    return [random.randint(2, 11), random.randint(2, 11)]

def calc(h):
    t = sum(h)
    a = h.count(11)
    while t > 21 and a:
        t -= 10
        a -= 1
    return t


async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    games[q.from_user.id] = {
        "p": hand(),
        "d": hand()
    }

    g = games[q.from_user.id]

    await q.message.reply_text(
        f"🃏 Blackjack\n{g['p']} ({calc(g['p'])})",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Carta", callback_data="hit"),
             InlineKeyboardButton("🛑 Stai", callback_data="stand")]
        ])
    )


async def hit(update, context):
    q = update.callback_query
    await q.answer()

    g = games.get(q.from_user.id)
    if not g:
        return

    g["p"].append(random.randint(2, 11))

    if calc(g["p"]) > 21:
        del games[q.from_user.id]
        return await q.message.reply_text("💥 Sballato!")

    await q.message.reply_text(f"🃏 {g['p']} ({calc(g['p'])})")


async def stand(update, context):
    q = update.callback_query
    await q.answer()

    g = games.get(q.from_user.id)
    if not g:
        return

    p = calc(g["p"])
    d = calc(g["d"])

    u = get_user(q.from_user.id)

    if p > d:
        win = 900
        u["wins"] += 1
    elif p < d:
        win = 0
        u["losses"] += 1
    else:
        win = 200

    u["chips"] += win
    u["xp"] += win // 20

    save(u)
    del games[q.from_user.id]

    await q.message.reply_text(f"🃏 Tu {p} vs Dealer {d}\n💰 +{win}", reply_markup=menu())


# =========================
# BONUS
# =========================

async def bonus(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    now = int(time.time())

    if now - u["last_bonus"] < 86400:
        return await q.message.reply_text("⏳ Bonus già preso")

    reward = random.randint(500, 1800)

    u["chips"] += reward
    u["last_bonus"] = now

    save(u)

    await q.message.reply_text(f"🎁 +{reward}", reply_markup=menu())


# =========================
# SHOP
# =========================

async def shop(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text(
        "💰 SHOP\n\n"
        "1) x2 → 5000 chips\n"
        "2) x3 → 12000 chips\n"
        "Usa /buy 1 o /buy 2"
    )


async def buy(update, context):
    u = get_user(update.effective_user.id)

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
        return await update.message.reply_text("❌ Non disponibile")

    save(u)
    await update.message.reply_text("✅ Acquisto fatto")


# =========================
# PROFILO + CLASSIFICA
# =========================

async def profilo(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    await q.message.reply_text(
        f"👤 {u['name']}\n💰 {u['chips']}\n⭐ XP {u['xp']}",
        reply_markup=menu()
    )


async def classifica(update, context):
    q = update.callback_query
    await q.answer()

    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    txt = "🏆 CLASSIFICA\n\n"
    for i, (n, c) in enumerate(top, 1):
        txt += f"{i}. {n} - {c}\n"

    await q.message.reply_text(txt, reply_markup=menu())


# =========================
# ROUTER
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data

    if d == "slot":
        return await slot(update, context)
    if d == "roulette":
        return await roulette(update, context)
    if d == "blackjack":
        return await blackjack(update, context)
    if d == "hit":
        return await hit(update, context)
    if d == "stand":
        return await stand(update, context)
    if d == "bonus":
        return await bonus(update, context)
    if d == "shop":
        return await shop(update, context)
    if d == "profilo":
        return await profilo(update, context)
    if d == "classifica":
        return await classifica(update, context)

    await q.message.reply_text("🚧 In sviluppo")


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO SERVER FINAL ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
