import os   
import random
import sqlite3
import time
import threading
import asyncio
import logging
from collections import deque

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ( 
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    MessageHandler, 
    filters
)


from telegram.error import BadRequest

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

games = {}
pvp_queue = deque()
active_matches = {}
tables = {}
user_tables = {}
COOLDOWN = {}


# =========================
# SAFE EDIT (FIXATO SOLO QUI)  *****
# =========================
async def safe_edit(msg, text, reply_markup=None, parse_mode=None):
    try:
        if msg.content_type == "photo" or hasattr(msg, "caption"):
            return await msg.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

        return await msg.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )

    except Exception as e:
        logger.error(f"safe_edit failed: {e}")
        return False
# =========================
# DATABASE (OBBLIGATORIO PRIMO)   ****
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


#=========================
#  TOKEN CONFIG  ******
#=========================
TOKEN = os.getenv("CASINO_TOKEN")

if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")


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




# =========================
# SAFE EDIT
# =========================
async def safe_edit(msg, text, reply_markup=None, parse_mode=None):
    try:
        return await msg.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return False

        try:
            return await msg.edit_text(
                text=text + "\u200b",
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e2:
            logger.error(f"safe_edit failed: {e2}")
            return False
# =========================
# USER SYSTEM ******
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
# MENU               ******
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
# START               *************
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.first_name)

    print("START ARRIVATO:", user.id)

    photo_id = "AgACAgQAAxkBAAMuai-rfso9kJ2iwjIUkpuI6bbceWEAAlcOaxsMTIBR2F1G_QHjrzcBAAMCAAN5AAM8BA"

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
# 🎰 SLOT CONFIG
# =========================
SYMBOLS = ["🍒", "🍋", "🔔", "💎", "7️⃣", "🍀", "⭐"]

PAYOUT = {
    "jackpot": 15000,
    "triple": 5000,
    "double": 1200
}

VIP_MULT = [1, 1, 1, 1.2, 1.5, 2]

COOLDOWN = {}

# =========================
# 🎰 SLOT SYMBOLS
# =========================

def weighted_symbol():
    table = [
        ("🍒", 30),
        ("🍋", 25),
        ("🍀", 20),
        ("🔔", 12),
        ("⭐", 8),
        ("💎", 4),
        ("7️⃣", 1),
    ]

    total = sum(w for _, w in table)
    r = random.randint(1, total)

    upto = 0
    for sym, w in table:
        upto += w
        if r <= upto:
            return sym

    return "🍒"


# =========================
# 🎰 SLOT GOD MODE (FIXED)
# =========================
async def slot(update, context):

    # ✅ FIX: supporta sia /slot che callback
    q = update.callback_query

    if q:
        try:
            await q.answer()
        except:
            pass

        uid = q.from_user.id
        send_target = q.message

    else:
        uid = update.effective_user.id
        send_target = update.message

    now = time.time()

    # 🛡️ anti spam
    if uid in COOLDOWN and now - COOLDOWN[uid] < 3:
        return
    COOLDOWN[uid] = now

    u = get_user(uid)

    reels = ["🎰", "🎰", "🎰"]

    # =========================
    # 🎬 MESSAGGIO INIZIALE
    # =========================
    msg = await send_target.reply_animation(
        animation="BAACAgQAAxkBAANCajJYH3Jfdd7S1sx5SVA2snDBo-kAAuwmAAKGHZhRonuMrpmMdyg8BA",
        caption="🎰 SLOT IN CORSO...\n\n┃ 🎰 | 🎰 | 🎰 ┃"
    )

    # =========================
    # 🎡 ANIMAZIONE VELOCE
    # =========================
    try:
        steps = 10

        for i in range(steps):

            delay = 0.10 + (i * 0.03)

            if i < 4:
                reels[0] = weighted_symbol()
            elif i < 7:
                reels[1] = weighted_symbol()
            else:
                reels[2] = weighted_symbol()

            await msg.edit_caption(
                caption=f"🎰 SPINNING...\n\n┃ {reels[0]} | {reels[1]} | {reels[2]} ┃"
            )

            await asyncio.sleep(delay)

        await asyncio.sleep(0.4)

    except Exception as e:
        print("SLOT ERROR:", e)

    # =========================
    # 🎯 RISULTATO
    # =========================
    vip = random.choice(VIP_MULT)
    jackpot_roll = random.randint(1, 200)

    if jackpot_roll == 1:
        r = ["7️⃣", "7️⃣", "7️⃣"]
        win = PAYOUT["jackpot"]
        status = "🔥 JACKPOT!"

    else:
        r = reels

        if random.randint(1, 100) <= 20:
            r[1] = r[0]

        if r[0] == r[1] == r[2]:
            win = PAYOUT["triple"]
            status = "🟢 HAI VINTO!"
        elif r[0] == r[1] or r[1] == r[2]:
            win = PAYOUT["double"]
            status = "🟡 QUASI!"
        else:
            win = 0
            status = "🔴 HAI PERSO"

    win = int(win * vip * u.get("multiplier", 1.0))

    u["chips"] = u.get("chips", 0) + win
    u["xp"] = u.get("xp", 0) + max(1, win // 15)
    save_user(u)

    # =========================
    # 🎯 OUTPUT FINALE
    # =========================
    final = (
        f"{status}\n\n"
        f"┃ {r[0]} | {r[1]} | {r[2]} ┃\n\n"
        f"💰 +{win} chips\n"
        f"💎 saldo: {u['chips']}"
    )

    await msg.edit_caption(caption=final)
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

        await safe_edit(
            q.message,
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
        import traceback
        traceback.print_exc()

        try:
            await safe_edit(q.message, f"⚠️ Errore:\n{e}")
        except:
            pass


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
# 🎰 ROULETTE PRO DEFINITIVA
# =========================

import asyncio
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# =========================
# 🎰 VARIABILI BASE
# =========================
red_numbers = {
    1,3,5,7,9,12,14,16,18,19,
    21,23,25,27,30,32,34,36
}

# =========================
# 🎰 MENU ROULETTE
# =========================
async def roulette(update, context):
    q = update.callback_query
    await q.answer()

    keyboard = [
        [
            InlineKeyboardButton("🔴 ROSSO", callback_data="bet_red"),
            InlineKeyboardButton("⚫ NERO", callback_data="bet_black")
        ],
        [
            InlineKeyboardButton("🔢 PARI", callback_data="bet_even"),
            InlineKeyboardButton("🔢 DISPARI", callback_data="bet_odd")
        ],
        [
            InlineKeyboardButton("🎯 ZERO", callback_data="bet_zero")
        ],
        [
            InlineKeyboardButton("🎲 NUMERO", callback_data="bet_number")
        ]
    ]

    await q.message.reply_photo(
        photo="AgACAgQAAxkBAAMuai-rfso9kJ2iwjIUkpuI6bbceWEAAlcOaxsMTIBR2F1G_QHjrzcBAAMCAAN5AAM8BA",
        caption="🎰 <b>ROULETTE PRO CASINO</b>\n\nScegli la tua puntata:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# 🎯 BET SEMPLICI (STABILI)
# =========================
async def bet_red(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "red")


async def bet_black(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "black")


async def bet_even(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "even")


async def bet_odd(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "odd")


async def bet_zero(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "zero")

# =========================
# 🎲 NUMERO FLOW (PRO UX)
# =========================
async def bet_number(update, context):
    q = update.callback_query
    await q.answer()

    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(0, 5)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(5, 10)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(10, 15)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(15, 20)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(20, 25)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(25, 30)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(30, 36)],
    ]

    await q.message.reply_text(
        "🎲 Scegli un numero (0-36):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# 🎲 SELEZIONE NUMERO
# =========================
async def select_number(update, context):
    q = update.callback_query
    await q.answer()

    n = int(q.data.split("_")[1])

    context.user_data["bet_number"] = n
    context.user_data["waiting_number"] = False
    context.user_data["stake"] = 100

    keyboard = [
        [InlineKeyboardButton("🎡 GIRA ROULETTE", callback_data="bet_number_value")]
    ]

    await q.message.reply_text(
        f"🎯 Numero scelto: {n}\n💰 Puntata base: 100",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# 🎡 SPIN ROULETTE
# =========================
async def roulette_spin(update, context, bet):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)
    stake = context.user_data.get("stake", 100)

    if u["chips"] < stake:
        return await q.message.reply_text("❌ Chips insufficienti")

    u["chips"] -= stake

    # 🎡 animazione
    await context.bot.send_animation(
        chat_id=q.message.chat_id,
        animation="BAACAgQAAxkBAAMyai-t7QABk6-viJWJJNrPpu1h8B4-AAJxGwACDEyAUQ9qmdWU-FGYPAQ",
        caption="🎡 LA ROULETTE STA GIRANDO..."
    )

    await asyncio.sleep(3)

    n = random.randint(0, 36)

    win = 0
    victory = False

    if bet == "red":
        victory = n in red_numbers
        win = stake * 2 if victory else 0

    elif bet == "black":
        victory = n != 0 and n not in red_numbers
        win = stake * 2 if victory else 0

    elif bet == "even":
        victory = n != 0 and n % 2 == 0
        win = stake * 2 if victory else 0

    elif bet == "odd":
        victory = n % 2 == 1
        win = stake * 2 if victory else 0

    elif bet == "zero":
        victory = n == 0
        win = stake * 35 if victory else 0

    elif bet == "number":
        chosen = context.user_data.get("bet_number")
        victory = (n == chosen)
        win = stake * 35 if victory else 0

    u["chips"] += win
    u["xp"] = u.get("xp", 0) + max(1, win // 20)
    save_user(u)

    color = "🟢 ZERO" if n == 0 else ("🔴 ROSSO" if n in red_numbers else "⚫ NERO")

    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text=(
            "╔════════════╗\n"
            f"{'🎉 VITTORIA' if victory else '💀 PERSO'}\n"
            "╚════════════╝\n\n"
            f"🎯 Numero: {n} - {color}\n"
            f"💰 +{win}\n"
            f"🏦 SALDO: {u['chips']}"
        ),
        reply_markup=menu()
    )

# =========================
# 🎰 ROULETTE PRO DEFINITIVA FIXED
# =========================

import asyncio
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# =========================
# 🎰 COLORI ROSSI
# =========================
red_numbers = {
    1,3,5,7,9,12,14,16,18,19,
    21,23,25,27,30,32,34,36
}

# =========================
# 🎰 MENU ROULETTE
# =========================
async def roulette(update, context):
    q = update.callback_query
    await q.answer()

    keyboard = [
        [
            InlineKeyboardButton("🔴 ROSSO", callback_data="bet_red"),
            InlineKeyboardButton("⚫ NERO", callback_data="bet_black")
        ],
        [
            InlineKeyboardButton("🔢 PARI", callback_data="bet_even"),
            InlineKeyboardButton("🔢 DISPARI", callback_data="bet_odd")
        ],
        [
            InlineKeyboardButton("🎯 ZERO", callback_data="bet_zero")
        ],
        [
            InlineKeyboardButton("🎲 NUMERO (0-36)", callback_data="bet_number")
        ]
    ]

    await q.message.reply_photo(
        photo="AgACAgQAAxkBAAMuai-rfso9kJ2iwjIUkpuI6bbceWEAAlcOaxsMTIBR2F1G_QHjrzcBAAMCAAN5AAM8BA",
        caption="🎰 <b>ROULETTE PRO CASINO</b>\n\nScegli la puntata:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# 🎯 BET SEMPLICI (100 FIX)
# =========================
async def bet_red(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "red")


async def bet_black(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "black")


async def bet_even(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "even")


async def bet_odd(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "odd")


async def bet_zero(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data["stake"] = 100
    return await roulette_spin(update, context, "zero")


# =========================
# 🎲 SELEZIONE NUMERO (STEP 1)
# =========================
async def bet_number(update, context):
    q = update.callback_query
    await q.answer()

    keyboard = []
    row = []

    for i in range(37):
        row.append(InlineKeyboardButton(str(i), callback_data=f"num_{i}"))
        if len(row) == 6:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    await q.message.reply_text(
        "🎲 Scegli un numero da 0 a 36:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# 🎲 NUMERO SELEZIONATO (STEP 2)
# =========================
async def select_number(update, context):
    q = update.callback_query
    await q.answer()

    n = int(q.data.split("_")[1])

    context.user_data["bet_number"] = n
    context.user_data["stake"] = 100

    keyboard = [
        [InlineKeyboardButton("🎡 GIRA ROULETTE", callback_data="bet_number_value")]
    ]

    await q.message.reply_text(
        f"🎯 Numero scelto: {n}\n💰 Puntata base: 100",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# 🎡 SPIN ROULETTE (CORE FIXED)
# =========================
async def roulette_spin(update, context, bet):
    q = update.callback_query
    await q.answer()

    u = get_user(q.from_user.id)
    stake = context.user_data.get("stake", 100)

    if u["chips"] < stake:
        return await q.message.reply_text("❌ Chips insufficienti")

    u["chips"] -= stake

    # 🎡 animazione
    await context.bot.send_animation(
        chat_id=q.message.chat_id,
        animation="BAACAgQAAxkBAAMyai-t7QABk6-viJWJJNrPpu1h8B4-AAJxGwACDEyAUQ9qmdWU-FGYPAQ",
        caption="🎡 ROULETTE GIRANDO..."
    )

    await asyncio.sleep(3)

    n = random.randint(0, 36)

    win = 0
    victory = False

    if bet == "red":
        victory = n in red_numbers
        win = stake * 2 if victory else 0

    elif bet == "black":
        victory = n != 0 and n not in red_numbers
        win = stake * 2 if victory else 0

    elif bet == "even":
        victory = n != 0 and n % 2 == 0
        win = stake * 2 if victory else 0

    elif bet == "odd":
        victory = n % 2 == 1
        win = stake * 2 if victory else 0

    elif bet == "zero":
        victory = n == 0
        win = stake * 35 if victory else 0

    elif bet == "number":
        chosen = context.user_data.get("bet_number")
        victory = (n == chosen)
        win = stake * 35 if victory else 0

    u["chips"] += win
    u["xp"] = u.get("xp", 0) + max(1, win // 20)
    save_user(u)

    color = "🟢 ZERO" if n == 0 else ("🔴 ROSSO" if n in red_numbers else "⚫ NERO")

    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text=(
            "╔════════════╗\n"
            f"{'🎉 VITTORIA' if victory else '💀 PERSO'}\n"
            "╚════════════╝\n\n"
            f"🎯 Numero: {n} - {color}\n"
            f"💰 +{win}\n"
            f"🏦 SALDO: {u['chips']}"
        ),
        reply_markup=menu()
    )


# =====================
# 🎛️ CALLBACK ROUTER UNICO
# =====================
async def cb_router(update, context):
    q = update.callback_query
    data = q.data

    try:
        await q.answer()
    except:
        pass

    # =====================
    # 🎰 MENU
    # =====================
    if data == "slot":
        return await slot(update, context)

    if data == "roulette":
        return await roulette(update, context)

    if data == "shop":
        return await shop(update, context)

    if data == "profilo":
        return await profilo(update, context)

    if data == "classifica":
        return await classifica(update, context)

    if data == "pvp":
        return await pvp(update, context)

    # =====================
    # 🎲 ROULETTE
    # =====================
    if data == "bet_red":
        return await bet_red(update, context)

    if data == "bet_black":
        return await bet_black(update, context)

    if data == "bet_even":
        return await bet_even(update, context)

    if data == "bet_odd":
        return await bet_odd(update, context)

    if data == "bet_zero":
        return await bet_zero(update, context)

    if data.startswith("bet_"):
        return await bet_number(update, context)

# =====================
# 🃏 BLACKJACK
# =====================
    if data == "blackjack":
        return await blackjack(update, context)

    if data == "hit":
        return await hit(update, context)

    if data == "stand":
        return await stand(update, context)

# =====================
# 🎮 PVP
# =====================
    if data == "pvp":
        return await pvp(update, context)

    if data == "hit_mp":
        return await hit_mp(update, context)

    if data == "stand_mp":
        return await stand_mp(update, context)

# =====================
# 🎁 EXTRA
# =====================
    if data == "bonus":
        return await bonus(update, context)

    if data == "profilo":
        return await profilo(update, context)

    if data == "classifica":
        return await classifica(update, context)

    if data == "shop":
        return await shop(update, context)

    if data == "noop":
        return

# =====================
# ❌ FALLBACK
# =====================
    print("❌ CALLBACK NON GESTITA:", data)

    try:
        await q.message.reply_text(f"🚧 Callback non gestita:\n\n{data}")
    except:
        pass
BONUS_LOCK = {}

# =========================
# 🎁 BONUS
# =========================
async def bonus(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    now = time.time()

    # 🔥 anti doppio click
    last = BONUS_LOCK.get(uid, 0)
    if now - last < 2:
        return

    BONUS_LOCK[uid] = now

    u = get_user(uid)

    # 24h cooldown
    if u["last_bonus"] and now - u["last_bonus"] < 86400:
        return await q.message.reply_text("❌ Hai già ricevuto il bonus oggi.")

    u["chips"] += 500
    u["last_bonus"] = now

    save_user(u)

    await q.message.reply_text("🎁 BONUS GIORNALIERO\n\n💰 +500 chips!")

# =========================
# 👤 PROFILO
# =========================
async def profilo(update, context):
    q = update.callback_query
    u = get_user(q.from_user.id)

    await safe_edit(
        q.message,
        f"👤 PROFILO\n\n"
        f"💰 Chips: {u['chips']}\n"
        f"⭐ XP: {u['xp']}",
        reply_markup=menu()
    )


# =========================
# 🏆 CLASSIFICA
# =========================
async def classifica(update, context):
    q = update.callback_query

    await safe_edit(
        q.message,
        "🏆 CLASSIFICA\n\n🚧 In arrivo...",
        reply_markup=menu()
    )


# =========================
# 🛒 SHOP
# =========================
async def shop(update, context):
    q = update.callback_query

    await safe_edit(
        q.message,
        "🛒 SHOP\n\n🚧 In arrivo...",
        reply_markup=menu()
    )


async def text_handler(update, context):
    message = update.message.text.lower()

    # esempio base (puoi espanderlo)
    if "ciao" in message:
        return await update.message.reply_text("👋 Ciao!")

    return

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
        return await update.message.reply_text(msg.photo[-1].file_id)

    if msg.animation:
        return await update.message.reply_text(msg.animation.file_id)

    if msg.video:
        return await update.message.reply_text(msg.video.file_id)

    if msg.document:
        return await update.message.reply_text(msg.document.file_id)

    await update.message.reply_text("❌ File non supportato")


# =========================
# CALLBACK ROUTER (ROULETTE FIX)
# =========================
async def cb_router(update, context):
    q = update.callback_query
    data = q.data

    try:
        await q.answer()
    except:
        pass

    # 🎰 MENU
    if data == "slot":
        return await slot(update, context)

    if data == "spin_slot":
        return await spin_slot(update, context)

    if data == "roulette":
        return await roulette(update, context)

    if data == "pvp":
        return await pvp(update, context)

    # 🎲 NUMERI (PRIMA DI bet_)
    if data.startswith("num_"):
        return await select_number(update, context)

    # 🎲 BETS ROULETTE
    if data == "bet_red":
        return await bet_red(update, context)

    if data == "bet_black":
        return await bet_black(update, context)

    if data == "bet_even":
        return await bet_even(update, context)

    if data == "bet_odd":
        return await bet_odd(update, context)

    if data == "bet_zero":
        return await bet_zero(update, context)

    if data == "bet_number_value":
        return await roulette_spin(update, context, "number")

    if data == "bet_number":
        return await bet_number(update, context)

    print("❌ CALLBACK NON GESTITA:", data)

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # COMMANDS
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fileid", fileid))

    # CALLBACK ROUTER
    app.add_handler(CallbackQueryHandler(cb_router))

    # TEXT HANDLER
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🟢 CASINO DEFINITIVO ONLINE")

    app.run_polling(drop_pending_updates=True)


# =========================
# ENTRY POINT (CORRETTO)
# =========================
if __name__ == "__main__":
    main()
