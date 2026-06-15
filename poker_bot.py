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
# DATABASE (OBBLIGATORIO PRIMO)
# =========================

conn = sqlite3.connect("casino_pro.db", check_same_thread=False)
cursor = conn.cursor()

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

# LOCK (FIXATO)
lock = threading.Lock()

#=======================
# SAVE USER
#======================
def save_user(u):
    with lock:
        cursor.execute("""
        UPDATE users
        SET name=?, chips=?, xp=?, wins=?, losses=?, last_bonus=?, multiplier=?
        WHERE user_id=?
        """, (
            u["name"], u["chips"], u["xp"], u["wins"], u["losses"],
            u["last_bonus"], u["multiplier"], u["user_id"]
        ))
        conn.commit()


# =========================
# STATE
# =========================

games = {}
pvp_queue = deque()
active_matches = {}
tables = {}
user_tables = {}

#=========================
#  TOKEN CONFIG
#=========================
TOKEN = os.getenv("CASINO_TOKEN")

if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")

# =========================
# SAFE EDIT
# =========================
async def safe_edit(msg, text, reply_markup=None):
    try:
        return await msg.edit_text(text, reply_markup=reply_markup)
    except:
        return await msg.edit_caption(text, reply_markup=reply_markup)
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
        "𝑰𝒍 𝒄𝒂𝒔𝒐 𝒏𝒐𝒏 è 𝒄𝒂𝒐𝒔:è 𝒖𝒏 𝒍𝒊𝒏𝒈𝒖𝒂𝒈𝒈𝒊𝒐..\n"
        "   …𝒄𝒉𝒊 𝒔𝒂 𝒂𝒔𝒄𝒐𝒍𝒕𝒂𝒓𝒍𝒐 𝒗𝒊𝒏𝒄𝒆\n\n"
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

    save_user(u)

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
        "players": [],
        "hands": {},
        "started": False,
        "message": None,
        "chat_id": None,

        "dealer": [],

        "pot": 0,
        "finished": False,

        "order": [],
        "turn_index": 0,

        "last_action": time.time(),

        "stood": set()
    }


# =========================
# PVP JOIN
# =========================

async def pvp(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    name = q.from_user.first_name

    bet = 100  # puoi renderla dinamica

    user = get_user(uid)

    # ❌ controllo chips
    if user["chips"] < bet:
        return await q.answer("❌ Non hai abbastanza chips", show_alert=True)

    # 🎯 cerca tavolo disponibile
    table_id = None

    for tid, t in tables.items():
        if not t["started"] and len(t["players"]) < 6:
            table_id = tid
            break

    # 🆕 crea tavolo se non esiste
    if not table_id:
        table_id = str(int(time.time()))
        tables[table_id] = create_table()

    t = tables[table_id]

    # ❌ già dentro al tavolo
    if any(p["id"] == uid for p in t["players"]):
        return await safe_edit(q.message, "⏳ Sei già al tavolo", reply_markup=menu())

    # 💰 scala chips
    user["chips"] -= bet
    save_user(user)

    # 🪑 aggiungi player
    t["players"].append({
        "id": uid,
        "name": name,
        "bet": bet
    })

    # 🖼️ IMMAGINE ENTRATA (effetto casino PvP)
    await context.bot.send_photo(
        chat_id=q.message.chat_id,
        photo="AgACAgQAAxkBAAMkai8flTPIwC3PRtw-ITOGKdLzjBsAAokPaxsMTHhRw0yUgC0hQVYBAAMCAAN5AAM8BA",
        caption=(
            f"🎰 CASINO ROYALE\n"
            f"🃏 PvP Blackjack\n\n"
            f"👤 {name} è entrato nel tavolo\n"
            f"💰 Puntata: {bet} chips"
        )
    )

    # 🃏 carte iniziali
    t["hands"][uid] = [
        random.randint(2, 11),
        random.randint(2, 11)
    ]

    t["pot"] += bet
    user_tables[uid] = table_id

    # 👥 se non ci sono abbastanza player
    if len(t["players"]) < 2:
        return await safe_edit(
            q.message,
            f"🃏 TABLE\n👥 {len(t['players'])}/6\n💰 Pot: {t['pot']}",
            reply_markup=menu()
        )

    # 🚀 avvio partita
    if not t["started"]:
        t["started"] = True

        t["dealer"] = [
            random.randint(2, 11),
            random.randint(2, 11)
        ]

        t["order"] = [p["id"] for p in t["players"]]

        await q.message.edit_text(
            render_table(t),
            reply_markup=table_buttons(t)
        )

        asyncio.create_task(
            game_loop(context.bot, table_id, q.message.chat_id)
        )

# =========================
# RENDER TABLE UI
# =========================

def render_table(t):
    txt = "🃏 <b>BLACKJACK PvP LIVE</b>\n\n"

    current_uid = None

    if t["order"] and t["turn_index"] < len(t["order"]):
        current_uid = t["order"][t["turn_index"]]

    for p in t["players"]:
        uid = p["id"]
        name = p["name"]
        hand = t["hands"].get(uid, [])

        marker = "👉" if uid == current_uid else "👤"

        txt += f"{marker} <b>{name}</b>: {sum(hand)} {hand}\n"

    txt += "\n🏦 <b>BANCO</b>: ? [?, ?]"

    if current_uid:
        current_name = next(
            (p["name"] for p in t["players"] if p["id"] == current_uid),
            "?"
        )

        txt += f"\n\n⏱️ Turno di: <b>{current_name}</b>"

    txt += f"\n💰 Pot: {t['pot']}"

    return txt


#==========================
# UPDATE
#==========================

async def update_table(bot, t):
    if t.get("finished"):
        return

    try:
        await bot.edit_message_text(
            chat_id=t["chat_id"],
            message_id=t["message_id"],
            text=render_table(t),
            reply_markup=table_buttons(t),
            parse_mode="HTML"
        )
    except Exception as e:
        print("UPDATE ERROR:", e)


# =========================
# BUTTONS (IMPORTANTISSIMO)
# =========================

def table_buttons(t):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ HIT", callback_data="hit_mp"),
            InlineKeyboardButton("🛑 STAND", callback_data="stand_mp")
        ]
    ])


# =========================
# HIT MP
# =========================

async def hit_mp(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)

    table_id = user_tables.get(uid)
    t = tables.get(table_id)

    if not t:
        return await q.answer(
            "⚠️ Tavolo non trovato",
            show_alert=True
        )

    if t.get("finished"):
        return await q.answer(
            "⚠️ Partita terminata",
            show_alert=True
        )

    if "order" not in t or "turn_index" not in t:
        return await q.answer(
            "⚠️ Tavolo non inizializzato",
            show_alert=True
        )

    if t["turn_index"] >= len(t["order"]):
        return await q.answer(
            "⏳ Turno non valido",
            show_alert=True
        )

    if t["order"][t["turn_index"]] != uid:
        return await q.answer(
            "⛔ Non è il tuo turno",
            show_alert=True
        )

    # pesca carta
    card = random.randint(2, 11)

    t["hands"].setdefault(uid, []).append(card)

    print(f"HIT_MP -> {uid} pesca {card}")

    score = sum(t["hands"][uid])

    # sballato
    if score > 21:
        print(f"BUST -> {uid}")

        t["turn_index"] += 1

    # aggiorna timer turno
    t["last_action"] = time.time()

    try:
        await update_table(context.bot, t)
    except Exception as e:
        print("❌ UPDATE ERROR HIT_MP:", e)

    return


# =========================
# STAND MP
# =========================

async def stand_mp(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    t = tables.get(user_tables.get(uid))

    if not t:
        return

    if t["order"][t["turn_index"]] != uid:
        return await q.answer("⛔ Non è il tuo turno", show_alert=True)

    t["turn_index"] += 1
    t["last_action"] = time.time()

    await update_table(context.bot, t)

# =========================
# RUN TABLE GAME LOOP
# =========================

async def game_loop(bot, table_id):
    t = tables[table_id]

    while not t["finished"]:
        await asyncio.sleep(2)

        # timeout turno (20 sec)
        if time.time() - t["last_action"] > 20:
            t["turn_index"] += 1
            t["last_action"] = time.time()

        if t["turn_index"] >= len(t["order"]):
            break

    await finish_table(bot, table_id)

# =========================
# FINISH TABLE
# =========================

async def finish_table(bot, table_id):
    t = tables[table_id]

    dealer = t["dealer"]
    while sum(dealer) < 17:
        dealer.append(random.randint(2,11))

    d = sum(dealer)

    txt = "🏁 <b>RISULTATO FINALE</b>\n\n"
    txt += f"🎰 Dealer: {d}\n\n"

    for p in t["players"]:
        uid = p["id"]
        user = get_user(uid)

        score = sum(t["hands"][uid])
        bet = t["bets"][uid]

        if score > 21:
            win = 0
        elif d > 21 or score > d:
            win = bet * 2
        elif score == d:
            win = bet
        else:
            win = 0

        user["chips"] += win
        save_user(user)

        txt += f"👤 {p['name']}: {score} → +{win}\n"

    await bot.send_message(t["chat_id"], txt)

    del tables[table_id]
    
# =========================
# ROULETTE PRO MAX
# =========================

async def roulette(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    # 🎰 TAVOLO ROULETTE
    await context.bot.send_photo(
        chat_id=q.message.chat_id,
        photo="AgACAgQAAxkBAAMuai-rfso9kJ2iwjIUkpuI6bbceWEAAlcOaxsMTIBR2F1G_QHjrzcBAAMCAAN5AAM8BA",
        caption="🎰 ROULETTE CASINO\n\n💰 Puntata registrata\n🎡 Preparazione estrazione..."
    )

    await asyncio.sleep(1)

    # 🎡 ANIMAZIONE SPIN
    await context.bot.send_animation(
        chat_id=q.message.chat_id,
        animation="FILE_ID_SPIN",
        caption="🎡 LA ROULETTE STA GIRANDO..."
    )

    await asyncio.sleep(4)

    # 🎯 ESTRAZIONE
    n = random.randint(0, 36)

    if n == 0:
        win = 1500
        esito = "🟢 JACKPOT ZERO!"
    elif n % 2 == 0:
        win = 300
        esito = "🔴 NUMERO PARI"
    else:
        win = 0
        esito = "⚫ NUMERO DISPARI"

    u["chips"] += win
    u["xp"] += win // 30
    save_user(u)

    # 🎯 RISULTATO FINALE
    risultato = (
        "╔══════════════╗\n"
        "🎰 RISULTATO 🎰\n"
        "╚══════════════╝\n\n"
        f"🎯 NUMERO USCITO\n\n"
        f"⭐ ⭐ {n} ⭐ ⭐\n\n"
        f"{esito}\n\n"
        f"💰 VINCITA: +{win} CHIPS"
    )

    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text=risultato
    )

    await safe_edit(
        q.message,
        f"🎲 Ultimo numero: {n}",
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

    save_user(u)

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

    save_user(u)

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

    save_user(u)

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
        q.message,
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

    data = q.data
    print("🔥 CB:", q.from_user.id, data)

    try:

        # SLOT
        if data == "slot":
            return await slot(update, context)

        # ROULETTE
        elif data == "roulette":
            return await roulette(update, context)

        # BLACKJACK
        elif data == "blackjack":
            return await blackjack(update, context)

        elif data == "hit":
            return await hit(update, context)

        elif data == "stand":
            return await stand(update, context)

        # PVP
        elif data == "pvp":
            return await pvp(update, context)

        elif data == "hit_mp":
            try:
                return await hit_mp(update, context)
            except Exception as e:
                print("❌ HIT_MP ERROR:", e)
                return await safe_edit(q.message, "⚠️ Errore HIT MP", reply_markup=menu())

        elif data == "stand_mp":
            try:
                return await stand_mp(update, context)

            except Exception as e:
                import traceback
                print("❌ STAND_MP ERROR:", e)
                traceback.print_exc()

                return await safe_edit(
                    q.message,
                    "⚠️ Errore STAND MP\n\nControlla log",
                    reply_markup=menu()
                )

        # BONUS
        elif data == "bonus":
            return await bonus(update, context)

        # PROFILO
        elif data == "profilo":
            return await profilo(update, context)

        # CLASSIFICA
        elif data == "classifica":
            return await classifica(update, context)

        # SHOP
        elif data == "shop":
            return await shop(update, context)

        # IGNORA
        elif data == "noop":
            return

        # NON GESTITO
        else:
            print("⚠️ CALLBACK NON GESTITA:", data)

            return await safe_edit(
                q.message,
                f"🚧 In sviluppo\n\nCallback: {data}",
                reply_markup=menu()
            )

    except Exception as e:
        print("❌ CB ERROR:", e)

        import traceback
        traceback.print_exc()

        try:
            return await safe_edit(
                q.message,
                f"⚠️ Errore temporaneo\n\n{e}",
                reply_markup=menu()
            )
        except Exception as e2:
            print("❌ SAFE_EDIT FAILED:", e2)
# =========================
# MAIN
# =========================

async def fileid(update, context):

    msg = update.message.reply_to_message

    if not msg:
        return await update.message.reply_text(
            "📎 Rispondi a una foto, GIF o video con /fileid"
        )

    if msg.photo:
        return await update.message.reply_text(
            msg.photo[-1].file_id
        )

    if msg.animation:
        return await update.message.reply_text(
            msg.animation.file_id
        )

    if msg.video:
        return await update.message.reply_text(
            msg.video.file_id
        )

    if msg.document:
        return await update.message.reply_text(
            msg.document.file_id
        )

    await update.message.reply_text("❌ File non supportato")




def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fileid", fileid))
    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 CASINO DEFINITIVO ONLINE")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
