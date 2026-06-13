import os  
import random
import sqlite3
import time
import threading
import asyncio
import logging

from collections import deque
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

# =========================
# DB
# =========================
conn = sqlite3.connect("casino_pro.db", check_same_thread=False)
cursor = conn.cursor()

# =========================
# LOCK
# =========================
lock = threading.Lock()

# =========================
# STATE
# =========================
games = {}
pvp_queue = deque()
active_matches = {}
tables = {}
user_tables = {}

# =========================
# SAFE EDIT
# =========================
async def safe_edit(message, text=None, reply_markup=None):
    try:
        if getattr(message, "text", None):
            return await message.edit_text(text, reply_markup=reply_markup)
        else:
            return await message.edit_caption(text, reply_markup=reply_markup)
    except:
        return await message.reply_text(text, reply_markup=reply_markup)

# =========================
# USER SYSTEM
# =========================
def get_user(user_id, name="Player"):
    uid = str(user_id)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        row = cursor.fetchone()

        if row:
            return {
                "user_id": row[0],
                "name": row[1],
                "chips": row[2],
                "xp": row[3],
                "wins": row[4],
                "losses": row[5],
                "last_bonus": row[6],
                "multiplier": row[7]
            }

        cursor.execute("""
            INSERT INTO users VALUES (?, ?, 1000, 0, 0, 0, 0, 1.0)
        """, (uid, name))
        conn.commit()

        return {
            "user_id": uid,
            "name": name,
            "chips": 1000,
            "xp": 0,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0,
            "multiplier": 1.0
        }

def save_user(u):
    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, xp=?, wins=?, losses=?, last_bonus=?, multiplier=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["xp"], u["wins"], u["losses"],
            u["last_bonus"], u["multiplier"], u["user_id"]
        ))
        conn.commit()

# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎰 Slot", callback_data="slot"),
            InlineKeyboardButton("🎲 Roulette", callback_data="roulette")
        ],
        [
            InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
            InlineKeyboardButton("🆚 PvP", callback_data="pvp")
        ],
        [
            InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
            InlineKeyboardButton("💰 Shop", callback_data="shop")
        ],
        [
            InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
            InlineKeyboardButton("🏆 Classifica", callback_data="classifica")
        ]
    ])

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.first_name)

    print("START ARRIVATO:", user.id)

    photo_id = "AgACAgQAAxkBAAMbaiz214DsBkP09-ZfQsrbL4MOqFgAAsoOaxsCGmhREEolIiPDR4cBAAMCAAN5AAM8BA"

    caption = (
        "👑 Benvenuto in CASINO PRO\n\n"
        "𝑰𝒍 𝒄𝒂𝒔𝒐 𝒏𝒐𝒏 è 𝒄𝒂𝒐𝒔: è 𝒖𝒏 𝒍𝒊𝒏𝒈𝒖𝒂𝒈𝒈𝒊𝒐…\n"
        "…𝒄𝒉𝒊 𝒔𝒂 𝒂𝒔𝒄𝒐𝒍𝒕𝒂𝒓𝒍𝒐 𝒗𝒊𝒏𝒄𝒆\n\n"
        "🎰 Slot | 🎲 Roulette | 🃏 Blackjack | 🆚 PvP\n"
        "🏆 Classifiche live | 🎁 Bonus giornaliero\n\n"
        "👇 Scegli una modalità"
    )

    await update.message.reply_photo(
        photo=photo_id,
        caption=caption,
        reply_markup=menu()
    )
# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    r = [random.choice(["🍒", "🍋", "🔔", "💎", "7️⃣"]) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 2500
    elif r[0] == r[1] or r[1] == r[2]:
        win = 700

    win = int(win * u["multiplier"])

    u["chips"] += win
    u["xp"] += win // 30

    save(u)

    await safe_edit(
        q.message,
        f"🎰 SLOT CASINO PRO\n\n"
        f"┃ {' | '.join(r)} ┃\n\n"
        f"💰 Vincita: +{win}\n"
        f"💎 Chips: {u['chips']}",
        reply_markup=menu()
    )
# =========================
# CREATE TABLE
# =========================

def create_table():
    return {
        "players": [],   # {id, name}
        "hands": {},     # uid -> cards
        "started": False,
        "message": None,
        "chat_id": None,
        "dealer": []
    }


# =========================
# PVP JOIN
# =========================

async def pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    name = q.from_user.first_name

    # trova tavolo
    table_id = None
    for tid, t in tables.items():
        if not t["started"] and len(t["players"]) < 6:
            table_id = tid
            break

    # crea tavolo
    if not table_id:
        table_id = str(int(time.time()))
        tables[table_id] = create_table()

    t = tables[table_id]

    # già dentro
    if any(p["id"] == uid for p in t["players"]):
        return await safe_edit(
            q.message,
            "⏳ Sei già al tavolo",
            reply_markup=menu()
        )

    # aggiungi player
    t["players"].append({
        "id": uid,
        "name": name
    })

    t["hands"][uid] = [
        random.randint(2, 11),
        random.randint(2, 11)
    ]

    user_tables[uid] = table_id

    # attesa
    if len(t["players"]) < 2:
        return await safe_edit(
            q.message,
            f"🃏 BLACKJACK TABLE\n\n"
            f"👥 Giocatori: {len(t['players'])}/6\n"
            f"⏳ In attesa...",
            reply_markup=menu()
        )

    # START GAME
    if not t["started"]:
        t["started"] = True
        t["dealer"] = [
            random.randint(2, 11),
            random.randint(2, 11)
        ]

        msg = await safe_edit(
            q.message,
            render_table(t),
            reply_markup=table_buttons(t)
        )

        t["message"] = msg.message_id
        t["chat_id"] = msg.chat_id

        print(f"TABLE STARTED: {table_id} players={len(t['players'])}")

        asyncio.create_task(run_table(context.bot, table_id, msg.chat_id))


# =========================
# RENDER TABLE
# =========================

def render_table(t):
    txt = "🃏 BLACKJACK TABLE\n\n"

    for p in t["players"]:
        uid = p["id"]
        name = p["name"]

        hand = t["hands"].get(uid, [])

        txt += f"👤 {name}: {sum(hand)} {hand}\n"

    txt += f"\n🎰 Dealer: {sum(t['dealer'])}\n"
    txt += f"\n👥 Players: {len(t['players'])}/6"

    return txt


# =========================
# BUTTONS
# =========================

def table_buttons(t):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ HIT", callback_data="hit_mp"),
            InlineKeyboardButton("🛑 STAND", callback_data="stand_mp")
        ]
    ])


# =========================
# RUN TABLE
# =========================

async def run_table(bot, table_id, chat_id):
    t = tables[table_id]

    while t["started"]:
        if len(t["players"]) == 0:
            del tables[table_id]
            return

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=t["message"],
                text=render_table(t),
                reply_markup=table_buttons(t)
            )
        except:
            pass

        await asyncio.sleep(2)

    await finish_table(bot, table_id)


# =========================
# FINISH GAME
# =========================

async def finish_table(bot, table_id):
    t = tables[table_id]

    dealer_score = sum(t["dealer"])
    results = []

    for p in t["players"]:
        uid = p["id"]
        name = p["name"]

        score = sum(t["hands"][uid])
        user = get_user(uid)

        if score > 21:
            win = 0
            user["losses"] += 1

        elif dealer_score > 21 or score > dealer_score:
            win = 1000
            user["wins"] += 1

        elif score == dealer_score:
            win = 300

        else:
            win = 0
            user["losses"] += 1

        user["chips"] += win
        save(user)

        results.append((name, score, win))

    text = "🏁 MATCH FINITO\n\n"
    text += f"🎰 Dealer: {dealer_score}\n\n"

    for name, score, win in results:
        text += f"👤 {name}: {score} | +{win}\n"

    await bot.send_message(t["chat_id"], text)

    del tables[table_id]

# =========================
# ROULETTE
# =========================

async def roulette(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    n = random.randint(0, 36)

    if n == 0:
        win = 1500
    elif n % 2 == 0:
        win = 300
    else:
        win = 0

    u["chips"] += win
    u["xp"] += win // 30

    save(u)

    await safe_edit(
        q.message,
        f"🎲 Numero: {n}\n💰 +{win}",
        reply_markup=menu()
    )
# =========================
# BLACKJACK
# =========================

def hand():
    return [random.randint(2, 11), random.randint(2, 11)]


def calc(h):
    t = sum(h)
    a = h.count(11)

    while t > 21 and a:
        t -= 10
        a -= 1

    return t


async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    games[q.from_user.id] = {
        "p": hand(),
        "d": hand()
    }

    g = games[q.from_user.id]

    await safe_edit(
        q.message,
        f"🃏 Blackjack\n\n"
        f"Le tue carte: {g['p']}\n"
        f"Totale: {calc(g['p'])}",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "➕ Carta",
                    callback_data="hit"
                ),
                InlineKeyboardButton(
                    "🛑 Stai",
                    callback_data="stand"
                )
            ]
        ])
    )


async def hit(update, context):
    q = update.callback_query
    await q.answer()

    g = games.get(q.from_user.id)

    if not g:
        return

    g["p"].append(random.randint(2, 11))

    if calc(g["p"]) > 21:
        del games[q.from_user.id]

        await safe_edit(
            q.message,
            "💥 Hai sballato!",
            reply_markup=menu()
        )
        return

    await safe_edit(
        q.message,
        f"🃏 Blackjack\n\n"
        f"Le tue carte: {g['p']}\n"
        f"Totale: {calc(g['p'])}",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "➕ Carta",
                    callback_data="hit"
                ),
                InlineKeyboardButton(
                    "🛑 Stai",
                    callback_data="stand"
                )
            ]
        ])
    )


async def stand(update, context):
    q = update.callback_query
    await q.answer()

    g = games.get(q.from_user.id)

    if not g:
        return

    while calc(g["d"]) < 17:
        g["d"].append(random.randint(2, 11))

    p = calc(g["p"])
    d = calc(g["d"])

    u = get_user(q.from_user.id)

    if d > 21 or p > d:
        win = 900
        u["wins"] += 1

    elif p < d:
        win = 0
        u["losses"] += 1

    else:
        win = 200

    u["chips"] += win
    u["xp"] += win // 20

    save(u)

    del games[q.from_user.id]

    await safe_edit(
        q.message,
        f"🃏 BLACKJACK\n\n"
        f"👤 Tu: {p}\n"
        f"🎰 Dealer: {d}\n\n"
        f"💰 Vincita: +{win}",
        reply_markup=menu()
    )
# =========================
# BONUS
# =========================

async def bonus(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    now = int(time.time())

    if now - u["last_bonus"] < 86400:
        return await safe_edit(
            q.message,
            "⏳ Bonus già preso",
            reply_markup=menu()
        )

    reward = random.randint(500, 1500)

    u["chips"] += reward
    u["last_bonus"] = now

    save(u)

    await safe_edit(
        q.message,
        f"🎁 BONUS GIORNALIERO\n\n💰 +{reward} Chips",
        reply_markup=menu()
    )

#===========================
# ACQUISTA
#==========================
async def shop(update, context):
    q = update.callback_query
    await q.answer()

    await safe_edit(
        q.message,
        "💰 SHOP CASINO PRO\n\n"
        "1️⃣ x2 Multiplier → 5000 chips\n"
        "2️⃣ x3 Multiplier → 12000 chips\n\n"
        "Usa:\n/acquista 1\n/acquista 2",
        reply_markup=menu()
    )


# =========================
# SHOP
# =========================

async def acquista(update, context):
    u = get_user(update.effective_user.id)

    try:
        opt = int(context.args[0])
    except:
        return await update.message.reply_text("Uso: /acquista 1 o /acquista 2")

    if opt == 1 and u["chips"] >= 5000:
        u["chips"] -= 5000
        u["multiplier"] = 2.0

    elif opt == 2 and u["chips"] >= 12000:
        u["chips"] -= 12000
        u["multiplier"] = 3.0

    else:
        return await update.message.reply_text("❌ Non disponibile o chips insufficienti")

    save(u)

    await update.message.reply_text(
        f"💰 ACQUISTO COMPLETATO\n\n"
        f"🎯 Moltiplicatore attuale: x{u['multiplier']}"
    )


# =========================
# PROFILO + CLASSIFICA
# =========================

async def classifica(update, context):
    q = update.callback_query
    await q.answer()

    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    txt = "🏆 CLASSIFICA\n\n"
    for i, (n, c) in enumerate(top, 1):
        txt += f"{i}. {n} - {c}\n"

    await safe_edit(
        q.message,
        txt,
        reply_markup=menu()
    )


# =========================
# CALLBACK ROUTER FIXED
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    print("🔥 CB:", q.from_user.id, q.data)

    try:
        data = q.data

        if data == "slot":
            return await slot(update, context)

        elif data == "roulette":
            return await roulette(update, context)

        elif data == "blackjack":
            return await blackjack(update, context)

        elif data == "hit_mp":
            return await hit_mp(update, context)

        elif data == "stand_mp":
            return await stand_mp(update, context)

        elif data == "bonus":
            return await bonus(update, context)

        elif data == "profilo":
            return await profilo(update, context)

        elif data == "classifica":
            return await classifica(update, context)

        elif data == "shop":
            return await shop(update, context)

        elif data == "pvp":
            return await pvp(update, context)

        else:
            return await safe_edit(
                q.message,
                "🚧 In sviluppo",
                reply_markup=menu()
            )

    except Exception as e:
        print("❌ ERROR:", e)

        try:
            return await safe_edit(
                q.message,
                "⚠️ Errore temporaneo",
                reply_markup=menu()
            )
        except Exception as e2:
            print("❌ SAFE_EDIT FAILED:", e2)
# =========================
# MAIN
# =========================

async def fileid(update, context):
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]

        await update.message.reply_text(
            f"📸 FILE ID:\n\n{photo.file_id}"
        )
    else:
        await update.message.reply_text(
            "❌ Rispondi a una foto con /fileid"
        )




def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fileid", fileid))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO DEFINITIVO ONLINE")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
