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

print("🟢 CASINO UPGRADE 6 ONLINE")

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
    bank INTEGER,
    xp INTEGER,
    level INTEGER,
    wins INTEGER,
    losses INTEGER,
    last_daily INTEGER
)
""")
conn.commit()

# =========================
# LOBBY / JACKPOT GLOBAL
# =========================

jackpot = 5000
lobby_pvp = []

games = {}

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
            """, (uid, name, 5000, 0, 0, 1, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "bank": 0,
                "xp": 0,
                "level": 1,
                "wins": 0,
                "losses": 0,
                "last_daily": 0
            }

        return {
            "user_id": row[0],
            "name": row[1],
            "chips": row[2],
            "bank": row[3],
            "xp": row[4],
            "level": row[5],
            "wins": row[6],
            "losses": row[7],
            "last_daily": row[8]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            bank=?,
            xp=?,
            level=?,
            wins=?,
            losses=?,
            last_daily=?
        WHERE user_id=?
        """, (
            u["name"],
            u["chips"],
            u["bank"],
            u["xp"],
            u["level"],
            u["wins"],
            u["losses"],
            u["last_daily"],
            u["user_id"]
        ))
        conn.commit()

# =========================
# XP
# =========================

def add_xp(u, amount):
    u["xp"] += amount
    need = u["level"] * 1000
    if u["xp"] >= need:
        u["xp"] -= need
        u["level"] += 1
        return True
    return False

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("💰 Jackpot", callback_data="jackpot")],
        [InlineKeyboardButton("⚔️ PvP Lobby", callback_data="lobby")],
        [InlineKeyboardButton("🏦 Bank", callback_data="bank")],
        [InlineKeyboardButton("🎁 Daily", callback_data="daily")],
        [InlineKeyboardButton("👤 Profilo", callback_data="profilo")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🎰 CASINO UPGRADE 6\nEntra nella lobby:", reply_markup=menu())

# =========================
# DAILY
# =========================

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Daily già preso", reply_markup=menu())

    reward = random.randint(1000, 3500)
    u["chips"] += reward
    u["last_daily"] = now

    update_user(u)

    await update.message.reply_text(f"🎁 +{reward} chips", reply_markup=menu())

# =========================
# BLACKJACK
# =========================

def deck():
    d = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] * 4
    random.shuffle(d)
    return d

def value(hand):
    t, a = 0, 0
    for c in hand:
        if c in ["J","Q","K"]:
            t += 10
        elif c == "A":
            t += 11
            a += 1
        else:
            t += int(c)

    while t > 21 and a:
        t -= 10
        a -= 1
    return t

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global jackpot

    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid, q.from_user.first_name)

    # ================= SLOT =================
    if q.data == "slot":
        r = [random.choice(["🍒","🍋","🍇","💎","7️⃣"]) for _ in range(3)]

        win = 0
        if r[0] == r[1] == r[2]:
            win = 2000
        elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
            win = 500

        jackpot += 50
        u["chips"] += win

        add_xp(u, 100 if win else 30)
        update_user(u)

        await q.message.reply_text(
            f"🎰 {r[0]} | {r[1]} | {r[2]}\n💰 +{win}\n💎 Jackpot: {jackpot}",
            reply_markup=menu()
        )

    # ================= JACKPOT =================
    elif q.data == "jackpot":
        roll = random.randint(1, 1000)

        if roll == 7:
            u["chips"] += jackpot
            msg = f"💥 JACKPOT VINTO: {jackpot}"
            jackpot = 5000
        else:
            msg = "❌ Non hai vinto"

        update_user(u)

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= LOBBY PVP =================
    elif q.data == "lobby":
        lobby_pvp.append(uid)

        if len(lobby_pvp) >= 2:
            p1 = lobby_pvp.pop(0)
            p2 = lobby_pvp.pop(0)

            w1 = random.randint(1, 100)
            w2 = random.randint(1, 100)

            if w1 > w2:
                winner = p1
            else:
                winner = p2

            if winner == uid:
                u["chips"] += 1500
                update_user(u)
                msg = "🏆 VINTO PVP LOBBY +1500"
            else:
                msg = "💀 HAI PERSO PVP"

            await q.message.reply_text(msg, reply_markup=menu())
        else:
            await q.message.reply_text("⏳ In attesa player...", reply_markup=menu())

    # ================= BANK =================
    elif q.data == "bank":
        deposit = min(1500, u["chips"])
        u["chips"] -= deposit
        u["bank"] += deposit

        update_user(u)

        await q.message.reply_text(f"🏦 +{deposit} in banca", reply_markup=menu())

    # ================= CLASSIFICA =================
    elif q.data == "classifica":
        cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
        top = cursor.fetchall()

        msg = "🏆 TOP PLAYERS\n\n"
        for i, (name, chips) in enumerate(top, 1):
            msg += f"{i}. {name} - {chips}\n"

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= PROFILO =================
    elif q.data == "profilo":
        await q.message.reply_text(
            f"👤 {u['name']}\n💰 {u['chips']}\n🏦 {u['bank']}\n⭐ Lv.{u['level']}\nXP {u['xp']}",
            reply_markup=menu()
        )

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE UPGRADE 6")
    app.run_polling()

if __name__ == "__main__":
    main()
    
