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

print("🟢 CASINO PRO UPGRADED ONLINE")

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
    best_win INTEGER,
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
# VIP LEVEL
# =========================

def vip(chips):
    if chips >= 1000000:
        return "👑 RE CASINO"
    if chips >= 250000:
        return "💎 DIAMANTE"
    if chips >= 50000:
        return "🥇 ORO"
    if chips >= 10000:
        return "🥈 ARGENTO"
    return "🥉 BRONZO"

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],

        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette"),
         InlineKeyboardButton("🎁 Bonus", callback_data="bonus")],

        [InlineKeyboardButton("🎡 Ruota", callback_data="wheel"),
         InlineKeyboardButton("💰 Saldo", callback_data="saldo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        f"🎰 CASINO PRO UPGRADED\n\n💰 {u['chips']} chips\n{vip(u['chips'])}",
        reply_markup=menu()
    )

# =========================
# SALDO
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    await update.message.reply_text(
        f"💰 Chips: {u['chips']}\n{vip(u['chips'])}",
        reply_markup=menu()
    )

# =========================
# SLOT
# =========================

def slot_game(u):
    s = ["🍒","🍋","🍇","💎","7️⃣"]
    r = [random.choice(s) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 1200
    elif r[0] == r[1] or r[1] == r[2]:
        win = 400

    u["chips"] += win
    u["wins"] += int(win > 0)
    u["losses"] += int(win == 0)

    update_user(u)

    return r, win
    
# =========================
# BLACKJACK
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

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid, q.from_user.first_name)

    # ================= SLOT =================

    if q.data == "slot":
        r, win = slot_game(u)

        testo = (
            "🎰 SLOT MACHINE\n\n"
            f"{r[0]} │ {r[1]} │ {r[2]}\n\n"
        )

        testo += f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
        testo += f"💰 {u['chips']} | {vip(u['chips'])}"

        await q.message.reply_text(testo, reply_markup=menu())

    # ================= BLACKJACK START =================

    elif q.data == "blackjack":

        d = deck()
        player = [d.pop(), d.pop()]
        dealer = [d.pop(), d.pop()]

        games[uid] = {"d": d, "p": player, "dl": dealer}

        keyboard = [[
            InlineKeyboardButton("🎯 HIT", callback_data="hit"),
            InlineKeyboardButton("🛑 STAND", callback_data="stand")
        ]]

        await q.message.reply_text(
            f"🃏 BLACKJACK\n\n"
            f"TU: {player} ({value(player)})\n"
            f"BANCO: [{dealer[0]}, ?]",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= ROULETTE =================

    elif q.data == "roulette":

        num = random.randint(0, 36)

        if num == 0:
            win = 1500
        elif num % 2 == 0:
            win = 300
        else:
            win = 0

        u["chips"] += win
        update_user(u)

        await q.message.reply_text(
            f"🎲 ROULETTE\n\nNumero: {num}\n"
            f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
            f"💰 {u['chips']} | {vip(u['chips'])}",
            reply_markup=menu()
        )

    # ================= BONUS GIORNALIERO =================

    elif q.data == "bonus":

        now = int(time.time())

        if now - u["last_daily"] < 86400:
            await q.message.reply_text("⏳ Hai già preso il bonus oggi", reply_markup=menu())
            return

        reward = random.randint(500, 3000)

        u["chips"] += reward
        u["last_daily"] = now

        update_user(u)

        await q.message.reply_text(
            f"🎁 BONUS GIORNALIERO\n\n+{reward} chips",
            reply_markup=menu()
        )

    # ================= RUOTA FORTUNA =================

    elif q.data == "wheel":

        rewards = [0, 100, 250, 500, 1000, 2500, 5000]
        reward = random.choice(rewards)

        u["chips"] += reward
        update_user(u)

        await q.message.reply_text(
            f"🎡 RUOTA\n\nHai vinto: {reward} chips",
            reply_markup=menu()
        )

    # ================= SALDO =================

    elif q.data == "saldo":

        await q.message.reply_text(
            f"💰 {u['chips']} chips\n{vip(u['chips'])}",
            reply_markup=menu()
        )

    # ================= CLASSIFICA =================

    elif q.data == "classifica":

        with lock:
            cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
            top = cursor.fetchall()

        msg = "🏆 TOP 10\n\n"

        for i, (name, chips) in enumerate(top, 1):
            msg += f"{i}. {name} - {chips}\n"

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= BLACKJACK HIT =================

    elif q.data == "hit":

        g = games.get(uid)
        if not g:
            return

        g["p"].append(g["d"].pop())

        if value(g["p"]) > 21:
            games.pop(uid, None)
            await q.message.reply_text("💀 SBALLATO", reply_markup=menu())
            return

        await q.message.reply_text(f"TU: {g['p']} ({value(g['p'])})")

    # ================= BLACKJACK STAND =================

    elif q.data == "stand":

        g = games.get(uid)
        if not g:
            return

        while value(g["dl"]) < 17:
            g["dl"].append(g["d"].pop())

        pv = value(g["p"])
        dv = value(g["dl"])

        if pv > dv:
            u["chips"] += 200
            result = "🎉 VINTO"
        elif pv == dv:
            result = "⚖️ PAREGGIO"
        else:
            result = "💀 PERSO"

        update_user(u)
        games.pop(uid, None)

        await q.message.reply_text(
            f"{result}\n\nTu: {pv}\nBanco: {dv}",
            reply_markup=menu()
        )

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO UPGRADED ONLINE")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
