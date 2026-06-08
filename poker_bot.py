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

print("🟢 CASINO UPGRADE 3 ONLINE")

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
    last_daily INTEGER,
    streak INTEGER,
    vip INTEGER
)
""")
conn.commit()

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
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "best_win": 0,
                "last_daily": 0,
                "streak": 0,
                "vip": 0
            }

        return {
            "user_id": row[0],
            "name": row[1],
            "chips": row[2],
            "wins": row[3],
            "losses": row[4],
            "best_win": row[5],
            "last_daily": row[6],
            "streak": row[7],
            "vip": row[8]
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
            last_daily=?,
            streak=?,
            vip=?
        WHERE user_id=?
        """, (
            u["name"],
            u["chips"],
            u["wins"],
            u["losses"],
            u["best_win"],
            u["last_daily"],
            u["streak"],
            u["vip"],
            u["user_id"]
        ))
        conn.commit()

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily")],
        [InlineKeyboardButton("💎 VIP", callback_data="vip")],
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🎰 CASINO UPGRADE 3\nScegli:", reply_markup=menu())

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"💰 Chips: {u['chips']}\n🔥 Streak: {u['streak']}\n💎 VIP: {u['vip']}"
    )

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 TOP 10\n\n"
    for i, (name, chips) in enumerate(top, 1):
        msg += f"{i}. {name} - {chips}\n"

    await update.message.reply_text(msg)

# =========================
# DAILY BONUS + STREAK
# =========================

def daily_bonus(u):
    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return 0, False

    # streak system
    if now - u["last_daily"] < 172800:
        u["streak"] += 1
    else:
        u["streak"] = 1

    base = random.randint(800, 2000)

    bonus = base + (u["streak"] * 200)

    if u["vip"] == 1:
        bonus *= 2

    u["chips"] += bonus
    u["last_daily"] = now

    return bonus, True

    
    # ================= SLOT =================
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
        r = [random.choice(["🍒","🍋","🍇","💎","7️⃣"]) for _ in range(3)]

        win = 0
        if r[0] == r[1] == r[2]:
            win = 1200
        elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
            win = 400

        if u["vip"] == 1:
            win *= 2

        u["chips"] += win
        u["wins"] += int(win > 0)

        update_user(u)

        await q.message.reply_text(
            f"🎰 SLOT\n{r[0]} | {r[1]} | {r[2]}\n"
            f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
            f"💰 {u['chips']}",
            reply_markup=menu()
        )

    # ================= ROULETTE =================
    elif q.data == "roulette":
        n = random.randint(0, 36)

        win = 0
        if n == 0:
            win = 2000
        elif n % 2 == 0:
            win = 300

        if u["vip"] == 1:
            win = int(win * 1.5)

        u["chips"] += win
        update_user(u)

        await q.message.reply_text(
            f"🎲 ROULETTE\nNumero: {n}\n"
            f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
            f"💰 {u['chips']}",
            reply_markup=menu()
        )

    # ================= DAILY =================
    elif q.data == "daily":
        bonus, ok = daily_bonus(u)

        if not ok:
            await q.message.reply_text("⏳ Daily già preso", reply_markup=menu())
            return

        update_user(u)

        await q.message.reply_text(
            f"🎁 DAILY BONUS +{bonus}\n🔥 Streak: {u['streak']}",
            reply_markup=menu()
        )

    # ================= VIP =================
    elif q.data == "vip":

        if u["chips"] >= 20000:
            u["vip"] = 1
            u["chips"] -= 20000
            update_user(u)

            await q.message.reply_text("💎 SEI DIVENTATO VIP!", reply_markup=menu())
        else:
            await q.message.reply_text("❌ Servono 20000 chips per VIP", reply_markup=menu())

    # ================= SALDO =================
    elif q.data == "saldo":
        await q.message.reply_text(
            f"💰 {u['chips']}\n🔥 Streak: {u['streak']}\n💎 VIP: {u['vip']}",
            reply_markup=menu()
        )

    # ================= CLASSIFICA =================
    elif q.data == "classifica":
        cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
        top = cursor.fetchall()

        msg = "🏆 TOP 10\n\n"
        for i, (name, chips) in enumerate(top, 1):
            msg += f"{i}. {name} - {chips}\n"

        await q.message.reply_text(msg, reply_markup=menu())

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO FINAL UPGRADE ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
