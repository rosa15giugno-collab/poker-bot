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
# DATABASE
# =========================

conn = sqlite3.connect("casino_pro.db", check_same_thread=False)
cursor = conn.cursor()
lock = threading.Lock()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    chips INTEGER,
    xp INTEGER,
    wins INTEGER,
    losses INTEGER,
    last_bonus INTEGER,
    multiplier REAL
)
""")
conn.commit()


# =========================
# STATE
# =========================

games = {}              # match attivi
pvp_queue = deque()    # matchmaking queue
active_matches = {}    # match id -> state
tables = {}            # user_id
user_tables = {}       # user_id


# =========================
# UTILS
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if not r:
            cursor.execute("""
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0, 0, 1.0))
            conn.commit()

            return {
                "user_id": uid,
                "name": name,
                "chips": 5000,
                "xp": 0,
                "wins": 0,
                "losses": 0,
                "last_bonus": 0,
                "multiplier": 1.0
            }

        return {
            "user_id": r[0],
            "name": r[1],
            "chips": r[2],
            "xp": r[3],
            "wins": r[4],
            "losses": r[5],
            "last_bonus": r[6],
            "multiplier": r[7]
        }


def save(u):
    with lock:
        cursor.execute("""
        UPDATE users SET name=?, chips=?, xp=?, wins=?, losses=?, last_bonus=?, multiplier=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["xp"], u["wins"], u["losses"],
            u["last_bonus"], u["multiplier"], u["user_id"]
        ))
        conn.commit()

async def safe_edit(msg, text, reply_markup=None):
    try:
        return await msg.edit_text(text, reply_markup=reply_markup)
    except:
        return await msg.edit_caption(text, reply_markup=reply_markup)

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
        menu()
    )
# =========================
# REAL TIME PVP 
# =========================

    # CREATE TAVOLO
    #----------------
def create_table():
    return {
        "players": [],
        "hands": {},
        "turn": 0,
        "started": False,
        "message": None,
        "chat_id": None,
        "dealer": []
    }

    # JOIN PVP
    #----------------

async def pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    # trova tavolo aperto
    table_id = None
    for tid, t in tables.items():
        if not t["started"] and len(t["players"]) < 6:
            table_id = tid
            break

    # crea tavolo se non esiste
    if not table_id:
        table_id = str(int(time.time()))
        tables[table_id] = create_table()

    t = tables[table_id]

    if uid in t["players"]:
        return await safe_edit("⏳ Sei già al tavolo")

    t["players"].append(uid)
    t["hands"][uid] = [random.randint(2, 11), random.randint(2, 11)]
    user_tables[uid] = table_id

    # start automatico
    if len(t["players"]) >= 2 and not t["started"]:
        t["started"] = True
        t["dealer"] = [random.randint(2, 11), random.randint(2, 11)]

        msg = await safe_edit(
            q.message,
            render_table(t),
            table_buttons(t)
        )

        t["message"] = msg.message_id
        t["chat_id"] = msg.chat_id

        asyncio.create_task(run_table(context.bot, table_id, msg.chat_id))

    # UI TAVOLO
    #----------------

def render_table(t):
    txt = "🃏 BLACKJACK TABLE\n\n"

    for i, p in enumerate(t["players"]):
        hand = t["hands"][p]
        txt += f"👤 P{i+1}: {sum(hand)} {hand}\n"

    txt += f"\n🎰 Dealer: {sum(t['dealer'])}\n"
    txt += f"\n👥 Players: {len(t['players'])}/6"

    return txt

    # PULSANTI DINAMICI
    #----------------

def table_buttons(t):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ HIT", callback_data="hit_mp"),
            InlineKeyboardButton("🛑 STAND", callback_data="stand_mp")
        ],
        [
            InlineKeyboardButton("📊 TABLE", callback_data="noop")
        ]
    ])

    # LOGICA GAME
    #----------------

async def run_table(bot, table_id, chat_id):
    t = tables[table_id]
    t["chat_id"] = chat_id

    while t["started"]:
        if len(t["players"]) == 0:
            del tables[table_id]
            return

        for uid in t["players"]:
            if uid not in t["hands"]:
                continue

            # aggiorna messaggio
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=t.get("message"),
                    text=render_table(t),
                    reply_markup=table_buttons(t)
                )
            except:
                pass

            await asyncio.sleep(2)

        break

    await finish_table(bot, table_id)

    # FINE PARTITA
    #----------------
async def finish_table(bot, table_id):
    t = tables[table_id]

    dealer_score = sum(t["dealer"])
    results = []

    for uid in t["players"]:
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

        results.append((uid, score, win))

    text = "🏁 MATCH FINITO\n\n"
    text += f"🎰 Dealer: {dealer_score}\n\n"

    for uid, score, win in results:
        text += f"👤 {uid} → {score} | +{win}\n"

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
        f"🃏 Blackjack\n{g['p']} ({calc(g['p'])})",
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
            "💥 Sballato!",
            reply_markup=menu()
        )

        return

    await safe_edit(
        f"🃏 {g['p']} ({calc(g['p'])})",
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

    p = calc(g["p"])
    d = calc(g["d"])

    u = get_user(q.from_user.id)

    if p > d:
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
        f"🃏 Tu {p} vs Dealer {d}\n💰 +{win}",
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
        return await safe_edit("⏳ Bonus già preso", reply_markup=menu())

    reward = random.randint(500, 1500)

    u["chips"] += reward
    u["last_bonus"] = now

    save(u)

    await safe_edit(f"🎁 +{reward}", reply_markup=menu())

#===========================
# ACQUISTA
#==========================
async def shop(update, context):
    q = update.callback_query
    await q.answer()

    await safe_edit(
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

async def profilo(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    await safe_edit(
        f"👤 {u['name']}\n💰 {u['chips']}\n⭐ XP {u['xp']}",
        reply_markup=menu()
    )


async def classifica(update, context):
    q = update.callback_query
    await q.answer()

    cursor.execute("SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    txt = "🏆 CLASSIFICA\n\n"
    for i, (n, c) in enumerate(top, 1):
        txt += f"{i}. {n} - {c}\n"

    await safe_text(txt, reply_markup=menu())


# =========================
# CALLBACK ROUTER FIXED
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    print("🔥 CB:", q.from_user.id, q.data)

    try:
        if q.data == "slot":
            await slot(update, context)

        elif q.data == "roulette":
            await roulette(update, context)

        elif q.data == "blackjack":
            await blackjack(update, context)

        elif q.data == "hit_mp":
            await hit_mp(update, context)

        elif q.data == "stand_mp":
            await stand_mp(update, context)

        elif q.data == "bonus":
            await bonus(update, context)

        elif q.data == "profilo":
            await profilo(update, context)

        elif q.data == "classifica":
            await classifica(update, context)

        elif q.data == "shop":
            await acquista_button(update, context)

        elif q.data == "pvp":
            await pvp(update, context)

        else:
            await safe_edit("🚧 In sviluppo", reply_markup=menu())

    except Exception as e:
        print("❌ ERROR:", e)
        await safe_edit("⚠️ Errore temporaneo", reply_markup=menu())
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
