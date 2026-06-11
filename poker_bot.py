import os
import random
import sqlite3
import time
import threading
from collections import deque

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

GRUPPI_AUTORIZZATI = [-1003664350829, -1002229066951]

def allowed(chat_id):
    return chat_id in GRUPPI_AUTORIZZATI


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
# MMO STATE
# =========================

games = {}              # match attivi
pvp_queue = deque()    # matchmaking queue
active_matches = {}    # match id -> state


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


# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("🆚 PvP", callback_data="pvp")],

        [InlineKeyboardButton("🎁 Bonus", callback_data="bonus"),
         InlineKeyboardButton("💰 Shop", callback_data="shop")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])


# =========================
# START
# =========================

# Funzione immagine di benvenuto
async def fileid(update, context):

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "📷 Rispondi ad una foto con /fileid"
        )

    if not update.message.reply_to_message.photo:
        return await update.message.reply_text(
            "❌ Quello non è una foto"
        )

    photo = update.message.reply_to_message.photo[-1]

    await update.message.reply_text(
        f"FILE ID:\n\n{photo.file_id}"
    )
#fine funzione

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_chat.id):
        return await update.message.reply_text("❌ Gruppo non autorizzato")

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_photo(
    photo="AgACAgQAAyEFAATaaY5tAAIQ8Wop5hJDkqhSsGRsfd2u8h-mQsYmAALIDWsbAwdQUdjjqwhQoAABFQEAAwIAA3kAAzsE",
    caption=
    "     Benvenuto in 👑 Casinò by Rosa \n\n"
    "   𝓘𝓵 𝓬𝓪𝓼𝓸 𝓷𝓸𝓷 𝓮̀ 𝓬𝓪𝓸𝓼: 𝓮̀ 𝓾𝓷 𝓵𝓲𝓷𝓰𝓾𝓪𝓰𝓰𝓲𝓸.\n"
    "       𝓒𝓱𝓲 𝓼𝓪 𝓪𝓼𝓬𝓸𝓵𝓽𝓪𝓻𝓵𝓸, 𝓿𝓲𝓷𝓬𝓮.\n"
    "____________________________________________\n"
    "  Slot, Blackjack, Roulette e classifiche\n"
    "                settimanali\n"
    " ____________________________________________\n"
    "  𝓘𝓵 𝓭𝓮𝓼𝓽𝓲𝓷𝓸 𝓽𝓲 𝓰𝓾𝓪𝓻𝓭𝓪. 𝓣𝓾 𝓰𝓾𝓪𝓻𝓭𝓲 𝓵𝓾𝓲"
    "👇 Scegli una modalità",
    reply_markup=menu()
)


# =========================
# SLOT
# =========================

async def slot(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    r = [random.choice(["🍒","🍋","🔔","💎","7️⃣"]) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = 2500
    elif r[0] == r[1] or r[1] == r[2]:
        win = 700

    win = int(win * u["multiplier"])

    u["chips"] += win
    u["xp"] += win // 30

    save(u)
    await q.message.reply_text(f"🎰 {' | '.join(r)}\n💰 +{win}", reply_markup=menu())

# =========================
# REAL TIME PVP MATCHMAKING
# =========================

def create_match(p1, p2):
    mid = f"{p1}{p2}{int(time.time())}"

    active_matches[mid] = {
        "p1": p1,
        "p2": p2,
        "p1_score": 0,
        "p2_score": 0,
        "round": 0,
        "msg_id": None,
        "chat_id": None
    }

    return mid


def calc_round(m):
    r1 = random.randint(1, 10)
    r2 = random.randint(1, 10)

    m["p1_score"] += r1
    m["p2_score"] += r2
    m["round"] += 1

    return r1, r2


async def finish_match(bot, mid):
    m = active_matches.get(mid)
    if not m:
        return

    p1 = get_user(m["p1"])
    p2 = get_user(m["p2"])

    if m["p1_score"] > m["p2_score"]:
        p1["wins"] += 1
        p2["losses"] += 1
        result = f"🏆 VINCE {p1['name']}"
    else:
        p2["wins"] += 1
        p1["losses"] += 1
        result = f"🏆 VINCE {p2['name']}"

    save(p1)
    save(p2)

    if m["chat_id"] and m["msg_id"]:
        await bot.edit_message_text(
            chat_id=m["chat_id"],
            message_id=m["msg_id"],
            text=(
                f"🔥 MATCH FINITO\n\n"
                f"P1: {m['p1_score']}\n"
                f"P2: {m['p2_score']}\n\n"
                f"{result}"
            )
        )

    del active_matches[mid]


async def run_match(bot, mid, chat_id, msg_id):
    m = active_matches[mid]
    m["chat_id"] = chat_id
    m["msg_id"] = msg_id

    for i in range(5):
        if mid not in active_matches:
            return

        r1, r2 = calc_round(m)

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=(
                f"⚡ PvP LIVE ROUND {m['round']}/5\n\n"
                f"P1 +{r1} → {m['p1_score']}\n"
                f"P2 +{r2} → {m['p2_score']}"
            )
        )

        await asyncio.sleep(2)

    await finish_match(bot, mid)


# =========================
# PvP JOIN
# =========================

async def pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if uid in pvp_queue:
        return await q.message.reply_text("⏳ Sei già in coda")

    pvp_queue.append(uid)

    if len(pvp_queue) < 2:
        return await q.message.reply_text("🆚 In attesa avversario...")

    p1 = pvp_queue.pop(0)
    p2 = pvp_queue.pop(0)

    mid = create_match(p1, p2)

    msg = await q.message.reply_text("🔥 MATCH INIZIATO...")

    asyncio.create_task(run_match(context.bot, mid, msg.chat_id, msg.message_id))


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

    await q.message.reply_text(f"🎲 Numero: {n}\n💰 +{win}", reply_markup=menu())


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

    await q.message.reply_text(
        f"🃏 Blackjack\n{g['p']} ({calc(g['p'])})",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Carta", callback_data="hit"),
             InlineKeyboardButton("🛑 Stai", callback_data="stand")]
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
        return await q.message.reply_text("💥 Sballato!")

    await q.message.reply_text(f"🃏 {g['p']} ({calc(g['p'])})")


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

    await q.message.reply_text(f"🃏 Tu {p} vs Dealer {d}\n💰 +{win}", reply_markup=menu())


# =========================
# BONUS
# =========================

async def bonus(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    now = int(time.time())

    if now - u["last_bonus"] < 86400:
        return await q.message.reply_text("⏳ Bonus già preso")

    reward = random.randint(500, 1500)

    u["chips"] += reward
    u["last_bonus"] = now

    save(u)

    await q.message.reply_text(f"🎁 +{reward}", reply_markup=menu())


# =========================
# SHOP
# =========================

async def shop(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text(
        "💰 SHOP\n\n"
        "1) x2 → 5000 chips\n"
        "2) x3 → 12000 chips\n"
        "Usa /buy 1 o /buy 2"
    )


async def buy(update, context):
    u = get_user(update.effective_user.id)

    try:
        opt = int(context.args[0])
    except:
        return await update.message.reply_text("Uso: /buy 1 o /buy 2")

    if opt == 1 and u["chips"] >= 5000:
        u["chips"] -= 5000
        u["multiplier"] = 2.0
    elif opt == 2 and u["chips"] >= 12000:
        u["chips"] -= 12000
        u["multiplier"] = 3.0
    else:
        return await update.message.reply_text("❌ Non disponibile")

    save(u)
    await update.message.reply_text("✅ Acquisto fatto")


# =========================
# PROFILO + CLASSIFICA
# =========================

async def profilo(update, context):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)

    await q.message.reply_text(
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

    await q.message.reply_text(txt, reply_markup=menu())


# =========================
# ROUTER
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data

    if d == "slot":
        return await slot(update, context)
    if d == "roulette":
        return await roulette(update, context)
    if d == "blackjack":
        return await blackjack(update, context)
    if d == "hit":
        return await hit(update, context)
    if d == "stand":
        return await stand(update, context)
    if d == "bonus":
        return await bonus(update, context)
    if d == "shop":
        return await shop(update, context)
    if d == "profilo":
        return await profilo(update, context)
    if d == "classifica":
        return await classifica(update, context)
    if d == "pvp":
        return await pvp(update, context)

    await q.message.reply_text("🚧 In sviluppo")


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("fileid", fileid))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO PRO SERVER FINAL ONLINE")
    app.run_polling()


if __name__ == "__main__":
    main()
