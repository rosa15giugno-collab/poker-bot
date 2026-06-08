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

print("🟢 CASINO UPGRADE 4 ONLINE")

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
    xp INTEGER,
    level INTEGER,
    wins INTEGER,
    losses INTEGER,
    last_daily INTEGER
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
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 1, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
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
            "xp": row[3],
            "level": row[4],
            "wins": row[5],
            "losses": row[6],
            "last_daily": row[7]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            xp=?,
            level=?,
            wins=?,
            losses=?,
            last_daily=?
        WHERE user_id=?
        """, (
            u["name"],
            u["chips"],
            u["xp"],
            u["level"],
            u["wins"],
            u["losses"],
            u["last_daily"],
            u["user_id"]
        ))
        conn.commit()

# =========================
# LEVEL SYSTEM
# =========================

def add_xp(u, amount):
    u["xp"] += amount

    needed = u["level"] * 1000

    if u["xp"] >= needed:
        u["xp"] -= needed
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
        [InlineKeyboardButton("👤 Profilo", callback_data="profilo")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🎰 CASINO UPGRADE 4\nScegli:", reply_markup=menu())

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 TOP LIVELLI\n\n"
    for i, (name, lvl, xp) in enumerate(top, 1):
        msg += f"{i}. {name} - Lv.{lvl} ({xp} XP)\n"

    await update.message.reply_text(msg)
    
games = {}

# =========================
# SLOT
# =========================

def slot_game():
    symbols = ["🍒","🍋","🍇","💎","7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 1200
    elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
        win = 300

    return r, win

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

        r, win = slot_game()

        u["chips"] += win

        xp_gain = 120 if win > 0 else 40
        leveled = add_xp(u, xp_gain)

        if win > 0:
            u["wins"] += 1
        else:
            u["losses"] += 1

        update_user(u)

        msg = (
            f"🎰 SLOT\n{r[0]} | {r[1]} | {r[2]}\n\n"
            f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
            f"⭐ +{xp_gain} XP\n"
            f"💰 {u['chips']} | Lv.{u['level']}"
        )

        if leveled:
            msg += "\n🎉 LEVEL UP!"

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= ROULETTE =================
    elif q.data == "roulette":

        n = random.randint(0, 36)

        if n == 0:
            win = 2000
        elif n % 2 == 0:
            win = 300
        else:
            win = 0

        u["chips"] += win

        xp_gain = 100 if win > 0 else 30
        leveled = add_xp(u, xp_gain)

        update_user(u)

        msg = (
            f"🎲 ROULETTE\nNumero: {n}\n\n"
            f"{'🎉 +' + str(win) if win else '💀 Perso'}\n"
            f"⭐ +{xp_gain} XP\n"
            f"💰 {u['chips']} | Lv.{u['level']}"
        )

        if leveled:
            msg += "\n🎉 LEVEL UP!"

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= PROFILO =================
    elif q.data == "profilo":

        await q.message.reply_text(
            f"👤 PROFILO\n\n"
            f"Nome: {u['name']}\n"
            f"💰 Chips: {u['chips']}\n"
            f"⭐ XP: {u['xp']}\n"
            f"📊 Livello: {u['level']}\n"
            f"🏆 Vittorie: {u['wins']}\n"
            f"💀 Sconfitte: {u['losses']}",
            reply_markup=menu()
        )

    # ================= CLASSIFICA =================
    elif q.data == "classifica":

        cursor.execute("SELECT name, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10")
        top = cursor.fetchall()

        msg = "🏆 TOP PLAYERS\n\n"
        for i, (name, lvl, xp) in enumerate(top, 1):
            msg += f"{i}. {name} - Lv.{lvl} ({xp} XP)\n"

        await q.message.reply_text(msg, reply_markup=menu())

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("classifica", classifica))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO UPGRADE 4 ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
