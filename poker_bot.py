
import os 
import random
import sqlite3
import time
import threading
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

print("🟢 CASINO PRO MAX ONLINE")

# =========================
# GRUPPI AUTORIZZATI
# =========================

GRUPPI_AUTORIZZATI = [
    -1003664350829,
    -1002229066951
]

def autorizzato(update):
    chat = None

    if update.effective_chat:
        chat = update.effective_chat
    elif update.callback_query:
        chat = update.callback_query.message.chat

    if not chat:
        return False

    if chat.type == "private":
        return True

    return chat.id in GRUPPI_AUTORIZZATI
    
is_allowed = autorizzato
# =========================
# DATABASE
# =========================

conn = sqlite3.connect("casino.db", check_same_thread=False)
cursor = conn.cursor()
lock = threading.Lock()

# =========================
# CREAZIONE TABELLA UTENTI
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    chips INTEGER,
    wins INTEGER,
    losses INTEGER,
    last_bonus INTEGER,
    xp INTEGER,
    streak INTEGER,
    last_daily INTEGER
)
""")

conn.commit()

# =========================
# STATO GIOCHI
# =========================

blackjack_data = {}

# Tavoli Blackjack PvP
pvp_tables = {}

jackpot = 0

# =========================
# TIMER TURNI PVP
# =========================

import asyncio

async def turn_timer(tid, context):
    await asyncio.sleep(20)

    t = pvp_tables.get(tid)
    if not t or not t["started"]:
        return

    current = t["players"][t["turn"]]
    hand = t["hands"][current]
    score = calcola_mano(hand)

    await context.bot.send_message(
        chat_id=current,
        text=f"⏱️ Tempo scaduto! Auto-stand.\n🃏 Mano: {hand} = {score}"
    )

    t["turn"] += 1
    await send_turn_global(context, tid)



# =========================
# FUNZIONI UTILI
# =========================

def carta():
    return random.choice([
        2, 3, 4, 5, 6, 7, 8, 9,
        10, 10, 10, 10, 11
    ])

def calc(mano):
    totale = sum(mano)
    assi = mano.count(11)

    while totale > 21 and assi:
        totale -= 10
        assi -= 1

    return totale

# =========================
# SISTEMA UTENTE
# =========================

def get_user(uid, name="Player"):
    uid = str(uid)

    with lock:
        cursor.execute(
            "SELECT * FROM users WHERE user_id=?",
            (uid,)
        )

        r = cursor.fetchone()

        if not r:

            cursor.execute("""
            INSERT INTO users (
                user_id,
                name,
                chips,
                wins,
                losses,
                last_bonus,
                xp,
                streak,
                last_daily
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                name,
                5000,
                0,
                0,
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
                "last_bonus": 0,
                "xp": 0,
                "streak": 0,
                "last_daily": 0
            }

        return {
            "user_id": r[0],
            "name": r[1],
            "chips": r[2],
            "wins": r[3],
            "losses": r[4],
            "last_bonus": r[5],
            "xp": r[6],
            "streak": r[7],
            "last_daily": r[8]
        }

def update_user(u):
    with lock:

        cursor.execute("""
        UPDATE users SET
            name=?,
            chips=?,
            wins=?,
            losses=?,
            last_bonus=?,
            xp=?,
            streak=?,
            last_daily=?
        WHERE user_id=?
        """, (
            u["name"],
            u["chips"],
            u["wins"],
            u["losses"],
            u["last_bonus"],
            u["xp"],
            u["streak"],
            u["last_daily"],
            u["user_id"]
        ))

        conn.commit()

# =========================
# SISTEMA XP
# =========================

def add_xp(u, amount):
    u["xp"] += amount
    update_user(u)

# =========================
# SISTEMA RANK
# =========================

def get_rank(xp):

    if xp >= 5000:
        return "👑 LEGGENDA"

    if xp >= 2500:
        return "💎 PROFESSIONISTA"

    if xp >= 1000:
        return "⭐ ESPERTO"

    if xp >= 300:
        return "🎲 GIOCATORE"

    return "🪙 PRINCIPIANTE"
    
# =========================
# MENU
# =========================

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Slot", callback_data="slot"),
         InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],

        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack"),
         InlineKeyboardButton("🃏 PvP Blackjack", callback_data="pvp_create")],

        [InlineKeyboardButton("🎡 Ruota della fortuna", callback_data="ruota"),
         InlineKeyboardButton("🎁 Bonus giornaliero", callback_data="bonus")],

        [InlineKeyboardButton("👤 Profilo", callback_data="profilo"),
         InlineKeyboardButton("💰 Saldo", callback_data="saldo")],

        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ])

# =========================
# START
# =========================
async def start(update, context):

    print("CHAT ID =", update.effective_chat.id)

    if not is_allowed(update):
        if update.message:
            await update.message.reply_text(
                f"❌ Gruppo non autorizzato.\nID gruppo: {update.effective_chat.id}"
            )
        return

    get_user(
        update.effective_user.id,
        update.effective_user.first_name
    )

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
# PVP BLACKJACK PRO FIXED
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
        "turn": 0,

        "last_action": time.time(),
        "turn_timeout": 20,
        "afk": {}
    }

    await q.message.reply_text(
        f"🃏 TAVOLO {table_id}\n💰 Ingresso: 1000",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Entra (1000)", callback_data=f"pvp_join_{table_id}")],
            [InlineKeyboardButton("🚀 Avvia partita", callback_data=f"pvp_start_{table_id}")]
        ])
    )


# =========================
# JOIN
# =========================

async def pvp_join(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables.get(tid)
    if not t or t["started"]:
        return await q.answer("❌ Tavolo non disponibile", show_alert=True)

    u = get_user(uid)

    if u["chips"] < 1000:
        return await q.answer("❌ Chips insufficienti", show_alert=True)

    if uid in t["players"]:
        return await q.answer("⚠️ Sei già nel tavolo", show_alert=True)

    u["chips"] -= 1000
    update_user(u)

    t["players"].append(uid)
    t["chips"][uid] = 1000
    t["pot"] += 1000

    await q.answer("🎮 Sei entrato nella partita!")

    await q.message.reply_text(
        f"🃏 NUOVO GIOCATORE\n🎯 Tavolo: {tid}\n👥 Players: {len(t['players'])}\n💰 Pot: {t['pot']}"
    )


# =========================
# START
# =========================

async def pvp_start(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables.get(tid)
    if not t or t["owner"] != uid:
        return await q.answer("❌ Non autorizzato", show_alert=True)

    if len(t["players"]) < 2:
        return await q.answer("❌ Minimo 2 giocatori", show_alert=True)

    t["started"] = True
    t["turn"] = 0
    t["last_action"] = time.time()

    for p in t["players"]:
        t["hands"][p] = [carta(), carta()]

    await send_turn(context, tid)


# =========================
# SEND TURN (FIXED)
# =========================

async def send_turn(context, tid):
    t = pvp_tables.get(tid)
    if not t:
        return

    while t["turn"] < len(t["players"]):
        p = t["players"][t["turn"]]
        hand = t["hands"].get(p, [])
        score = calcola_mano(hand)

        if score > 21:
            t["turn"] += 1
            continue

        t["last_action"] = time.time()

        await context.bot.send_message(
            chat_id=p,
            text=f"""
🎯 TURNO
🃏 Mano: {hand} = {score}
💰 Pot: {t['pot']}

⏱️ 20 secondi
""",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎯 HIT", callback_data=f"pvp_hit_{tid}"),
                    InlineKeyboardButton("🛑 STAND", callback_data=f"pvp_stand_{tid}")
                ]
            ])
        )

        asyncio.create_task(turn_timer(context, tid))
        return

    await finish(context, tid)


# =========================
# HIT
# =========================

async def pvp_hit(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables.get(tid)
    if not t:
        return

    if t["players"][t["turn"]] != uid:
        return await q.answer("❌ Non è il tuo turno", show_alert=True)

    t["last_action"] = time.time()

    t["hands"][uid].append(carta())
    score = calcola_mano(t["hands"][uid])

    await q.answer(f"🎯 {score}")

    if score > 21:
        await q.message.reply_text(f"💥 Sballato ({score})")
        t["turn"] += 1
        await send_turn(context, tid)
    else:
        await q.message.reply_text(f"🃏 Mano: {t['hands'][uid]} = {score}")


# =========================
# STAND
# =========================

async def pvp_stand(update, context):
    q = update.callback_query
    uid = str(q.from_user.id)
    tid = q.data.split("_")[-1]

    t = pvp_tables.get(tid)
    if not t:
        return

    if t["players"][t["turn"]] != uid:
        return await q.answer("❌ Non è il tuo turno", show_alert=True)

    t["last_action"] = time.time()

    await q.answer("🛑 Turno passato")

    t["turn"] += 1
    await send_turn(context, tid)


# =========================
# TIMER AFK
# =========================

async def turn_timer(context, tid):
    await asyncio.sleep(20)

    t = pvp_tables.get(tid)
    if not t or not t["started"]:
        return

    if time.time() - t["last_action"] < 20:
        return

    current = t["players"][t["turn"]]
    hand = t["hands"][current]
    score = calcola_mano(hand)

    await context.bot.send_message(
        chat_id=current,
        text=f"⏱️ AFK → AUTO STAND\n🃏 {hand} = {score}"
    )

    t["turn"] += 1
    await send_turn(context, tid)


# =========================
# FINISH
# =========================

async def finish(context, tid):
    t = pvp_tables.get(tid)
    if not t:
        return

    scores = [(p, calcola_mano(t["hands"][p])) for p in t["players"]]
    scores.sort(key=lambda x: x[1], reverse=True)

    best = scores[0][1]
    winners = [p for p, s in scores if s == best and s <= 21]

    payout = t["pot"] // len(winners) if winners else 0

    text = "🏆 RISULTATO PVP\n\n"

    for p, s in scores:
        text += f"{p} → {s}\n"

    text += f"\n💰 Winners: {winners}\n💸 +{payout}"

    for w in winners:
        u = get_user(w)
        u["chips"] += payout
        update_user(u)

    del pvp_tables[tid]

    await context.bot.send_message(
        chat_id=winners[0] if winners else t["owner"],
        text=text
    )
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

    if now - u["last_daily"] < 86400:
        return await q.message.reply_text("⏳ Hai già preso il bonus oggi")

    # streak system
    if now - u["last_daily"] < 172800:
        u["streak"] += 1
    else:
        u["streak"] = 1

    base = random.randint(500, 2000)
    reward = base + (u["streak"] * 100)

    u["chips"] += reward
    u["last_daily"] = now
    u["xp"] += 50

    update_user(u)

    await q.message.reply_text(
        f"🎁 BONUS PRO MAX\n+{reward}\n🔥 Streak: {u['streak']}",
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

    total = u["wins"] + u["losses"]
    winrate = round((u["wins"] / total) * 100, 2) if total else 0

    rank = get_rank(u["xp"])

    badges = []

    if u["chips"] > 20000:
        badges.append("💎 VIP")
    if winrate > 60:
        badges.append("🔥 LUCKY")
    if u["wins"] > u["losses"]:
        badges.append("🏆 WINNER")
    if u["streak"] >= 5:
        badges.append("⚡ HOT STREAK")
    if u["xp"] > 1000:
        badges.append("🎮 GRINDER")

    if not badges:
        badges.append("🆕 NEW")

    await q.message.reply_text(f"""
╔══════════════════╗
║   👤 LA TUA CLASSIFICA   ║
╚══════════════════╝

🧑 {u['name']}
💰 Chips: {u['chips']}
🏆 Rank: {rank}

📊 Stats:
✔️ Wins: {u['wins']}
❌ Losses: {u['losses']}
🎮 Winrate: {winrate}%

⭐ XP: {u['xp']}
🔥 Streak: {u['streak']}

🏅 Badge:
{" | ".join(badges)}
""", reply_markup=menu())

async def classifica(update, context):
    q = update.callback_query

    cursor.execute("SELECT name, chips, xp FROM users ORDER BY chips DESC LIMIT 10")
    top = cursor.fetchall()

    text = "🏆 TOP CLASSIFICA GENERALE\n\n"

    for i, (name, chips, xp) in enumerate(top, 1):
        text += f"{i}. {name}\n💰 {chips} | ⭐ {xp}\n\n"

    await q.message.reply_text(text, reply_markup=menu())

#==========================
# CALLBACK
#========================


async def cb(update, context):
    q = update.callback_query

    print(
        "CALLBACK:",
        q.from_user.id,
        "CHAT:",
        q.message.chat.id,
        "TIPO:",
        q.message.chat.type
    )

    if not is_allowed(update):
        await q.answer(
            f"NON AUTORIZZATO\nCHAT={q.message.chat.id}",
            show_alert=True
        )
        return

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
