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

print("🟢 CASINO ARENA BOT ONLINE")

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
    last_daily INTEGER
)
""")
conn.commit()

# =========================
# ARENE + GAMES
# =========================

games = {}
arenas = {}

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
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "last_daily": 0
            }

        return {
            "user_id": row[0],
            "name": row[1],
            "chips": row[2],
            "wins": row[3],
            "losses": row[4],
            "last_daily": row[5]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            wins=?,
            losses=?,
            last_daily=?
        WHERE user_id=?
        """, (
            u["name"],
            u["chips"],
            u["wins"],
            u["losses"],
            u["last_daily"],
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
        [InlineKeyboardButton("⚔️ Arena PvP", callback_data="arena")],
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🎰 CASINO ARENA SYSTEM\nScegli un gioco:",
        reply_markup=menu()
    )

# =========================
# GAME HELPERS
# =========================

def deck():
    d = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] * 4
    random.shuffle(d)
    return d

def value(hand):
    t = 0
    a = 0

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
# ARENA SYSTEM
# =========================

def create_arena(owner, bet):
    arena_id = str(random.randint(1000, 9999))

    arenas[arena_id] = {
        "owner": owner,
        "bet": bet,
        "players": [owner],
        "created": time.time(),
        "state": "waiting"
    }

    return arena_id


def resolve_arena(arena_id):
    arena = arenas.get(arena_id)
    if not arena:
        return "❌ Arena non valida"

    players = arena["players"]

    if len(players) < 2:
        for p in players:
            u = get_user(p)
            u["chips"] += arena["bet"]
            update_user(u)

        arenas.pop(arena_id, None)
        return "❌ Arena annullata (pochi giocatori)"

    results = []

    for p in players:
        u = get_user(p)
        score = random.randint(1, 100) + (u["wins"] // 5)
        results.append((p, score))

    results.sort(key=lambda x: x[1], reverse=True)

    winner = results[0][0]
    pot = arena["bet"] * len(players)

    u = get_user(winner)
    u["chips"] += pot
    u["wins"] += 1
    update_user(u)

    for p, _ in results[1:]:
        u2 = get_user(p)
        u2["losses"] += 1
        update_user(u2)

    arenas.pop(arena_id, None)

    return f"🏆 VINCE {u['name']} +{pot} chips!"

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
            win = 300

        u["chips"] += win
        u["wins"] += int(win > 0)
        update_user(u)

        await q.message.reply_text(
            f"🎰 {r[0]} | {r[1]} | {r[2]}\n💰 +{win}",
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

        u["chips"] += win
        update_user(u)

        await q.message.reply_text(
            f"🎲 {n} → {'WIN +' + str(win) if win else 'LOSE'}",
            reply_markup=menu()
        )

    # ================= SALDO =================
    elif q.data == "saldo":
        await q.message.reply_text(f"💰 {u['chips']}", reply_markup=menu())

    # ================= CLASSIFICA =================
    elif q.data == "classifica":
        cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
        top = cursor.fetchall()

        msg = "🏆 TOP\n\n"
        for i, (name, chips) in enumerate(top, 1):
            msg += f"{i}. {name} - {chips}\n"

        await q.message.reply_text(msg, reply_markup=menu())

    # ================= ARENA CREATE =================
    elif q.data == "arena":

        bet = 500

        if u["chips"] < bet:
            return await q.message.reply_text("❌ Non hai chips")

        u["chips"] -= bet
        update_user(u)

        arena_id = create_arena(uid, bet)
        arenas[arena_id]["players"].append(uid)

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎮 Entra Arena", callback_data=f"join_{arena_id}")
        ]])

        await q.message.reply_text(
            f"⚔️ ARENA APERTA\n💰 {bet} chips\n👥 2-4 player\n⏳ parte in 20s",
            reply_markup=keyboard
        )

    # ================= JOIN ARENA =================
    elif q.data.startswith("join_"):

        arena_id = q.data.split("_")[1]
        arena = arenas.get(arena_id)

        if not arena:
            return await q.message.reply_text("❌ Arena non esiste")

        if uid in arena["players"]:
            return await q.message.reply_text("⚠️ già dentro")

        if len(arena["players"]) >= 4:
            return await q.message.reply_text("❌ piena")

        if u["chips"] < arena["bet"]:
            return await q.message.reply_text("❌ non hai chips")

        u["chips"] -= arena["bet"]
        update_user(u)

        arena["players"].append(uid)

        await q.message.reply_text(f"✅ Entrato! ({len(arena['players'])}/4)")

        # auto start semplice
        if len(arena["players"]) >= 2:
            result = resolve_arena(arena_id)

            for p in arena["players"]:
                try:
                    await context.bot.send_message(
                        chat_id=p,
                        text=result,
                        reply_markup=menu()
                    )
                except:
                    pass

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT READY")
    app.run_polling()

if __name__ == "__main__":
    main()
