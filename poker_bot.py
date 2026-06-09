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

print("🟡 CASINO ULTRA ORO 4.0 ONLINE")

# =========================
# GRUPPI AUTORIZZATI
# =========================

ALLOWED_GROUPS = [
    -1003664350829,
    -1002229066951
]

def is_allowed(update):
    chat = update.effective_chat
    if not chat:
        return False

    # privato sempre ok (se vuoi puoi togliere questa riga)
    if chat.type == "private":
        return True

    return chat.id in ALLOWED_GROUPS

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
    last_bonus INTEGER
)
""")
conn.commit()

# =========================
# GLOBAL STATE
# =========================

blackjack = {}
tavoli = {}
jackpot = 0

TURN_TIME = 20

def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

# =========================
# UTENTE
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if r is None:
            cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                           (uid, name, 5000, 0, 0, 0))
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
            "user_id": r[0],
            "name": r[1],
            "chips": r[2],
            "wins": r[3],
            "losses": r[4],
            "last_bonus": r[5]
        }

def update_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            wins=?,
            losses=?,
            last_bonus=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["wins"],
            u["losses"], u["last_bonus"], u["user_id"]
        ))
        conn.commit()

# =========================
# SEND SAFE
# =========================

async def send(update, context, text, markup=None):
    q = update.callback_query
    await context.bot.send_message(q.message.chat_id, text, reply_markup=markup)

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

        [InlineKeyboardButton("🎯 PvP Blackjack", callback_data="crea_tavolo")]
    ])

# =========================
# START (WHITELIST)
# =========================

async def start(update, context):
    if not is_allowed(update):
        if update.message:
            await update.message.reply_text("❌ Questo gruppo non è autorizzato.")
        return

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟡 CASINO ULTRA ORO 4.0\n🎮 Benvenuto!",
        reply_markup=menu()
    )

# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    global jackpot

    bet = 500
    if u["chips"] < bet:
        return await send(update, context, "❌ Chips insufficienti", menu())

    u["chips"] -= bet
    jackpot += 50

    r = [random.choice(["🍒","🍋","🍇","💎","7️⃣"]) for _ in range(3)]

    win = 3000 if r[0]==r[1]==r[2] else 800 if r[0]==r[1] or r[1]==r[2] else 0

    if win > 0:
        u["chips"] += win + jackpot
        jackpot = 0

    u["wins" if win>0 else "losses"] += 1
    update_user(u)

    await send(update, context,
        f"🎰 SLOT\n{r[0]}|{r[1]}|{r[2]}\n💥 JACKPOT {jackpot}",
        menu()
    )

# =========================
# BLACKJACK BOT
# =========================

blackjack_data = {}

async def blackjack_start(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    mano = [carta(), carta()]
    dealer = [carta(), carta()]

    blackjack_data[uid] = {"mano": mano, "dealer": dealer}

    await send(update, context,
        f"🃏 MANO: {mano} = {sum(mano)}\n🎩 Dealer: [{dealer[0]}, ?]",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 PESCA", callback_data="pesca"),
             InlineKeyboardButton("🛑 STAI", callback_data="stai")]
        ])
    )

async def pesca(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack_data.get(uid)
    if not g:
        return await send(update, context, "❌ Nessuna partita", menu())

    g["mano"].append(carta())
    s = sum(g["mano"])

    if s > 21:
        del blackjack_data[uid]
        return await send(update, context, f"💥 Sballato {s}", menu())

    await send(update, context, f"🎯 {g['mano']} = {s}")

async def stai(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack_data.get(uid)
    if not g:
        return await send(update, context, "❌ Nessuna partita", menu())

    p = sum(g["mano"])
    d = g["dealer"]

    while sum(d) < 17:
        d.append(carta())

    ds = sum(d)

    res = "🏆 VINTO" if (ds>21 or p>ds) else "💀 PERSO" if p<ds else "🤝 PARI"

    del blackjack_data[uid]

    await send(update, context,
        f"🃏 RISULTATO\n👤 {p}\n🎩 {ds}\n\n{res}",
        menu()
    )

# =========================
# CALLBACK (WHITELIST ATTIVA)
# =========================

async def cb(update, context):
    if not is_allowed(update):
        return

    q = update.callback_query
    await q.answer()

    d = q.data

    if d == "slot": return await slot(update,context)
    if d == "blackjack": return await blackjack_start(update,context)
    if d == "pesca": return await pesca(update,context)
    if d == "stai": return await stai(update,context)

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟡 CASINO ULTRA ORO 4.0 ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
