import os
import random
import sqlite3
import threading

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")

if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

print("🟢 CASINO PRO ONLINE")

# =========================
# DATABASE SQLITE
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
# UTENTI
# =========================

def get_user(uid, name="Giocatore"):
    uid = str(uid)

    with lock:
        cursor.execute(
            "SELECT * FROM users WHERE user_id=?",
            (uid,)
        )

        row = cursor.fetchone()

        if row is None:

            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                name,
                5000,
                0,
                0,
                0,
                0
            ))

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


def update_user(user):

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
            user["name"],
            user["chips"],
            user["wins"],
            user["losses"],
            user["best_win"],
            user["last_daily"],
            user["user_id"]
        ))

        conn.commit()

# =========================
# MENU
# =========================

def menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎰 Slot Machine",
                callback_data="slot"
            ),
            InlineKeyboardButton(
                "🃏 Blackjack",
                callback_data="blackjack"
            )
        ],
        [
            InlineKeyboardButton(
                "🎲 Roulette",
                callback_data="roulette"
            ),
            InlineKeyboardButton(
                "💰 Saldo",
                callback_data="saldo"
            )
        ],
        [
            InlineKeyboardButton(
                "🏆 Classifica",
                callback_data="classifica"
            )
        ]
    ])


async def mostra_menu(chat):

    await chat.reply_text(
        "🎮 Scegli un gioco:",
        reply_markup=menu()
    )

# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    get_user(
        update.effective_user.id,
        update.effective_user.first_name
    )

    await update.message.reply_text(
        """
🎰 CASINO PRO 🎰

Benvenuto al Casinò!

💰 Chips iniziali: 5000

Scegli un gioco dal menu:
        """,
        reply_markup=menu()
    )

# =========================
# SALDO
# =========================

async def saldo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    u = get_user(update.effective_user.id)

    await update.message.reply_text(
        f"""
💰 PORTAFOGLIO

Chips: {u['chips']}
Vittorie: {u['wins']}
Sconfitte: {u['losses']}
"""
    )

# =========================
# SLOT MACHINE
# =========================

def play_slot(user):

    symbols = [
        "🍒",
        "🍋",
        "🍇",
        "💎",
        "7️⃣"
    ]

    reels = [
        random.choice(symbols),
        random.choice(symbols),
        random.choice(symbols)
    ]

    win = 0

    if reels[0] == reels[1] == reels[2]:
        win = 1000

    elif (
        reels[0] == reels[1]
        or reels[1] == reels[2]
        or reels[0] == reels[2]
    ):
        win = 300

    user["chips"] += win

    if win:
        user["wins"] += 1
    else:
        user["losses"] += 1

    if win > user["best_win"]:
        user["best_win"] = win

    update_user(user)

    return reels, win

# =========================
# BLACKJACK
# =========================

games = {}

def deck():

    cards = [
        "A","2","3","4","5","6","7",
        "8","9","10","J","Q","K"
    ] * 4

    random.shuffle(cards)

    return cards


def value(hand):

    total = 0
    aces = 0

    for card in hand:

        if card in ["J", "Q", "K"]:
            total += 10

        elif card == "A":
            total += 11
            aces += 1

        else:
            total += int(card)

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

# =========================
# CALLBACK MENU
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid, q.from_user.first_name)

    # ================= SLOT =================

    if q.data == "slot":

        r, win = play_slot(u)

        testo = (
            "╔══════════════╗\n"
            "🎰 SLOT MACHINE\n"
            "╚══════════════╝\n\n"
            f"{r[0]} │ {r[1]} │ {r[2]}\n\n"
        )

        if win:
            testo += f"🎉 HAI VINTO {win} CHIPS!\n"
        else:
            testo += "💀 NESSUNA VINCITA\n"

        testo += f"\n💰 Saldo: {u['chips']}"

        await q.message.reply_text(
            testo,
            reply_markup=menu()
        )

    # ================= BLACKJACK START =================

    elif q.data == "blackjack":

        d = deck()
        player = [d.pop(), d.pop()]
        dealer = [d.pop(), d.pop()]

        games[uid] = {
            "d": d,
            "p": player,
            "dl": dealer
        }

        keyboard = [[
            InlineKeyboardButton("🎯 CARTA", callback_data="hit"),
            InlineKeyboardButton("🛑 STO", callback_data="stand")
        ]]

        await q.message.reply_text(
            "🃏 BLACKJACK\n\n"
            f"👤 Tu: {player} ({value(player)})\n"
            f"🤖 Banco: [{dealer[0]}, ?]",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= ROULETTE =================

    elif q.data == "roulette":

        numero = random.randint(0, 36)

        if numero == 0:
            win = 1400
        elif numero % 2 == 0:
            win = 200
        else:
            win = 0

        u["chips"] += win
        update_user(u)

        testo = (
            "🎲 ROULETTE\n\n"
            f"Numero uscito: {numero}\n\n"
        )

        if win:
            testo += f"🎉 HAI VINTO {win} CHIPS!\n"
        else:
            testo += "💀 HAI PERSO\n"

        testo += f"\n💰 Saldo: {u['chips']}"

        await q.message.reply_text(
            testo,
            reply_markup=menu()
        )

    # ================= SALDO =================

    elif q.data == "saldo":

        await q.message.reply_text(
            f"💰 Hai {u['chips']} chips",
            reply_markup=menu()
        )

    # ================= CLASSIFICA =================

    elif q.data == "classifica":

        with lock:
            cursor.execute("""
            SELECT name, chips
            FROM users
            ORDER BY chips DESC
            LIMIT 10
            """)
            top = cursor.fetchall()

        msg = "🏆 CLASSIFICA TOP 10\n\n"

        for i, (name, chips) in enumerate(top, start=1):
            msg += f"{i}. {name} — {chips} chips\n"

        await q.message.reply_text(
            msg,
            reply_markup=menu()
        )

    # ================= BLACKJACK HIT =================

    elif q.data == "hit":

        g = games.get(uid)

        if not g:
            return

        g["p"].append(g["d"].pop())

        totale = value(g["p"])

        if totale > 21:

            games.pop(uid, None)

            await q.message.reply_text(
                f"💀 SBALLATO!\n\nCarte: {g['p']}\nTotale: {totale}",
                reply_markup=menu()
            )
            return

        keyboard = [[
            InlineKeyboardButton("🎯 CARTA", callback_data="hit"),
            InlineKeyboardButton("🛑 STO", callback_data="stand")
        ]]

        await q.message.reply_text(
            f"🃏 Le tue carte:\n{g['p']}\n\nTotale: {totale}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= BLACKJACK STAND =================

    elif q.data == "stand":

        g = games.get(uid)

        if not g:
            return

        while value(g["dl"]) < 17:
            g["dl"].append(g["d"].pop())

        pv = value(g["p"])
        dv = value(g["dl"])

        if dv > 21 or pv > dv:

            u["chips"] += 200
            update_user(u)

            risultato = "🎉 HAI VINTO!"

        elif pv == dv:

            risultato = "⚖️ PAREGGIO"

        else:

            risultato = "💀 HAI PERSO"

        games.pop(uid, None)

        await q.message.reply_text(
            f"{risultato}\n\n"
            f"👤 Tu: {pv}\n"
            f"🤖 Banco: {dv}\n\n"
            f"💰 Saldo: {u['chips']}",
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

    print("🟢 CASINO PRO ONLINE")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
