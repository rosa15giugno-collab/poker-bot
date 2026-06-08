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

print("🟢 CASINO UPGRADE 5 ONLINE")

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
# XP SYSTEM
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
        [InlineKeyboardButton("🏦 Banca", callback_data="bank")],
        [InlineKeyboardButton("⚔️ PvP", callback_data="pvp")],
        [InlineKeyboardButton("🎁 Daily", callback_data="daily")],
        [InlineKeyboardButton("👤 Profilo", callback_data="profilo")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# BLACKJACK STATE
# =========================

games = {}

def deck():
    d = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] * 4
    random.shuffle(d)
    return d

def value(hand):
    total = 0
    aces = 0

    for c in hand:
        if c in ["J","Q","K"]:
            total += 10
        elif c == "A":
            total += 11
            aces += 1
        else:
            total += int(c)

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🎰 CASINO UPGRADE 5\nScegli:", reply_markup=menu())

# =========================
# DAILY
# =========================

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    now = int(time.time())

    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ già preso")

    reward = random.randint(1000, 3000)
    u["chips"] += reward
    u["last_daily"] = now

    update_user(u)

    await update.message.reply_text(f"🎁 +{reward}", reply_markup=menu())

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
            win = 1500
        elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
            win = 400

        u["chips"] += win
        add_xp(u, 120 if win else 40)
        u["wins"] += int(win > 0)
        u["losses"] += int(win == 0)

        update_user(u)

        await q.message.reply_text(
            f"🎰 {r[0]} | {r[1]} | {r[2]}\n{'🎉 +'+str(win) if win else '💀 Perso'}",
            reply_markup=menu()
        )

    # ================= ROULETTE =================
    elif q.data == "roulette":
        n = random.randint(0, 36)

        if n == 0:
            win = 2500
        elif n % 2 == 0:
            win = 400
        else:
            win = 0

        u["chips"] += win
        add_xp(u, 100 if win else 30)

        update_user(u)

        await q.message.reply_text(
            f"🎲 {n} | {'WIN' if win else 'LOSE'} +{win}",
            reply_markup=menu()
        )

    # ================= BANK =================
    elif q.data == "bank":
        deposit = min(1000, u["chips"])
        u["chips"] -= deposit
        u["bank"] += deposit
        update_user(u)

        await q.message.reply_text(
            f"🏦 Deposito automatico: {deposit}\nBank: {u['bank']}",
            reply_markup=menu()
        )

    # ================= PVP =================
    elif q.data == "pvp":
        enemy = random.randint(1, 100)
        player = random.randint(1, 100)

        if player > enemy:
            u["chips"] += 1000
            result = "🏆 VINTO PvP +1000"
        else:
            result = "💀 PERSO PvP"

        update_user(u)

        await q.message.reply_text(result, reply_markup=menu())

    # ================= PROFILO =================
    elif q.data == "profilo":
        await q.message.reply_text(
            f"👤 {u['name']}\n💰 {u['chips']}\n🏦 {u['bank']}\n⭐ Lv.{u['level']}\nXP {u['xp']}",
            reply_markup=menu()
        )

    # ================= CLASSIFICA =================
    elif q.data == "classifica":
        cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
        top = cursor.fetchall()

        msg = "🏆 TOP\n\n"
        for i, (name, chips) in enumerate(top, 1):
            msg += f"{i}. {name} - {chips}\n"

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= BLACKJACK =================
    elif q.data == "blackjack":
        d = deck()
        p = [d.pop(), d.pop()]
        dl = [d.pop(), d.pop()]

        games[uid] = {"d": d, "p": p, "dl": dl}

        await q.message.reply_text(
            f"🃏 {p} ({value(p)}) vs [{dl[0]}, ?]",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("HIT", callback_data="hit"),
                InlineKeyboardButton("STAND", callback_data="stand")
            ]])
        )

    elif q.data == "hit":
        g = games.get(uid)
        if not g:
            return

        g["p"].append(g["d"].pop())

        if value(g["p"]) > 21:
            games.pop(uid)
            await q.message.reply_text("💀 Sballato", reply_markup=menu())
            return

        await q.message.reply_text(f"{g['p']} ({value(g['p'])})")

    elif q.data == "stand":
        g = games.get(uid)
        if not g:
            return

        while value(g["dl"]) < 17:
            g["dl"].append(g["d"].pop())

        pv = value(g["p"])
        dv = value(g["dl"])

        if pv > dv:
            u["chips"] += 1200
            msg = "🏆 VINTO"
        elif pv == dv:
            msg = "⚖️ PAREGGIO"
        else:
            msg = "💀 PERSO"

        update_user(u)
        games.pop(uid)

        await q.message.reply_text(
            f"{msg}\nTu:{pv} Banco:{dv}",
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

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
    
