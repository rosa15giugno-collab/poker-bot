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

print("🟢 CASINO PRO V9 FINAL ONLINE")

# =========================
# DB
# =========================

conn = sqlite3.connect("casino.db", check_same_thread=False)
cursor = conn.cursor()
lock = threading.Lock()

cursor.execute("""
CREATE TABLE IF NOT EXISTS utenti (
    user_id TEXT PRIMARY KEY,
    nome TEXT,
    chips INTEGER,
    wins INTEGER,
    losses INTEGER,
    last_bonus INTEGER
)
""")
conn.commit()

# =========================
# GAME STATE
# =========================

blackjack_bot = {}
tables = {}

def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

# =========================
# USER SYSTEM
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM utenti WHERE user_id=?", (uid,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                "INSERT INTO utenti VALUES (?, ?, ?, ?, ?, ?)",
                (uid, name, 5000, 0, 0, 0)
            )
            conn.commit()
            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "last_bonus": 0
            }

        return {
            "user_id": row[0],
            "name": row[1],
            "chips": row[2],
            "wins": row[3],
            "losses": row[4],
            "last_bonus": row[5]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE utenti SET
            name=?,
            chips=?,
            wins=?,
            losses=?,
            last_bonus=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"], u["losses"],
            u["last_bonus"], u["user_id"]
        ))
        conn.commit()

# =========================
# SAFE SEND (GRUPPI FIX DEFINITIVO)
# =========================

async def send(update, context, text, markup=None):
    q = update.callback_query
    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text=text,
        reply_markup=markup
    )

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],

        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette"),
         InlineKeyboardButton("🎡 Ruota", callback_data="ruota")],

        [InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
         InlineKeyboardButton("👤 Profilo", callback_data="profilo")],

        [InlineKeyboardButton("💰 Saldo", callback_data="saldo"),
         InlineKeyboardButton("🏆 Classifica", callback_data="classifica")],

        [InlineKeyboardButton("🎯 Blackjack PvP", callback_data="create_table")]
    ])

# =========================
# START
# =========================

async def start(update, context):
    get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text("🎰 CASINO V9 FINAL", reply_markup=menu())

# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    bet = 500
    if u["chips"] < bet:
        return await send(update, context, "❌ Chips insufficienti", menu())

    u["chips"] -= bet

    r = [random.choice(["🍒","🍋","🍇","💎","7️⃣"]) for _ in range(3)]

    if r[0] == r[1] == r[2]:
        win = 3000
    elif r[0] == r[1] or r[1] == r[2]:
        win = 800
    else:
        win = 0

    u["chips"] += win
    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    update_user(u)

    await send(update, context,
        f"🎰 SLOT\n{r[0]} | {r[1]} | {r[2]}\n💸 -{bet}\n💰 +{win}\n💳 {u['chips']}",
        menu()
    )

# =========================
# ROULETTE
# =========================

async def roulette(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    bet = 300
    if u["chips"] < bet:
        return await send(update, context, "❌ Chips insufficienti", menu())

    u["chips"] -= bet
    n = random.randint(0, 36)

    if n == 0:
        win = 2000
    elif n % 2 == 0:
        win = 600
    else:
        win = 0

    u["chips"] += win
    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    update_user(u)

    await send(update, context,
        f"🎲 ROULETTE\n{n}\n💸 -{bet}\n💰 +{win}\n💳 {u['chips']}",
        menu()
    )

# =========================
# RUOTA
# =========================

async def ruota(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    win = random.choice([0,0,100,200,500,1000,2000])
    u["chips"] += win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    update_user(u)

    await send(update, context,
        f"🎡 RUOTA\n+{win}\n💳 {u['chips']}",
        menu()
    )

# =========================
# BONUS
# =========================

async def bonus(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    now = int(time.time())
    if now - u["last_bonus"] < 86400:
        return await send(update, context, "⏳ Bonus già preso oggi", menu())

    reward = random.randint(500, 2000)
    u["chips"] += reward
    u["last_bonus"] = now

    update_user(u)

    await send(update, context,
        f"🎁 BONUS +{reward}\n💳 {u['chips']}",
        menu()
    )

# =========================
# SALDO / CLASSIFICA
# =========================

async def saldo(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)
    await send(update, context, f"💰 SALDO: {u['chips']}", menu())

async def classifica(update, context):
    q = update.callback_query

    cursor.execute("SELECT name, chips FROM utenti ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 TOP 10\n\n"
    for i,(n,c) in enumerate(top,1):
        msg += f"{i}. {n} - {c}\n"

    await send(update, context, msg, menu())

# =========================
# BLACKJACK BOT
# =========================

blackjack = {}

async def blackjack_start(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    player = [carta(), carta()]
    dealer = [carta(), carta()]

    blackjack[uid] = {"player": player, "dealer": dealer}

    await send(update, context,
        f"🃏 BLACKJACK\n👤 {player} = {sum(player)}\n🎩 [{dealer[0]}, ?]",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 PESCA", callback_data="bj_hit"),
             InlineKeyboardButton("🛑 STAI", callback_data="bj_stand")]
        ])
    )

async def bj_hit(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack.get(uid)
    if not g:
        return await send(update, context, "❌ Nessuna partita")

    g["player"].append(carta())
    score = sum(g["player"])

    if score > 21:
        del blackjack[uid]
        return await send(update, context, f"💥 Sballato {score}")

    await send(update, context, f"🎯 {g['player']} = {score}")

async def bj_stand(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack.get(uid)
    if not g:
        return await send(update, context, "❌ Nessuna partita")

    p = sum(g["player"])
    d = g["dealer"]

    while sum(d) < 17:
        d.append(carta())

    ds = sum(d)

    if ds > 21 or p > ds:
        res = "🏆 VINTO"
    elif p < ds:
        res = "💀 PERSO"
    else:
        res = "🤝 PARI"

    del blackjack[uid]

    await send(update, context,
        f"🃏 RISULTATO\n👤 {p}\n🎩 {ds}\n\n{res}"
    )

# =========================
# PVP BLACKJACK (2–6 PLAYER)
# =========================

def new_table(owner):
    tid = str(random.randint(1000,9999))
    tables[tid] = {
        "owner": owner,
        "players": [owner]
    }
    return tid

async def create_table(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    tid = new_table(uid)

    await send(update, context,
        f"🎯 TAVOLO {tid}\n👥 1/6",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ENTRA", callback_data=f"join_{tid}"),
             InlineKeyboardButton("🚀 AVVIA", callback_data=f"start_{tid}")]
        ])
    )

async def join_table(update, context, tid):
    q = update.callback_query
    uid = str(q.from_user.id)

    t = tables.get(tid)
    if not t:
        return await send(update, context, "❌ Tavolo non esiste")

    if uid not in t["players"] and len(t["players"]) < 6:
        t["players"].append(uid)

    await send(update, context,
        f"🎯 TAVOLO {tid}\n👥 {len(t['players'])}/6"
    )

async def start_table(update, context, tid):
    q = update.callback_query
    t = tables.get(tid)

    if not t or len(t["players"]) < 2:
        return await send(update, context, "❌ Minimo 2 giocatori")

    results = []

    for p in t["players"]:
        hand = [carta(), carta()]
        results.append((p, sum(hand)))

    winner = max(results, key=lambda x: x[1])

    del tables[tid]

    await send(update, context,
        "🏆 RISULTATI\n\n" +
        "\n".join([f"{p}: {s}" for p,s in results]) +
        f"\n\n🥇 Vincitore: {winner[0]}"
    )

# =========================
# CALLBACK
# =========================

async def cb(update, context):
    q = update.callback_query
    await q.answer()

    d = q.data

    if d == "slot": return await slot(update, context)
    if d == "roulette": return await roulette(update, context)
    if d == "ruota": return await ruota(update, context)
    if d == "bonus": return await bonus(update, context)
    if d == "saldo": return await saldo(update, context)
    if d == "classifica": return await classifica(update, context)

    if d == "blackjack": return await blackjack_start(update, context)
    if d == "bj_hit": return await bj_hit(update, context)
    if d == "bj_stand": return await bj_stand(update, context)

    if d == "create_table": return await create_table(update, context)
    if d.startswith("join_"): return await join_table(update, context, d.split("_")[1])
    if d.startswith("start_"): return await start_table(update, context, d.split("_")[1])

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE FINAL")
    app.run_polling()

if __name__ == "__main__":
    main()
