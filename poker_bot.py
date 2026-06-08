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

print("🟢 CASINO PRO V6 GRUPPI FIX ONLINE")

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
    vittorie INTEGER,
    sconfitte INTEGER,
    ultimo_bonus INTEGER
)
""")
conn.commit()

# =========================
# BLACKJACK MEMORY
# =========================

blackjack = {}

def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

# =========================
# UTENTE
# =========================

def get_user(uid, nome="Giocatore"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM utenti WHERE user_id=?", (uid,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("""
            INSERT INTO utenti VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, nome, 5000, 0, 0, 0))
            conn.commit()

            return {
                "user_id": uid,
                "nome": nome,
                "chips": 5000,
                "vittorie": 0,
                "sconfitte": 0,
                "ultimo_bonus": 0
            }

        return {
            "user_id": row[0],
            "nome": row[1],
            "chips": row[2],
            "vittorie": row[3],
            "sconfitte": row[4],
            "ultimo_bonus": row[5]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE utenti SET
            nome=?,
            chips=?,
            vittorie=?,
            sconfitte=?,
            ultimo_bonus=?
        WHERE user_id=?
        """, (
            u["nome"],
            u["chips"],
            u["vittorie"],
            u["sconfitte"],
            u["ultimo_bonus"],
            u["user_id"]
        ))
        conn.commit()

# =========================
# SAFE SEND (FIX GRUPPI)
# =========================

async def safe_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text, markup=None):
    q = update.callback_query
    try:
        await context.bot.send_message(
            chat_id=q.message.chat_id,
            text=text,
            reply_markup=markup
        )
    except Exception as e:
        print("ERRORE SEND:", e)

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
         InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🎰 CASINO PRO V6\nScegli un gioco:",
        reply_markup=menu()
    )

# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    bet = 500
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
        u["vittorie"] += 1
    else:
        u["sconfitte"] += 1

    if u["chips"] < 0:
        u["chips"] = 0

    update_user(u)

    await safe_send(update, context,
        f"🎰 SLOT\n{r[0]} | {r[1]} | {r[2]}\n💸 -{bet}\n💰 +{win}\n💳 {u['chips']}",
        menu()
    )

# =========================
# ROULETTE
# =========================

async def roulette(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    bet = 300
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
        u["vittorie"] += 1
    else:
        u["sconfitte"] += 1

    if u["chips"] < 0:
        u["chips"] = 0

    update_user(u)

    await safe_send(update, context,
        f"🎲 ROULETTE\nNumero: {n}\n💸 -{bet}\n💰 +{win}\n💳 {u['chips']}",
        menu()
    )

# =========================
# RUOTA
# =========================

async def ruota(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    win = random.choice([0,0,100,200,500,1000,2000])

    u["chips"] += win

    if win > 0:
        u["vittorie"] += 1
    else:
        u["sconfitte"] += 1

    update_user(u)

    await safe_send(update, context,
        f"🎡 RUOTA\n+{win}\n💳 {u['chips']}",
        menu()
    )

# =========================
# BONUS
# =========================

async def bonus(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    now = int(time.time())

    if now - u["ultimo_bonus"] < 86400:
        return await safe_send(update, context, "⏳ Bonus già preso oggi", menu())

    reward = random.randint(500, 2000)

    u["chips"] += reward
    u["ultimo_bonus"] = now

    update_user(u)

    await safe_send(update, context,
        f"🎁 BONUS +{reward}\n💳 {u['chips']}",
        menu()
    )

# =========================
# SALDO + CLASSIFICA
# =========================

async def saldo(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    await safe_send(update, context, f"💰 SALDO: {u['chips']}", menu())

async def classifica(update, context):
    q = update.callback_query

    cursor.execute("SELECT nome, chips FROM utenti ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 TOP 10\n\n"
    for i, (n, c) in enumerate(top, 1):
        msg += f"{i}. {n} - {c}\n"

    await safe_send(update, context, msg, menu())

# =========================
# BLACKJACK (GRUPPI SAFE)
# =========================

async def blackjack_start(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    player = [carta(), carta()]
    dealer = [carta(), carta()]

    blackjack[uid] = {"player": player, "dealer": dealer}

    await safe_send(update, context,
        f"🃏 BLACKJACK\n👤 {player} = {sum(player)}\n🎩 [{dealer[0]}, ?]",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 PESCA", callback_data="bj_pesca"),
             InlineKeyboardButton("🛑 STAI", callback_data="bj_stai")]
        ])
    )

async def bj_pesca(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack.get(uid)
    if not g:
        return await safe_send(update, context, "❌ Nessuna partita")

    g["player"].append(carta())
    score = sum(g["player"])

    if score > 21:
        del blackjack[uid]
        return await safe_send(update, context, f"💥 Sballato ({score})")

    await safe_send(update, context, f"🎯 PESCA\n{g['player']} = {score}")

async def bj_stai(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack.get(uid)
    if not g:
        return await safe_send(update, context, "❌ Nessuna partita")

    player = sum(g["player"])
    dealer = g["dealer"]

    while sum(dealer) < 17:
        dealer.append(carta())

    d = sum(dealer)

    if d > 21 or player > d:
        res = "🏆 VINTO"
    elif player < d:
        res = "💀 PERSO"
    else:
        res = "🤝 PARI"

    del blackjack[uid]

    await safe_send(update, context,
        f"🃏 RISULTATO\n👤 {player}\n🎩 {d}\n\n{res}"
    )

# =========================
# CALLBACK
# =========================

async def cb(update, context):
    q = update.callback_query
    await q.answer()

    if q.data == "slot":
        return await slot(update, context)
    if q.data == "roulette":
        return await roulette(update, context)
    if q.data == "ruota":
        return await ruota(update, context)
    if q.data == "bonus":
        return await bonus(update, context)
    if q.data == "saldo":
        return await saldo(update, context)
    if q.data == "classifica":
        return await classifica(update, context)

    if q.data == "blackjack":
        return await blackjack_start(update, context)
    if q.data == "bj_pesca":
        return await bj_pesca(update, context)
    if q.data == "bj_stai":
        return await bj_stai(update, context)

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
