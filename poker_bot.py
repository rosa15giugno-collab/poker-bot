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
# DB
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
    level INTEGER,
    last_bonus INTEGER,
    multiplier REAL
)
""")
conn.commit()


# =========================
# STATE
# =========================

games = {}
pvp_rooms = {}
jackpot = 0


# =========================
# UTILS
# =========================

def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

def calc(hand):
    t = sum(hand)
    a = hand.count(11)
    while t > 21 and a:
        t -= 10
        a -= 1
    return t


def level_from_xp(xp):
    return xp // 500


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
                "level": 0,
                "last_bonus": 0,
                "multiplier": 1.0
            }

        return {
            "user_id": r[0],
            "name": name,
            "chips": r[2],
            "wins": r[3],
            "losses": r[4],
            "xp": r[5],
            "level": r[6],
            "last_bonus": r[7],
            "multiplier": r[8]
        }


def save(u):
    u["level"] = level_from_xp(u["xp"])

    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, wins=?, losses=?, xp=?, level=?, last_bonus=?, multiplier=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["xp"], u["level"], u["last_bonus"], u["multiplier"], u["user_id"]
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
         InlineKeyboardButton("🆚 PvP", callback_data="pvp_menu")],

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

    if not allowed(chat_id):
        return await update.message.reply_text("❌ Gruppo non autorizzato")

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO GOD FINAL BOSS MODE ATTIVO",
        reply_markup=menu()
    )


# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    r = [random.choice(["🍒","🍋","🔔","💎","7️⃣"]) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = int(3000 * u["multiplier"])
    elif r[0] == r[1] or r[1] == r[2]:
        win = int(800 * u["multiplier"])

    u["chips"] += win
    u["xp"] += 10 + win // 100

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
    u["wins"] += 1 if win > 0 else 0
    u["losses"] += 1 if win == 0 else 0
    u["xp"] += win // 50

    save(u)

    await q.message.reply_text(f"🎲 Numero: {n}\n💰 +{win}", reply_markup=menu())


# =========================
# BLACKJACK
# =========================

async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    games[uid] = {
        "p": [carta(), carta()],
        "d": [carta(), carta()]
    }

    await q.message.reply_text(
        f"🃏 Blackjack\n{games[uid]['p']} ({calc(games[uid]['p'])})",
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

    g["p"].append(carta())

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
    del games[uid]

    await q.message.reply_text(f"Tu {p} vs Dealer {d}\n💰 +{win}")


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

    await q.message.reply_text(f"🎁 +{reward}")


# =========================
# SHOP
# =========================

async def shop(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text(
        "💰 SHOP\n\n"
        "1) Moltiplicatore x2 → 5000 chips\n"
        "2) Moltiplicatore x3 → 12000 chips\n\n"
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
    await update.message.reply_text("✅ Acquisto effettuato")


# =========================
# PROFILO
# =========================

async def profilo(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    tot = u["wins"] + u["losses"]
    wr = round(u["wins"] / tot * 100, 2) if tot else 0

    await q.message.reply_text(
        f"👤 {u['name']}\n"
        f"💰 {u['chips']}\n"
        f"🏆 WR {wr}%\n"
        f"⭐ XP {u['xp']}\n"
        f"📊 Livello {u['level']}",
        reply_markup=menu()
    )


# =========================
# CLASSIFICA
# =========================

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
# CALLBACK ROUTER
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

    await q.message.reply_text("🚧 Modalità in sviluppo")


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO GOD FINAL BOSS MODE ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
