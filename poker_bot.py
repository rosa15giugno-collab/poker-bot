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

print("🟢 CASINO PRO V5.1 ONLINE")

# =========================
# DATABASE
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
    mazzo = [2,3,4,5,6,7,8,9,10,10,10,10,11]
    return random.choice(mazzo)

# =========================
# USER SYSTEM
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
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],

        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette"),
         InlineKeyboardButton("🎡 Ruota Fortuna", callback_data="ruota")],

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
        "🎰 CASINO PRO V5.1 🇮🇹\nScegli un gioco:",
        reply_markup=menu()
    )

# =========================
# SLOT
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    scommessa = 500
    u["chips"] -= scommessa

    simboli = ["🍒","🍋","🍇","💎","7️⃣"]
    r = [random.choice(simboli) for _ in range(3)]

    if r[0] == r[1] == r[2]:
        vincita = 3000
    elif r[0] == r[1] or r[1] == r[2]:
        vincita = 800
    else:
        vincita = 0

    u["chips"] += vincita
    if vincita > 0:
        u["vittorie"] += 1
    else:
        u["sconfitte"] += 1

    if u["chips"] < 0:
        u["chips"] = 0

    update_user(u)

    await q.message.reply_text(
        f"🎰 SLOT\n\n"
        f"{r[0]} | {r[1]} | {r[2]}\n"
        f"💸 Scommessa: -{scommessa}\n"
        f"💰 Vincita: +{vincita}\n"
        f"💳 Saldo: {u['chips']}",
        reply_markup=menu()
    )

# =========================
# ROULETTE
# =========================

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    scommessa = 300
    u["chips"] -= scommessa

    n = random.randint(0, 36)

    if n == 0:
        vincita = 2000
    elif n % 2 == 0:
        vincita = 600
    else:
        vincita = 0

    u["chips"] += vincita
    if vincita > 0:
        u["vittorie"] += 1
    else:
        u["sconfitte"] += 1

    if u["chips"] < 0:
        u["chips"] = 0

    update_user(u)

    await q.message.reply_text(
        f"🎲 ROULETTE\n\nNumero: {n}\n💸 Scommessa: -{scommessa}\n💰 Vincita: +{vincita}\n💳 Saldo: {u['chips']}",
        reply_markup=menu()
    )

# =========================
# RUOTA FORTUNA
# =========================

async def ruota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    premi = [0,0,100,200,500,1000,2000]
    vincita = random.choice(premi)

    u["chips"] += vincita

    if vincita > 0:
        u["vittorie"] += 1
    else:
        u["sconfitte"] += 1

    update_user(u)

    await q.message.reply_text(
        f"🎡 RUOTA FORTUNA\n\nHai vinto: +{vincita}\n💳 Saldo: {u['chips']}",
        reply_markup=menu()
    )

# =========================
# BONUS
# =========================

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    now = int(time.time())

    if now - u["ultimo_bonus"] < 86400:
        return await q.message.reply_text("⏳ Bonus già preso oggi", reply_markup=menu())

    premio = random.randint(500, 2000)

    u["chips"] += premio
    u["ultimo_bonus"] = now

    update_user(u)

    await q.message.reply_text(
        f"🎁 BONUS GIORNALIERO +{premio}\n💳 Saldo: {u['chips']}",
        reply_markup=menu()
    )

# =========================
# SALDO + CLASSIFICA
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = get_user(q.from_user.id, q.from_user.first_name)

    await q.message.reply_text(f"💰 SALDO: {u['chips']}", reply_markup=menu())

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    cursor.execute("SELECT nome, chips FROM utenti ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 CLASSIFICA TOP 10\n\n"
    for i, (n, c) in enumerate(top, 1):
        msg += f"{i}. {n} - {c}\n"

    await q.message.reply_text(msg, reply_markup=menu())

# =========================
# BLACKJACK
# =========================

async def blackjack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = str(q.from_user.id)

    player = [carta(), carta()]
    dealer = [carta(), carta()]

    blackjack[uid] = {"player": player, "dealer": dealer}

    await q.message.reply_text(
        f"🃏 BLACKJACK\n\n"
        f"👤 Tu: {player} = {sum(player)}\n"
        f"🎩 Dealer: [{dealer[0]}, ?]\n",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 PESCA", callback_data="bj_pesca"),
             InlineKeyboardButton("🛑 STAI", callback_data="bj_stai")]
        ])
    )

async def bj_pesca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack.get(uid)
    if not g:
        return await q.message.reply_text("❌ Nessuna partita attiva")

    g["player"].append(carta())
    score = sum(g["player"])

    if score > 21:
        del blackjack[uid]
        return await q.message.reply_text(f"💥 Sballato! Hai perso ({score})")

    await q.message.reply_text(f"🎯 PESCA\n👤 Mano: {g['player']} = {score}")

async def bj_stai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack.get(uid)
    if not g:
        return await q.message.reply_text("❌ Nessuna partita attiva")

    player_score = sum(g["player"])
    dealer = g["dealer"]

    while sum(dealer) < 17:
        dealer.append(carta())

    dealer_score = sum(dealer)

    if dealer_score > 21 or player_score > dealer_score:
        risultato = "🏆 HAI VINTO"
    elif player_score < dealer_score:
        risultato = "💀 HAI PERSO"
    else:
        risultato = "🤝 PAREGGIO"

    del blackjack[uid]

    await q.message.reply_text(
        f"🃏 RISULTATO\n\n"
        f"👤 Tu: {player_score}\n"
        f"🎩 Dealer: {dealer_score}\n\n"
        f"{risultato}"
    )

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if q.data == "profilo":
        u = get_user(q.from_user.id, q.from_user.first_name)

        partite = u["vittorie"] + u["sconfitte"]
        livello = 1 + (partite // 20)

        grado = "🥉 Bronzo"
        if livello >= 10:
            grado = "🥈 Argento"
        if livello >= 20:
            grado = "🥇 Oro"
        if livello >= 40:
            grado = "💎 Diamante"

        await q.message.reply_text(
            f"👤 PROFILO\n\n"
            f"🧑 Nome: {u['nome']}\n"
            f"💰 Chips: {u['chips']}\n"
            f"🏆 Vittorie: {u['vittorie']}\n"
            f"💀 Sconfitte: {u['sconfitte']}\n"
            f"🎮 Partite: {partite}\n"
            f"⭐ Livello: {livello}\n"
            f"🎖️ Grado: {grado}",
            reply_markup=menu()
        )
        return

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
