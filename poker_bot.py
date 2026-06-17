import os
import random
import sqlite3
import time
import threading
import asyncio
import logging
from collections import deque

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from telegram.error import BadRequest

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 SLOT", callback_data="slot")],
        [InlineKeyboardButton("🎲 ROULETTE", callback_data="roulette")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="blackjack")],
        [InlineKeyboardButton("⚔️ PVP", callback_data="pvp")],
        [InlineKeyboardButton("👤 PROFILO", callback_data="profilo")],
        [InlineKeyboardButton("🏆 CLASSIFICA", callback_data="classifica")],
        [InlineKeyboardButton("🛒 SHOP", callback_data="shop")],
        [InlineKeyboardButton("🎁 BONUS", callback_data="bonus")]
    ])


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
# 🃏 BLACKJACK / PVP
# =========================
bj_games = {}
bets = {}


BLACKJACK_BETS = [100, 500, 1000]

CARDS = [
    "A♠️","A♥️","A♦️","A♣️",
    "2♠️","2♥️","2♦️","2♣️",
    "3♠️","3♥️","3♦️","3♣️",
    "4♠️","4♥️","4♦️","4♣️",
    "5♠️","5♥️","5♦️","5♣️",
    "6♠️","6♥️","6♦️","6♣️",
    "7♠️","7♥️","7♦️","7♣️",
    "8♠️","8♥️","8♦️","8♣️",
    "9♠️","9♥️","9♦️","9♣️",
    "10♠️","10♥️","10♦️","10♣️",
    "J♠️","J♥️","J♦️","J♣️",
    "Q♠️","Q♥️","Q♦️","Q♣️",
    "K♠️","K♥️","K♦️","K♣️"
]

#===========================
# CARD BLACK E PVP
#===========================
def card_value(hand):
    total = 0
    aces = 0

    for card in hand:
        value = card[:-1].replace("️", "")

        if value in ["J", "Q", "K"]:
            total += 10
        elif value == "A":
            total += 11
            aces += 1
        else:
            total += int(value) 

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total


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
    
MENU_PHOTO = "AgACAgQAAxkBAANFajK3EgT-sXBmbmi9vwS-ia3oNPYAAp4SaxuGHZhRRK7nT0alIxkBAAMCAAN5AAM8BA"
BLACKJACK_PHOTO = "AgACAgQAAxkBAANIajL7PfXN3cYXM6NliybRfiPCbP0AAk4PaxvsDJlRLQrkmC2DxfsBAAMCAAN5AAM8BA"

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
# 🧠 UTILITY / MENU SYSTEM
# =========================

async def send_main_menu(chat_id, context):
    caption = (
        "🏠 MENU PRINCIPALE\n\n"
        "Scegli un gioco:"
    )

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=MENU_PHOTO,
        caption=caption,
        reply_markup=main_menu_keyboard()
    )




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

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 SLOT", callback_data="slot"),
         InlineKeyboardButton("🎲 ROULETTE", callback_data="roulette")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="blackjack"),
         InlineKeyboardButton("🆚 PVP", callback_data="pvp")],
        [InlineKeyboardButton("🎁 BONUS", callback_data="bonus"),
         InlineKeyboardButton("💰 SHOP", callback_data="shop")],
        [InlineKeyboardButton("👤 PROFILO", callback_data="profilo"),
         InlineKeyboardButton("🏆 CLASSIFICA", callback_data="classifica")]
    ])


# =========================
# START               *************
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.first_name)

    print("START ARRIVATO:", user.id)

    photo_id = "AgACAgQAAxkBAANFajK3EgT-sXBmbmi9vwS-ia3oNPYAAp4SaxuGHZhRRK7nT0alIxkBAAMCAAN5AAM8BA"

    caption = (
        "👑 Benvenuto in CASINO PRO\n\n"
        "𝑰𝒍 𝒄𝒂𝒔𝒐 𝒏𝒐𝒏 è 𝒄𝒂𝒐𝒔: è 𝒖𝒏 𝒍𝒊𝒏𝒈𝒖𝒂𝒈𝒈𝒊𝒐..\n"
        "   …𝒄𝒉𝒊 𝒔𝒂 𝒂𝒔𝒄𝒐𝒍𝒕𝒂𝒓𝒍𝒐 𝒗𝒊𝒏𝒄𝒆\n\n"
        "🎰 Slot | 🎲 Roulette | 🃏 Blackjack | 🆚 PvP\n"
        "🏆 Classifiche live | 🎁 Bonus giornaliero\n\n"
        "👇 Scegli una modalità"
    )

    await update.message.reply_photo(
        photo=photo_id,
        caption=caption,
        reply_markup=main_menu_keyboard()
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
# 🎰 SLOT MENU ENTRATA
# =========================
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import time

async def slot(update, context):

    q = update.callback_query

    if q:
        try:
            await q.answer()
        except:
            pass

        uid = q.from_user.id
        target = q.message
    else:
        uid = update.effective_user.id
        target = update.message

    now = time.time()

    if uid in COOLDOWN and now - COOLDOWN[uid] < 3:
        return
    COOLDOWN[uid] = now

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 SPIN", callback_data="spin_slot")]
    ])

    # 🎬 MESSAGGIO INIZIALE (VERSIONE PRO)
    await target.reply_animation(
        animation="BAACAgQAAxkBAANCajJYH3Jfdd7S1sx5SVA2snDBo-kAAuwmAAKGHZhRonuMrpmMdyg8BA",
        caption=(
            "🎰 SLOT MACHINE\n\n"
            "💰 Premi SPIN per giocare!\n"
            "🔥 Vinci fino a JACKPOT!"
        ),
        reply_markup=keyboard
    )
# =========================
# 🎰 SLOT SPIN ANIMATION (FIXED)
# =========================

async def spin_slot(update, context):

    q = update.callback_query
    await q.answer()

    msg = q.message
    uid = q.from_user.id

    # 🛡️ cooldown
    now = time.time()
    if uid in COOLDOWN and now - COOLDOWN[uid] < 2:
        return
    COOLDOWN[uid] = now

    reels = ["🎰", "🎰", "🎰"]

    # =========================
    # 🎡 ANIMAZIONE STABILE (NO FLOOD)
    # =========================
    try:
        steps = 6
        last_text = ""

        for i in range(steps):

            # 🎯 delay sicuro (Telegram friendly)
            await asyncio.sleep(0.55)

            # 🎰 animazione progressiva
            if i < 2:
                reels[0] = weighted_symbol()
            elif i < 4:
                reels[1] = weighted_symbol()
            else:
                reels[2] = weighted_symbol()

            text = (
                "🎰 SPIN IN CORSO...\n\n"
                f"┃ {reels[0]} | {reels[1]} | {reels[2]} ┃"
            )

            # 🔥 SOLO OGNI 2 STEP → evita flood
            if i % 2 == 0 and text != last_text:
                try:
                    await msg.edit_caption(caption=text)
                    last_text = text
                except:
                    pass

    except Exception as e:
        print("SLOT ERROR:", e)

    # pausa finale stabilità Telegram
    await asyncio.sleep(0.7)

    # =========================
    # 🎯 RISULTATO
    # =========================
    u = get_user(uid)

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
    # 🎯 OUTPUT FINALE + MENU
    # =========================
    final = (
        f"{status}\n\n"
        f"┃ {r[0]} | {r[1]} | {r[2]} ┃\n\n"
        f"💰 +{win} chips\n"
        f"💎 saldo: {u['chips']}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 SPIN DI NUOVO", callback_data="spin_slot")],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    try:
        await msg.edit_caption(
            caption=final,
            reply_markup=keyboard
        )
    except Exception as e:
        print("FINAL EDIT ERROR:", e)


# =========================
# 🃏 BLACKJACK
# =========================
    await q.message.reply_photo(
        photo=PHOTO_BLACKJACK,
        caption=caption,
        reply_markup=keyboard
    )

async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 100", callback_data="bj_bet_100"),
         InlineKeyboardButton("💰 500", callback_data="bj_bet_500")],
        [InlineKeyboardButton("💰 1000", callback_data="bj_bet_1000")],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    await q.message.edit_caption(
    caption="🃏 BLACKJACK CASINO\n\n💰 Scegli la puntata:",
    reply_markup=keyboard
    )

    uid = q.from_user.id

    deck = CARDS.copy()
    random.shuffle(deck)

    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    bj_games[uid] = {
        "deck": deck,
        "player": player,
        "dealer": dealer
    }

    testo = (
        "🃏 BLACKJACK\n\n"
        f"🃏 Le tue carte:\n{' '.join(player)}\n"
        f"Totale: {card_value(player)}\n\n"
        f"🎩 Carte del banco:\n{dealer[0]} ❓"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ CARTA", callback_data="hit"),
            InlineKeyboardButton("✋ STAI", callback_data="stand")
        ],
        [
            InlineKeyboardButton("🏠 MENU", callback_data="menu")
        ]
    ])

    await q.message.reply_text(
        testo,
        reply_markup=keyboard
    )

#==========================
#  START BJ
#==========================

async def start_bj(update, context, bet):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    u = get_user(uid)

    if u["chips"] < bet:
        return await q.answer("❌ Chips insufficienti", show_alert=True)

    u["chips"] -= bet
    save_user(u)

    deck = CARDS.copy()
    random.shuffle(deck)

    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    bj_games[uid] = {
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    text = (
        "🃏 BLACKJACK\n\n"
        f"💰 Puntata: {bet}\n\n"
        f"🎩 Banco: {dealer[0]} ❓\n"
        f"👤 Tu: {' '.join(player)}\n"
        f"📊 Totale: {card_value(player)}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ CARTA", callback_data="hit"),
         InlineKeyboardButton("✋ STAI", callback_data="stand")],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    await q.message.edit_caption(
    caption=text,
    reply_markup=keyboard
    )

# =========================
# ➕ HIT
# =========================
async def hit(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if uid not in bj_games:
        try:
            await q.message.edit_caption(
                caption="❌ Nessuna partita attiva.\n\n🏠 Usa MENU"
            )
        except:
            await q.message.reply_text("❌ Nessuna partita attiva.\n\n🏠 Usa MENU")
        return

    game = bj_games[uid]

    # 🧠 sicurezza deck
    if not game["deck"]:
        game["deck"] = CARDS.copy()
        random.shuffle(game["deck"])

    game["player"].append(game["deck"].pop())

    player = game["player"]
    dealer = game["dealer"]

    p_total = card_value(player)

    # 💥 BUST
    if p_total > 21:

        text = (
            "💥 SBALLATO!\n\n"
            f"🃏 TU: {' '.join(player)} ({p_total})\n\n"
            f"🎩 BANCO: {' '.join(dealer)} ({card_value(dealer)})\n\n"
            "💰 RISULTATO: -puntata"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🃏 GIOCA ANCORA", callback_data="blackjack")],
            [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
        ])

        bj_games.pop(uid, None)

        await q.message.edit_caption(
            caption=text,
            reply_markup=keyboard
        )
        return

    # 🃏 BLACKJACK NATURALE LIVE CHECK
    if p_total == 21:

        text = (
            "🔥 BLACKJACK!\n\n"
            f"🃏 TU: {' '.join(player)} (21)\n\n"
            f"🎩 BANCO: {dealer[0]} ❓\n\n"
            "👉 puoi STARE o continuare"
        )

    else:

        text = (
            "🃏 BLACKJACK\n\n"
            f"🃏 TU: {' '.join(player)} ({p_total})\n\n"
            f"🎩 BANCO: {dealer[0]} ❓"
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ CARTA", callback_data="hit"),
            InlineKeyboardButton("✋ STAI", callback_data="stand")
        ],
        [
            InlineKeyboardButton("🏠 MENU", callback_data="menu")
        ]
    ])

    await q.message.edit_caption(
        caption=text,
        reply_markup=keyboard
    )
# =========================
# ✋ STAND
# =========================
async def stand(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if uid not in bj_games:
        return

    game = bj_games[uid]

    player = game["player"]
    dealer = game["dealer"]

    while card_value(dealer) < 17:
        dealer.append(game["deck"].pop())

    p = card_value(player)
    d = card_value(dealer)

    if d > 21:
        risultato = "🎉 HAI VINTO!"
    elif p > d:
        risultato = "🎉 HAI VINTO!"
    elif p < d:
        risultato = "😔 HAI PERSO"
    else:
        risultato = "🤝 PAREGGIO"

    testo = (
        f"{risultato}\n\n"
        f"🃏 Le tue carte:\n{' '.join(player)}\n"
        f"Totale: {p}\n\n"
        f"🎩 Carte del banco:\n{' '.join(dealer)}\n"
        f"Totale banco: {d}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🃏 GIOCA ANCORA", callback_data="blackjack")
        ],
        [
            InlineKeyboardButton("🏠 MENU", callback_data="menu")
        ]
    ])

    del bj_games[uid]

    await q.message.edit_caption(
        caption=text,
        reply_markup=keyboard
    )
#==========================
# BLACKJACK ASYNC
#==========================

async def blackjack_bet(update, context, amount):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    bj_games[uid] = {
        "deck": CARDS.copy(),
        "player": [],
        "dealer": []
    }

    random.shuffle(bj_games[uid]["deck"])

    game = bj_games[uid]

    game["player"] = [game["deck"].pop(), game["deck"].pop()]
    game["dealer"] = [game["deck"].pop(), game["deck"].pop()]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ CARTA", callback_data="hit"),
            InlineKeyboardButton("✋ STAI", callback_data="stand")
        ],
        [
            InlineKeyboardButton("🏠 MENU", callback_data="menu")
        ]
    ])

    text = (
        f"🃏 BLACKJACK\n\n"
        f"💰 Puntata: {amount}\n\n"
        f"🃏 Tu: {' '.join(game['player'])}\n"
        f"🎩 Banco: {game['dealer'][0]} ❓"
    )

    await q.message.edit_caption(
        caption=text,
        reply_markup=keyboard
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
        return await safe_edit(q.message, "⏳ Sei già al tavolo", reply_markup=main_menu_keyboard())

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
    random.choice(CARDS),
    random.choice(CARDS)
    ]

    t["pot"] += bet
    user_tables[uid] = table_id

    # 👥 se non ci sono abbastanza player
    if len(t["players"]) < 2:
        return await safe_edit(
            q.message,
            f"🃏 TABLE\n👥 {len(t['players'])}/6\n💰 Pot: {t['pot']}",
            reply_markup=main_menu_keyboard()
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
    txt = "🃏 <txt = "<b>BLACKJACK PvP LIVE</b>\n\n"

current_uid = None

if t["order"] and t["turn_index"] < len(t["order"]):
    current_uid = t["order"][t["turn_index"]]

for p in t["players"]:
    uid = p["id"]
    name = p["name"]
    hand = t["hands"].get(uid) or []

    marker = "👉" if uid == current_uid else "👤"

    txt += f"{marker} <b>{name}</b>: {card_value(hand)} {hand}\n"

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
        reply_markup=main_menu_keyboard()
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
        reply_markup=main_menu_keyboard()
    )

# =====================
# 🏠 MENU HANDLER
# =====================
async def menu(update, context):
    q = update.callback_query
    await q.answer()

    await q.message.edit_caption(
        caption="🏠 MENU PRINCIPALE\n\nScegli un gioco:",
        reply_markup=main_menu_keyboard()
    )





async def cb_router(update, context):
    q = update.callback_query
    data = q.data

    await q.answer()

    # 🎯 BLACKJACK BET (PRIMA)
    if data.startswith("bj_bet_"):
        return await blackjack_bet(update, context, int(data.split("_")[-1]))

    # 🎯 BLACKJACK GAME
    if data == "blackjack":
        return await blackjack(update, context)

    if data == "hit":
        return await hit(update, context)

    if data == "stand":
        return await stand(update, context)

    if data == "hit_mp":
        return await hit_mp(update, context)

    if data == "stand_mp":
        return await stand_mp(update, context)

    # 🎯 GENERICO HANDLERS
    handlers = {
        "slot": slot,
        "roulette": roulette,
        "menu": menu,
        "shop": shop,
        "profilo": profilo,
        "classifica": classifica,
        "pvp": pvp,
        "bonus": bonus,
    }

    if data in handlers:
        return await handlers[data](update, context)

    # 🎯 BET NUMBERS FALLBACK
    if data.startswith("bet_"):
        return await bet_number(update, context)

    print("❌ CALLBACK NON GESTITA:", data)

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
        reply_markup=main_menu_keyboard()
    )


# =========================
# 🏆 CLASSIFICA
# =========================
async def classifica(update, context):
    q = update.callback_query

    await safe_edit(
        q.message,
        "🏆 CLASSIFICA\n\n🚧 In arrivo...",
        reply_markup=main_menu_keyboard()
    )


# =========================
# 🛒 SHOP
# =========================
async def shop(update, context):
    q = update.callback_query

    await safe_edit(
        q.message,
        "🛒 SHOP\n\n🚧 In arrivo...",
        reply_markup=main_menu_keyboard()
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


async def cb_router(update, context):
    q = update.callback_query
    data = q.data

    try:
        await q.answer()
    except:
        pass

    # SLOT
    if data == "slot":
        return await slot(update, context)

    if data == "spin_slot":
        return await spin_slot(update, context)

    # MENU (AGGIUNGI QUI)
    if data == "menu":
        return await send_main_menu(q.message.chat_id, context)

    if data == "go_menu":
        return await send_main_menu(q.message.chat_id, context) 

    # 🎲 ROULETTE MENU
    if data == "roulette":
        return await roulette(update, context)

    if data.startswith("num_"):
        return await select_number(update, context)

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

    if data.startswith("bet_"):
        return await bet_number(update, context)

    # 🎮 ALTRO
    if data == "pvp":
        return await pvp(update, context)

    # BLACKJACK
    if data == "blackjack":
        return await blackjack(update, context)

    if data == "hit":
        return await hit(update, context)

    if data == "stand":
       return await stand(update, context)
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
