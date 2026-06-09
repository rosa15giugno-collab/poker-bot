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

print("🟢 CASINO WHITELIST FINAL ONLINE")

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

    if chat.type == "private":
        return True

    return chat.id in ALLOWED_GROUPS

# =========================
# DATABASE
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
# GAME STATE
# =========================

blackjack_data = {}
pvt_tables = {}
jackpot = 0

#========================
#UTILS
#========================
def carta():
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

def calc(hand):
    s = sum(hand)
    aces = hand.count(11)
    while s > 21 and aces:
        s -= 10
        aces -= 1
    return s

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = cursor.fetchone()

        if not r:
            cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                           (uid, name, 5000, 0, 0, 0))
            conn.commit()
            return {"user_id": uid, "name": name, "chips": 5000, "wins": 0, "losses": 0, "last_bonus": 0}

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
        UPDATE users SET name=?, chips=?, wins=?, losses=?, last_bonus=? WHERE user_id=?
        """, (u["name"], u["chips"], u["wins"], u["losses"], u["last_bonus"], u["user_id"]))
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
            INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, name, 5000, 0, 0, 0))
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
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("🃏 PvP Blackjack", callback_data="pvp_create")],

        [InlineKeyboardButton("🎡 Ruota", callback_data="ruota"),
         InlineKeyboardButton("🎁 Bonus", callback_data="bonus")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("💰 Saldo", callback_data="saldo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================

async def start(update, context):
    if not is_allowed(update):
        if update.message:
            await update.message.reply_text("❌ Gruppo non autorizzato.")
        return

    get_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "🟢 CASINO ATTIVO\n🎮 Benvenuto!",
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
        return await q.message.reply_text("❌ Chips insufficienti")

    u["chips"] -= bet
    jackpot += 50

    r = [random.choice(["🍒","🍋","🍇","💎","7️⃣"]) for _ in range(3)]

    win = 3000 if r[0]==r[1]==r[2] else 800 if r[0]==r[1] or r[1]==r[2] else 0

    if win > 0:
        u["chips"] += win + jackpot
        jackpot = 0

    u["wins" if win > 0 else "losses"] += 1
    update_user(u)

    await q.message.reply_text(
    f"""
╔══════════════╗
║        🎰 SLOT 🎰           ║
╚══════════════╝

┏━━━━━━━━━━━━━┓
┃     {r[0]} │ {r[1]} │ {r[2]}         ┃
┗━━━━━━━━━━━━━┛

💰 Vincita: {win}
🏦 Jackpot: {jackpot}
💳 Saldo: {u['chips']}
""",
    reply_markup=menu()
)

# =========================
# BLACKJACK BOT
# =========================

async def blackjack_start(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    mano = [carta(), carta()]
    dealer = [carta(), carta()]

    blackjack_data[uid] = {"mano": mano, "dealer": dealer}

    await q.message.reply_text(
        f"🃏 MANO: {mano} = {sum(mano)}\n🎩 Dealer: [{dealer[0]}, ?]",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Pesca", callback_data="hit"),
             InlineKeyboardButton("🛑 Stai", callback_data="stand")]
        ])
    )

async def hit(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack_data.get(uid)
    if not g:
        return await q.message.reply_text("❌ Nessuna partita")

    g["mano"].append(carta())
    s = sum(g["mano"])

    if s > 21:
        del blackjack_data[uid]
        return await q.message.reply_text(f"💥 Sballato {s}", reply_markup=menu())

    await q.message.reply_text(f"🎯 {g['mano']} = {s}")

async def stand(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    g = blackjack_data.get(uid)
    if not g:
        return await q.message.reply_text("❌ Nessuna partita")

    p = calc(g["mano"])
    d = g["dealer"]

    while calc(d) < 17:
        d.append(carta())

    ds = calc(d)

    res = "🏆 VINTO" if (ds > 21 or p > ds) else "💀 PERSO" if p < ds else "🤝 PARI"

    del blackjack_data[uid]

    await q.message.reply_text(
        f"🃏 RISULTATO\nTu: {p}\nDealer: {ds}\n\n{res}",
        reply_markup=menu()
    )

# =========================
# PVT BLACKJACK pro
# =========================

async def pvp_create(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)

    table_id = str(random.randint(1000, 9999))

    pvp_tables[table_id] = {
        "owner": uid,
        "players": [uid],
        "hands": {},
        "chips": {},
        "pot": 0,
        "started": False,
        "turn": 0
    }

    await q.message.reply_text(
        f"🃏 TABLE {table_id}\n💰 Buy-in 1000",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("JOIN 1000", callback_data=f"pvp_join_{table_id}")],
            [InlineKeyboardButton("START", callback_data=f"pvp_start_{table_id}")]
        ])
    )

async def pvp_join(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables.get(tid)
    if not t or t["started"]:
        return

    u = get_user(uid)

    if u["chips"] < 1000:
        return await q.message.reply_text("❌ No chips")

    if uid in t["players"]:
        return

    u["chips"] -= 1000
    update_user(u)

    t["players"].append(uid)
    t["chips"][uid] = 1000
    t["pot"] += 1000

    await q.message.reply_text(f"✅ Join {tid} | Pot {t['pot']}")

async def pvp_start(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables.get(tid)
    if not t or t["owner"] != uid:
        return

    if len(t["players"]) < 2:
        return await q.message.reply_text("❌ Min 2 players")

    t["started"] = True

    for p in t["players"]:
        t["hands"][p] = [carta(), carta()]

    await send_turn(q, tid)

async def send_turn(q, tid):
    t = pvp_tables[tid]
    p = t["players"][t["turn"]]

    await q.message.reply_text(
        f"🎯 TURN {p}\n{t['hands'][p]} = {calc(t['hands'][p])}\n💰 {t['pot']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("HIT", callback_data=f"pvp_hit_{tid}"),
             InlineKeyboardButton("STAND", callback_data=f"pvp_stand_{tid}")]
        ])
    )

async def pvp_hit(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables[tid]

    if t["players"][t["turn"]] != uid:
        return

    t["hands"][uid].append(carta())

    if calc(t["hands"][uid]) > 21:
        await next_turn(q, tid)
    else:
        await q.message.reply_text(str(t["hands"][uid]))

async def pvp_stand(update, context):
    q = update.callback_query
    tid = q.data.split("_")[-1]
    await next_turn(q, tid)

async def next_turn(q, tid):
    t = pvp_tables[tid]
    t["turn"] += 1

    if t["turn"] >= len(t["players"]):
        return await finish(q, tid)

    await send_turn(q, tid)

async def finish(q, tid):
    t = pvp_tables[tid]

    scores = [(p, calc(t["hands"][p])) for p in t["players"]]
    scores.sort(key=lambda x: x[1], reverse=True)

    best = scores[0][1]
    winners = [p for p, s in scores if s == best and s <= 21]

    payout = t["pot"] // len(winners) if winners else 0

    text = "🏆 RESULT\n\n"

    for p, s in scores:
        text += f"{p} {s}\n"

    text += f"\nWIN {winners} +{payout}"

    for w in winners:
        u = get_user(w)
        u["chips"] += payout
        update_user(u)

    del pvp_tables[tid]

    await q.message.reply_text(text, reply_markup=menu())

#==========================
# ROULETTE
#==========================

async def roulette(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    numero = random.randint(0, 36)

    win = 1000 if numero == 0 else 300 if numero % 2 == 0 else 0

    u["chips"] += win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    update_user(u)

    await q.message.reply_text(
        f"🎲 Roulette\nNumero uscito: {numero}\n💰 Vincita: {win}",
        reply_markup=menu()
    )


async def ruota(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    premi = [
        ("💀", 0),
        ("🥉", 100),
        ("🥈", 250),
        ("🥇", 500),
        ("💎", 1000),
        ("👑", 2000)
    ]

    simbolo, premio = random.choice(premi)

    u["chips"] += premio

    if premio > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    update_user(u)

    await q.message.reply_text(
        f"""
╔══════════════╗
║  🎡 SUPER RUOTA      ║
╚══════════════╝

      {simbolo}

💰 Premio: {premio}
💳 Saldo: {u['chips']}
""",
        reply_markup=menu()
    )

async def bonus(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    now = int(time.time())

    if now - u["last_bonus"] < 86400:
        ore = (86400 - (now - u["last_bonus"])) // 3600

        return await q.message.reply_text(
            f"⏳ Bonus già ritirato.\nTorna tra circa {ore} ore.",
            reply_markup=menu()
        )

    premio = random.randint(500, 2000)

    u["chips"] += premio
    u["last_bonus"] = now

    update_user(u)

    await q.message.reply_text(
        f"🎁 Bonus giornaliero\n💰 +{premio}",
        reply_markup=menu()
    )


async def saldo(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    await q.message.reply_text(
        f"💰 Saldo: {u['chips']} chips",
        reply_markup=menu()
    )


async def profilo(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    partite = u["wins"] + u["losses"]

    await q.message.reply_text(
    f"""
╔══════════════╗
║    👤 PROFILO 👤         ║
╚══════════════╝

🧑 Nome: {u['name']}
💰 Chips: {u['chips']}
🏆 Vittorie: {u['wins']}
💀 Sconfitte: {u['losses']}
🎮 Partite: {partite}

⭐ Livello: {max(1, partite // 10 + 1)}
""",
    reply_markup=menu()
)


async def classifica(update, context):
    q = update.callback_query

    cursor.execute(
        "SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10"
    )

    top = cursor.fetchall()

    testo = "🏆 CLASSIFICA TOP 10 🏆\n\n"

    medaglie = ["🥇","🥈","🥉"]

    for i, (nome, chips) in enumerate(top, start=1):
        if i <= 3:
            pos = medaglie[i-1]
        else:
            pos = f"{i}️⃣"

        testo += f"{pos} {nome}\n💰 {chips} chips\n\n"

    await q.message.reply_text(
        testo,
        reply_markup=menu()
    )

#==========================
# CALLBACK
#========================


async def cb(update, context):
    q = update.callback_query
    await q.answer()

    d = q.data

    if d == "slot": return await slot(update, context)
    if d == "roulette": return await roulette(update, context)
    if d == "ruota": return await ruota(update, context)
    if d == "bonus": return await bonus(update, context)
    if d == "saldo": return await saldo(update, context)
    if d == "profilo": return await profilo(update, context)
    if d == "classifica": return await classifica(update, context)

    if d == "blackjack": return await blackjack_start(update, context)
    if d == "hit": return await hit(update, context)
    if d == "stand": return await stand(update, context)

    if d == "pvp_create": return await pvp_create(update, context)
    if d.startswith("pvp_join_"): return await pvp_join(update, context)
    if d.startswith("pvp_start_"): return await pvp_start(update, context)
    if d.startswith("pvp_hit_"): return await pvp_hit(update, context)
    if d.startswith("pvp_stand_"): return await pvp_stand(update, context)

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 ONLINE")
    app.run_polling()
if __name__ == "__main__":
    main()
