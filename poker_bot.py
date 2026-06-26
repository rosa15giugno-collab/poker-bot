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
    InlineKeyboardMarkup,
    InputMediaPhoto
)

from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# ✅ FIX IMPORT GIUSTO
from telegram.error import BadRequest

# =========================
# 🧠 CONTEXT UTILS (TOPIC SAFE)
# =========================
def get_ctx(update):
    chat_id = update.effective_chat.id
    thread_id = update.effective_message.message_thread_id
    return chat_id, thread_id

# =====================
# 🔐 AUTH SYSTEM
# =====================
CASINO_CHAT_ID = -1002229066951
CASINO_TOPIC_ID = 1476685

def in_casino_topic(update):
    try:
        msg = update.effective_message
        chat = update.effective_chat

        if not msg or not chat:
            return False

        return (
            chat.id == CASINO_CHAT_ID
            and msg.message_thread_id == CASINO_TOPIC_ID
        )
    except:
        return False

def get_topic(update):
    msg = update.effective_message
    chat = update.effective_chat

    return chat.id, msg.message_thread_id 


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 SLOT", callback_data="slot")],
        [InlineKeyboardButton("🎲 ROULETTE", callback_data="roulette")],
        [InlineKeyboardButton("🃏 BLACKJACK", callback_data="blackjack")],
        [InlineKeyboardButton("⚔️ PVP", callback_data="pvp")],
        [InlineKeyboardButton("👤 PROFILO", callback_data="profilo")],
        [InlineKeyboardButton("🏆 CLASSIFICA", callback_data="classifica")],
        [InlineKeyboardButton("🛒 SHOP", callback_data="shop")],
        InlineKeyboardButton("🧠 INFO TURNO", callback_data="pvp_info"),
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
pvp_tables = {}
pvp_turn_index = {}
pvp_deadlines = {}

# 🔒 LOCK GLOBALE PvP (QUI)
pvp_lock = asyncio.Lock()

# LOCK BLACKJACK
update_ui_lock = asyncio.Lock()

# =========================
# RENDER PVP TABLE
# =========================
def render_table(t):
    players = t.get("players", [])

    # 👥 lista giocatori con mani e punteggio
    players_text = ""

    for uid in players:
        name = t.get("names", {}).get(uid, f"User {uid}")
        hand = t.get("hands", {}).get(uid, [])
        score = card_value(hand) if hand else 0

        cards = " ".join(hand) if hand else "—"

        players_text += (
            f"👤 {name}\n"
            f"🃏 {cards}\n"
            f"💯 {score}\n\n"
        )

    return (
        "🎮 PVP BLACKJACK\n\n"
        f"👥 Giocatori: {len(players)}\n"
        f"💰 Puntata: {t.get('bet', 0)}\n"
        f"📊 Stato: {t.get('state', 'waiting')}\n\n"
        f"🧠 Ultima azione:\n{t.get('last_action', '—')}\n\n"
        f"{players_text}"
    )

# =========================
# 🃏 BLACKJACK / PVP
# =========================
bj_games = {}
bets = {}
slot_games = {}
PVP_MIN = 2
PVP_MAX = 6
PVP_TIME = 30
CURRENT_PVP_TABLE = "pvp_main"
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
# =========================
# CARD VALUE (BLACKJACK + PVP)
# =========================
def card_value(hand):
    total = 0
    aces = 0

    for card in hand:
        value = (
            card.replace("♠️", "")
                .replace("♥️", "")
                .replace("♦️", "")
                .replace("♣️", "")
                .replace("️", "")
                .strip()
        )

        if value in ("J", "Q", "K"):
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
# SAFE EDIT (UNICO E STABILE)
# =========================

async def safe_edit(bot, msg, text, reply_markup=None, parse_mode=None):
    try:
        # 📸 MEDIA (photo / animation)
        if getattr(msg, "photo", None) or getattr(msg, "animation", None):
            return await msg.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

        # 💬 TESTO
        return await msg.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )

    except BadRequest as e:
        # messaggio identico → ignoriamo
        if "Message is not modified" in str(e):
            return False
        print(f"safe_edit BadRequest: {e}")

    except Exception as e:
        print(f"safe_edit error: {e}")

    # 🔥 FALLBACK SICURO (FIXATO)
    try:
        return await bot.send_message(
            chat_id=msg.chat.id,
            message_thread_id=msg.message_thread_id if hasattr(msg, "message_thread_id") else None,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )

    except Exception as e2:
        print(f"safe_edit fallback failed: {e2}")

    return False

# =========================
# DATABASE INIT (UNICO)
# =========================

import sqlite3
import threading
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "casino_pro.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("PRAGMA journal_mode=WAL")
cursor.execute("PRAGMA synchronous=NORMAL")

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

lock = threading.Lock()


# =========================
# TOKEN CONFIG
# =========================

TOKEN = os.getenv("CASINO_TOKEN")
if not TOKEN:
    raise ValueError("CASINO_TOKEN mancante")


# =========================
# MEDIA FILES
# =========================

MENU_PHOTO = "AgACAgQAAxkBAANFajK3EgT-sXBmbmi9vwS-ia3oNPYAAp4SaxuGHZhRRK7nT0alIxkBAAMCAAN5AAM8BA"

PHOTO_BLACKJACK = "AgACAgQAAxkBAANIajL7PfXN3cYXM6NliybRfiPCbP0AAk4PaxvsDJlRLQrkmC2DxfsBAAMCAAN5AAM8BA"

PROFILE_PHOTO = "AgACAgQAAxkBAANOajYuITssc-pAU6q03jTKI_7zp_oAAi4SaxubbrFRiaOrOLzu75oBAAMCAAN5AAM8BA"

SHOP_PHOTO = "AgACAgQAAxkBAAODajb6Dab8GhkTHecN2tMqSIrH3AYAApoPaxuTR7hRczsjOGoTyzcBAAMCAAN5AAM8BA"

BONUS_PHOTO = "AgACAgQAAxkBAANPajYuK06wNQGQdauEwDzc0O6j09cAAi8SaxubbrFR68wY43pHxZMBAAMCAAN5AAM8BA"

LEADERBOARD_PHOTO = "AgACAgQAAxkBAAOAajb5SIMtlH3auG-qn2qcYUTCccsAApcPaxuTR7hRnzIcNeUkxhABAAMCAAN5AAM8BA"

SHOP_VIP_PHOTO = "AgACAgQAAxkBAAODajb6Dab8GhkTHecN2tMqSIrH3AYAApoPaxuTR7hRczsjOGoTyzcBAAMCAAN5AAM8BA"

SHOP_SLOT_PHOTO = "AgACAgQAAxkBAAODajb6Dab8GhkTHecN2tMqSIrH3AYAApoPaxuTR7hRczsjOGoTyzcBAAMCAAN5AAM8BA"

SHOP_BJ_PHOTO = "AgACAgQAAxkBAAODajb6Dab8GhkTHecN2tMqSIrH3AYAApoPaxuTR7hRczsjOGoTyzcBAAMCAAN5AAM8BA"

# =========================
# SAVE USER (UNICO)
# =========================

def save_user(u):
    with lock:
        cursor.execute("""
        UPDATE users
        SET name=?, chips=?, xp=?, wins=?, losses=?, last_bonus=?, multiplier=?
        WHERE user_id=?
        """, (
            u.get("name", "Player"),
            int(u.get("chips", 0)),
            int(u.get("xp", 0)),
            int(u.get("wins", 0)),
            int(u.get("losses", 0)),
            int(u.get("last_bonus", 0)),
            float(u.get("multiplier", 1.0)),
            str(u.get("user_id"))
        ))
        conn.commit()


# =========================
# GET USER (UNICO)
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
        INSERT INTO users (user_id, name, chips, xp, wins, losses, last_bonus, multiplier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
# MAIN MENU
# =========================

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎰 SLOT", callback_data="slot"),
            InlineKeyboardButton("🎲 ROULETTE", callback_data="roulette")
        ],
        [
            InlineKeyboardButton("🃏 BLACKJACK", callback_data="blackjack"),
            InlineKeyboardButton("🆚 PVP", callback_data="pvp")
        ],
        [
            InlineKeyboardButton("🎁 BONUS", callback_data="bonus"),
            InlineKeyboardButton("🛒 SHOP", callback_data="shop")
        ],
        [
            InlineKeyboardButton("👤 PROFILO", callback_data="profile"),
            InlineKeyboardButton("🏆 CLASSIFICA", callback_data="leaderboard")
        ]
    ])


# =========================
# START (FIXED STABLE)
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)

    # 🔒 BLOCCO TOPIC
    msg = update.effective_message
    thread_id = getattr(msg, "message_thread_id", None)

    if thread_id is None or not in_casino_topic(update):
        return await update.message.reply_text(
            "🎰 Vai nel topic CASINO per giocare!"
        )

    # 👤 crea / carica utente
    u = get_user(uid, user.first_name)

    u["name"] = user.first_name
    save_user(u)

    print("START ARRIVATO:", uid)

    photo_id = "AgACAgQAAxkBAANFajK3EgT-sXBmbmi9vwS-ia3oNPYAAp4SaxuGHZhRRK7nT0alIxkBAAMCAAN5AAM8BA"

    caption = (
        "👑 Benvenuto in CASINO by Rosa\n\n"
        "𝑰𝒍 𝒄𝒂𝒔𝒐 𝒏𝒐𝒏 è 𝒄𝒂𝒐𝒔: è 𝒖𝒏 𝒍𝒊𝒏𝒈𝒖𝒂𝒈𝒈𝒊𝒐..\n"
        "…𝒄𝒉𝒊 𝒔𝒂 𝒂𝒔𝒄𝒐𝒍𝒕𝒂𝒓𝒍𝒐 𝒗𝒊𝒏𝒄𝒆\n\n"
        "🎰 Slot | 🎲 Roulette | 🃏 Blackjack 🆚 PvP\n"
        "🏆 Classifiche | 🎁 Bonus\n\n"
        "👇 Scegli una modalità"
    )

    await update.message.reply_photo(
        photo=photo_id,
        caption=caption,
        reply_markup=main_menu_keyboard()
    )
# =========================
# 🧠 TOPIC SAFE SENDER
# =========================

async def send_topic(context, table, text=None, photo=None, animation=None, reply_markup=None):
    chat_id = table["chat_id"]
    thread_id = table["thread_id"]

    try:
        if photo:
            return await context.bot.send_photo(
                chat_id=chat_id,
                message_thread_id=thread_id,
                photo=photo,
                caption=text,
                reply_markup=reply_markup
            )

        if animation:
            return await context.bot.send_animation(
                chat_id=chat_id,
                message_thread_id=thread_id,
                animation=animation,
                caption=text,
                reply_markup=reply_markup
            )

        return await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=text,
            reply_markup=reply_markup
        )

    except Exception as e:
        print("SEND_TOPIC ERROR:", e)
# =======================
# PROFILO
# =======================

from telegram import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

async def profile(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(update.effective_user.id)
    user = q.from_user
    u = get_user(uid)

    # ⭐ nome bello (username > nome > ID)
    if user.username:
        name_base = f"@{user.username}"
    elif user.first_name:
        name_base = user.first_name
    else:
        name_base = f"ID {user.id}"

    # ⭐ stelline decorative (puoi cambiarle dopo)
    chips = u.get("chips", 0)

    if chips >= 10_000_000:
        stars = "⭐⭐⭐⭐⭐"
    elif chips >= 1_000_000:
        stars = "⭐⭐⭐⭐"
    elif chips >= 100_000:
        stars = "⭐⭐⭐"
    elif chips >= 10_000:
        stars = "⭐⭐"
    else:
        stars = "⭐"

    name = f"{stars} {name_base}"

    text = (
        f"👤 PROFILO\n\n"
        f"👑 Nome: {name}\n\n"
        f"💰 Chips: {u.get('chips', 0)}\n"
        f"🏆 Vittorie: {u.get('wins', 0)}\n"
        f"💥 Sconfitte: {u.get('losses', 0)}\n"
        f"⭐ XP: {u.get('xp', 0)}\n"
    )

    try:
        
        await q.message.edit_media(
            media=InputMediaPhoto(
                media=PROFILE_PHOTO,
                caption=text
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
            ])
        )

    except Exception:
        await q.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
            ])
        )
#=====================
#  BONUS GIORNALIERO
#=====================

async def daily_bonus(update, context):

    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    now = time.time()
    cooldown = 86400  # 24 ore

    last = u.get("last_bonus", 0)

    # ⛔ Cooldown
    if now - last < cooldown:
        remaining = int(cooldown - (now - last))

        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60

        text = (
            "🎁 Bonus già riscattato!\n\n"
            f"⏳ Riprova tra {h}h {m}m {s}s"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
        ])

        return await context.bot.send_photo(
            chat_id=q.message.chat.id,
            message_thread_id=q.message.message_thread_id,
            photo=BONUS_PHOTO,
            caption=text,
            reply_markup=keyboard
        )

    # 🎁 Premio
    reward = 1000
    u["chips"] = int(u.get("chips", 0)) + reward
    u["last_bonus"] = now
    save_user(u)

    text = (
        "🎁 BONUS GIORNALIERO\n\n"
        f"💰 +{reward} chips ricevuti!\n"
        f"💎 Saldo attuale: {u['chips']}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    await context.bot.send_photo(
        chat_id=q.message.chat.id,
        message_thread_id=q.message.message_thread_id,
        photo=BONUS_PHOTO,
        caption=text,
        reply_markup=keyboard
    )

#======================
# SHOP
#======================

async def shop(update, context):
    q = update.callback_query
    await q.answer()

    text = (
        "🛒 SHOP CASINO\n\n"
        "💎 VIP PASS - 5000 chips\n"
        "   → +20% vincite su tutti i giochi\n\n"
        "🎰 BOOST SLOT - 3000 chips\n"
        "   → aumenta la fortuna nelle slot\n\n"
        "🃏 BLACKJACK PRO - 7000 chips\n"
        "   → miglior payout nel blackjack\n\n"
        "👇 Scegli un potenziamento:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Acquista VIP PASS", callback_data="buy_vip")],
        [InlineKeyboardButton("🎰 Acquista BOOST SLOT", callback_data="buy_slotboost")],
        [InlineKeyboardButton("🃏 Acquista BLACKJACK PRO", callback_data="buy_bjpro")],
        [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
    ])

    await context.bot.send_photo(
        chat_id=q.message.chat.id,
        message_thread_id=getattr(q.message, "message_thread_id", None),
        photo=BONUS_PHOTO,
        caption=text,
        reply_markup=keyboard
    )
#======================
# 💎 ACQUISTO VIP
#======================

async def buy_vip(update, context):
    print("BUY_VIP START")

    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)

    print("UID:", uid)

    u = get_user(uid)

    print("USER:", u)

    price = 5000

    # ❌ saldo insufficiente
    if u["chips"] < price:
        return await q.message.reply_text(
            f"❌ Non hai abbastanza chips.\n\n"
            f"💰 Saldo attuale: {u['chips']}\n"
            f"💎 Costo VIP: {price}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
            ])
        )

    # 💰 pagamento
    u["chips"] -= price
    u["vip"] = True
    save_user(u)

    text = (
        "💎 VIP ATTIVATO!\n\n"
        "✔️ Ora guadagni +20% su tutte le vincite"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
    ])

    chat_id = q.message.chat.id
    thread_id = getattr(q.message, "message_thread_id", None)

    # 📸 send photo stabile (evita edit error)
    await context.bot.send_photo(
        chat_id=chat_id,
        message_thread_id=thread_id,
        photo=SHOP_PHOTO,
        caption=text,
        reply_markup=keyboard
    )
#==========================
# 🎰 BUY SLOT BOOST SHOP
#==========================

async def buy_slotboost(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    price = 3000

    # ❌ saldo insufficiente
    if u["chips"] < price:
        return await q.message.reply_text(
            f"❌ Non hai abbastanza chips.\n\n"
            f"💰 Saldo attuale: {u['chips']}\n"
            f"💎 Costo VIP: {price}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
            ])
        )
    # 💰 acquisto
    u["chips"] -= price
    u["slot_boost"] = True
    save_user(u)

    text = (
        "🎰 BOOST SLOT ATTIVATO!\n\n"
        "✔️ Più fortuna nelle slot"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
    ])

    chat_id = q.message.chat.id
    thread_id = getattr(q.message, "message_thread_id", None)

    return await context.bot.send_photo(
        chat_id=chat_id,
        message_thread_id=thread_id,
        photo=SHOP_PHOTO,
        caption=text,
        reply_markup=keyboard
    )

#==========================
# BUY BLACK JACK SHOP
#==========================
async def buy_bjpro(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    price = 7000

    # ❌ saldo insufficiente
    if u.get("chips", 0) < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
        ])

        try:
            return await q.message.edit_text(
                "❌ Chips insufficienti per BLACKJACK PRO",
                reply_markup=keyboard
            )
        except:
            return await q.message.edit_caption(
                "❌ Chips insufficienti per BLACKJACK PRO",
                reply_markup=keyboard
            )

    # 💰 acquisto
    u["chips"] -= price
    u["bj_pro"] = True
    save_user(u)

    text = (
        "🃏 BLACKJACK PRO ATTIVATO!\n\n"
        "✔️ Payout migliorato"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
    ])

    chat_id = q.message.chat.id
    thread_id = getattr(q.message, "message_thread_id", None)

    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            message_thread_id=thread_id,
            photo=SHOP_BJ_PHOTO,
            caption=text,
            reply_markup=keyboard
        )

    except Exception as e:
        print("❌ ERROR BUY_BJPRO:", e)

        try:
            return await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=text,
                reply_markup=keyboard
            )
        except:
            return await q.message.edit_text(
                text,
                reply_markup=keyboard
            )
#==========================
# 🎰 BUY SLOT SHOP
#==========================

async def buy_slotboost(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    price = 3000

    # ❌ saldo insufficiente
    if u["chips"] < price:
        return await q.message.reply_text(
            f"❌ Non hai abbastanza chips.\n\n"
            f"💰 Saldo attuale: {u['chips']}\n"
            f"💎 Costo VIP: {price}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
            ])
        )

    # 💰 acquisto
    u["chips"] -= price
    u["slot_boost"] = True
    save_user(u)

    text = (
        "🎰 BOOST SLOT ATTIVATO!\n\n"
        "✔️ Più fortuna nelle slot"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Torna al Menu", callback_data="menu")]
    ])

    chat_id = q.message.chat.id
    thread_id = getattr(q.message, "message_thread_id", None)

    # 🔥 FIX: evita invio thread_id=None
    kwargs = {
        "chat_id": chat_id,
        "photo": SHOP_SLOT_PHOTO,
        "caption": text,
        "reply_markup": keyboard
    }

    if thread_id is not None:
        kwargs["message_thread_id"] = thread_id

    await context.bot.send_photo(**kwargs)
#==========================
# CLASSIFICA
#==========================

async def leaderboard(update, context):
    q = update.callback_query
    await q.answer()

    cursor.execute(
        "SELECT name, chips FROM users ORDER BY chips DESC LIMIT 10"
    )
    rows = cursor.fetchall()

    text = "🏆 CLASSIFICA TOP 10\n\n"

    for i, r in enumerate(rows, 1):
        text += f"{i}. {r[0]} - 💰 {r[1]}\n"

    try:
        await q.message.edit_media(
            media=InputMediaPhoto(
                media=LEADERBOARD_PHOTO,
                caption=text
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
            ])
        )
    except:
        await q.message.edit_text(text)


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
games = {}

# =========================
# 🎰 SLOT SYMBOLS (WEIGHTED)
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
# 🎰 SLOT MENU (SAFE FIX)
# =========================

async def slot(update, context):
    q = update.callback_query

    try:
        if q:
            await q.answer()
            target = q.message
        else:
            target = update.message

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎰 SPIN 200", callback_data="spin_slot_200")],
            [InlineKeyboardButton("🎰 SPIN 400", callback_data="spin_slot_400")],
            [InlineKeyboardButton("🎰 SPIN 900", callback_data="spin_slot_900")],
            [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
        ])

        thread_id = target.message_thread_id

        try:
            await target.reply_animation(
                animation="BAACAgQAAxkBAANCajJYH3Jfdd7S1sx5SVA2snDBo-kAAuwmAAKGHZhRonuMrpmMdyg8BA",
                caption="🎰 SLOT MACHINE\n\n💰 Scegli la puntata!",
                reply_markup=keyboard
            )

        except Exception:
            await context.bot.send_animation(
                chat_id=target.chat.id,
        message_thread_id=target.message_thread_id,
        animation="BAACAgQAAxkBAANCajJYH3Jfdd7S1sx5SVA2snDBo-kAAuwmAAKGHZhRonuMrpmMdyg8BA",
            caption="🎰 SLOT MACHINE\n\n💰 Scegli la puntata!",
            reply_markup=keyboard
        )

    except Exception as e:
        print("SLOT MENU ERROR:", e)
async def spin_slot(update, context):

    q = update.callback_query
    await q.answer()

    msg = q.message
    uid = str(q.from_user.id)
    u = get_user(uid)

    # 🛡️ COOLDOWN
    now = time.time()
    if uid in COOLDOWN and now - COOLDOWN[uid] < 2:
        return
    COOLDOWN[uid] = now

    # 💰 PUNTATA
    try:
        bet = int(q.data.split("_")[-1])
    except:
        bet = 200

    # 🔒 saldo check
    if u["chips"] < bet:
        return await q.answer("❌ Chips insufficienti", show_alert=True)

    u["chips"] -= bet

    reels = ["🎰", "🎰", "🎰"]

    thread_id = msg.message_thread_id

    # 🎬 ANIMAZIONE
    for i in range(6):
        await asyncio.sleep(0.6)

        if i < 2:
            reels[0] = weighted_symbol()
        elif i < 4:
            reels[1] = weighted_symbol()
        else:
            reels[2] = weighted_symbol()

        text = (
            "🎬 SPIN IN CORSO...\n\n"
            f"┃ {reels[0]} | {reels[1]} | {reels[2]} ┃\n\n"
            f"💰 Puntata: {bet} chips"
        )

        # 🔥 FIX: evita spam + evita edit su messaggi non pronti
        if i % 2 == 0:
            try:
                await context.bot.edit_message_text(
                    chat_id=msg.chat.id,
                    message_id=msg.message_id,
                    text=text
                )    
            except:
                try:
                    await context.bot.edit_message_caption(
                        chat_id=msg.chat.id,
                        message_id=msg.message_id,
                        caption=text
                    )
                except Exception as e:
                    print("SPIN EDIT ERROR:", e)
                

    # =========================
    # 🎯 RISULTATO
    # =========================

    vip = random.choice(VIP_MULT)
    if reels[0] == reels[1] == reels[2]:
        win = int(bet * 10 * vip)
        status = "🏆 JACKPOT!"
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        win = int(bet * 3 * vip)
        status = f"✨ QUASI VITTORIA! +{int(bet * 3)} CHIPS"
    else:
        win = 0
        status = "💥 HAI PERSO!"

    # =========================
    # 💎 MULTIPLIER SAFE
    # =========================
    mult = float(u.get("multiplier", 1.0))
    vip = float(vip)

    win = int(win * mult)

    # =========================
    # 💰 UPDATE SALDO
    # =========================
    u["chips"] += win
    u["xp"] = int(u.get("xp", 0) + max(1, win // 15))

    if win > 0:
        u["wins"] = u.get("wins", 0) + 1
    else:
        u["losses"] = u.get("losses", 0) + 1

    save_user(u)

    
    
    new_balance = u["chips"]
    # =========================
    # 🧾 OUTPUT FINALE
    # =========================
    final_text = (
        f"{status}\n\n"
        f"┃ {reels[0]} | {reels[1]} | {reels[2]} ┃\n\n"
        f"💰 Vincita: +{win} chips\n"
        f"💎 Saldo: {new_balance}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 SPIN DI NUOVO", callback_data="slot")],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    await asyncio.sleep(0.3)

    try:
        await msg.edit_caption(caption=final_text, reply_markup=keyboard)
    except:
        try:
            await msg.edit_text(final_text, reply_markup=keyboard)
        except Exception as e:
            print("FINAL ERROR:", e)
            try:
                thread_id = getattr(msg, "message_thread_id", None)

                await context.bot.send_message(
                    chat_id=msg.chat.id,
                    message_thread_id=thread_id,
                    text=final_text,
                    reply_markup=keyboard
                )    
            except:
                pass

    return
    
# =========================
# 💰 START PARTITA BLACKJACK FIX FILEID
# =========================
async def blackjack(update, context):
    q = update.callback_query
    await q.answer()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 100", callback_data="blackjack_bet_100"),
            InlineKeyboardButton("💰 500", callback_data="blackjack_bet_500")
        ],
        [
            InlineKeyboardButton("💰 1000", callback_data="blackjack_bet_1000")
        ],
        [
            InlineKeyboardButton("🏠 MENU", callback_data="menu")
        ]
    ])

    text = "🃏 BLACKJACK\n\n💰 Scegli la puntata:"

    # 🔥 FIX CHIAVE: EDIT invece di reply_text
    return await safe_edit(
        context.bot,
        q.message,
        text,
        reply_markup=keyboard
    )



# =========================
# 💰 START PARTITA BLACKJACK
# =========================
async def blackjack_bet(update, context, amount):
    print("🔥 blackjack_bet:", amount)

    q = update.callback_query
    await q.answer()

    uid = str(update.effective_user.id)
    u = get_user(uid)

    # ❌ CHIPS CHECK
    if u.get("chips", 0) < amount:

        text = "❌ Non hai abbastanza chips per questa puntata."

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
        ])

        return await safe_edit(
            context.bot,
            q.message,
            text,
            reply_markup=keyboard
        )

    # 💰 DEDUCI CHIPS
    u["chips"] -= amount
    save_user(u)

    # 🃏 CREA MAZZO
    deck = CARDS.copy()
    random.shuffle(deck)

    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    # 🔄 RESET PARTITA
    bj_games.pop(uid, None)

    bj_games[uid] = {
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "bet": amount
    }

    # 🎮 KEYBOARD
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ CARTA", callback_data="hit"),
            InlineKeyboardButton("✋ STAI", callback_data="stand")
        ],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    # 🧾 TESTO
    text = (
        "🃏 BLACKJACK\n\n"
        f"💰 Puntata: {amount}\n\n"
        f"🃏 TU: {' '.join(player)}\n"
        f"🎩 BANCO: {dealer[0]} ❓\n"
        f"📊 Totale: {card_value(player)}"
    )

    return await safe_edit(
        context.bot,
        q.message,
        text,
        reply_markup=keyboard
    )
# =========================
# ➕ HIT
# =========================
async def hit(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(update.effective_user.id)

    # ❌ nessuna partita
    if uid not in bj_games:
        return await safe_edit(context.bot, q.message, "❌ Nessuna partita attiva.")

    game = bj_games[uid]

    # 🔄 ricrea deck se vuoto
    if not game["deck"]:
        game["deck"] = CARDS.copy()
        random.shuffle(game["deck"])

    # 🃏 pesca carta
    game["player"].append(game["deck"].pop())

    player = game["player"]
    dealer = game["dealer"]
    bet = game["bet"]

    p_total = card_value(player)

    # 💥 BUST
    if p_total > 21:
        u = get_user(uid)

        text = (
            "💥 SBALLATO!\n\n"
            f"🃏 TU: {' '.join(player)} ({p_total})\n"
            f"🎩 BANCO: {' '.join(dealer)} ({card_value(dealer)})\n\n"
            f"💸 HAI PERSO -{bet} chips\n"
            f"🏦 SALDO: {u['chips']}"
        )

        bj_games.pop(uid, None)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🃏 RIGIOCA", callback_data="blackjack")],
            [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
        ])

        return await safe_edit(context.bot, q.message, text, reply_markup=keyboard)

    # 🃏 CONTINUA PARTITA
    text = (
        "🃏 BLACKJACK\n\n"
        f"🃏 TU: {' '.join(player)} ({p_total})\n"
        f"🎩 Banco: {dealer[0]}\n\n"
        "🎮 Scegli la tua mossa"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ CARTA", callback_data="hit"),
            InlineKeyboardButton("✋ STAI", callback_data="stand")
        ],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    return await safe_edit(context.bot, q.message, text, reply_markup=keyboard)


# =========================
# ✋ STAND
# =========================
async def stand(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(update.effective_user.id)

    # ❌ nessuna partita attiva
    if uid not in bj_games:
        await safe_edit(context.bot, q.message, "❌ Nessuna partita attiva.")
        return

    game = bj_games[uid]
    u = get_user(uid)

    player = game["player"]
    dealer = game["dealer"]
    bet = game["bet"]

    # 🃏 dealer play (regola casino)
    while card_value(dealer) < 17:
        if not game["deck"]:
            game["deck"] = CARDS.copy()
            random.shuffle(game["deck"])

        dealer.append(game["deck"].pop())

    p = card_value(player)
    d = card_value(dealer)

    # =========================
    # 🃏 BLACKJACK NATURALE
    # =========================
    if p == 21 and len(player) == 2:
        win = int(bet * 2.5)
        profit = win - bet
        u["chips"] += win

        risultato = (
            "🃏 BLACKJACK!\n"
            f"💰 Vincita: +{profit} chips\n"
            f"🏦 Saldo: {u['chips']} chips"
        )

    # =========================
    # 🎉 VITTORIA
    # =========================
    elif d > 21 or p > d:
        win = bet * 2
        profit = bet
        u["chips"] += win

        risultato = (
            "🎉 HAI VINTO!\n"
            f"💰 Vincita: +{profit} chips\n"
            f"🏦 Saldo: {u['chips']} chips"
        )

    # =========================
    # 😔 SCONFITTA
    # =========================
    elif p < d:
        # già scalato in blackjack_bet
        risultato = (
            "😔 HAI PERSO\n"
            f"💸 Perdita: -{bet} chips\n"
            f"🏦 Saldo: {u['chips']} chips"
        )

    # =========================
    # 🤝 PAREGGIO
    # =========================
    else:
        u["chips"] += bet

        risultato = (
            "🤝 PAREGGIO\n"
            f"💰 Rimborso: +{bet} chips\n"
            f"🏦 Saldo: {u['chips']} chips"
        )

    # 💾 SALVA UTENTE
    save_user(u)

    # 🧹 CHIUDI PARTITA
    bj_games.pop(uid, None)

    # 🎮 OUTPUT FINALE
    testo = (
        f"{risultato}\n\n"
        f"🃏 TU: {' '.join(player)} ({p})\n"
        f"🎩 BANCO: {' '.join(dealer)} ({d})"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 RIGIOCA", callback_data="blackjack")],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    await safe_edit(context.bot, q.message, testo, reply_markup=keyboard)
    return
#====================
#  PVP
#=====================

async def pvp(update, context):
    q = update.callback_query
    await q.answer()

    table_id = CURRENT_PVP_TABLE

    # 🛑 tavolo già attivo
    if table_id in pvp_tables:
        table = pvp_tables[table_id]

        if table.get("state") != "finished":
            return await q.answer(
                "🎮 Tavolo già aperto!",
                show_alert=True
            )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎯 ENTRA TAVOLO",
                callback_data=f"pvp_join_{table_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 AVVIA PARTITA",
                callback_data=f"pvp_start_{table_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 MENU",
                callback_data="menu"
            )
        ]
    ])

    chat_id = q.message.chat.id
    thread_id = getattr(q.message, "message_thread_id", None)

    # 🎬 INVIO MESSAGGIO
    msg = await context.bot.send_animation(
        chat_id=chat_id,
        message_thread_id=thread_id,
        animation="BAACAgQAAxkBAANSajYyOYLMYvipiOk9MIO_9GrCnEQAArUnAAKbbrFRZhzxx2G87ck8BA",
        caption=(
            "🎬 PVP BLACKJACK\n\n"
            "👥 Tavolo aperto (2-6 giocatori)\n"
            "💰 Puntata: 200 chips\n\n"
            "⏳ Entra ora!"
        ),
        reply_markup=keyboard
    )

    # 🧠 SALVATAGGIO TAVOLO
    pvp_tables[table_id] = {
        "players": [],
        "hands": {},
        "bets": {},
        "dealer": [],
        "deck": [],
        "state": "waiting",
        "turn_index": 0,
        "names": {},
        "bet": 500,

        "chat_id": msg.chat.id,
        "thread_id": getattr(msg, "message_thread_id", None),
        "message_id": msg.message_id
    }
# =========================
# ENTRATA TAVOLO PVP
# =========================

async def pvp_join(update, context, table_id):
    q = update.callback_query
    uid = str(update.effective_user.id)

    table = pvp_tables.get(table_id)
    if not table:
        return await q.answer("Tavolo non esiste", show_alert=True)

    if table["state"] != "waiting":
        return await q.answer(
            "La partita è già iniziata",
            show_alert=True
        )

    # 🔒 anti-duplicazione
    if uid in table["players"]:
        return await q.answer(
            "Sei già dentro",
            show_alert=True
        )

    if len(table["players"]) >= PVP_MAX:
        return await q.answer(
            "Tavolo pieno",
            show_alert=True
        )

    # 👤 init names
    if "names" not in table:
        table["names"] = {}

    # 👤 nome visualizzato
    if q.from_user.username:
        name = f"@{q.from_user.username}"
    else:
        name = q.from_user.first_name or "Giocatore"

    # 👤 salva player
    table["players"].append(uid)
    table["hands"][uid] = []
    table["bets"][uid] = 200
    table["names"][uid] = name

    await q.answer("Entrato 🎯")

    # 👥 lista giocatori
    players_text = "\n".join(
        f"• {table['names'][pid]}"
        for pid in table["players"]
    )

    # 🎬 aggiorna caption
    try:
        await q.message.edit_caption(
            caption=(
                "🎬 PVP BLACKJACK LIVE\n\n"
                f"👥 Giocatori: {len(table['players'])}/{PVP_MAX}\n\n"
                f"{players_text}\n\n"
                "⏳ In attesa avvio..."
            ),
            reply_markup=q.message.reply_markup
        )
    except Exception as e:
        print("EDIT CAPTION ERROR:", e)
# =========================
# START PARTITA PVP
# =========================

async def pvp_start(update, context, table_id):
    q = update.callback_query
    await q.answer()

    table = pvp_tables.get(table_id)

    if not table:
        return await q.answer("Tavolo non trovato", show_alert=True)

    if len(table["players"]) < PVP_MIN:
        return await q.answer("Servono almeno 2 giocatori", show_alert=True)

    # 🧠 salva SEMPRE riferimenti messaggio (FONDAMENTALE)
    table["chat_id"] = q.message.chat.id
    table["message_id"] = q.message.message_id
    table["thread_id"] = getattr(q.message, "message_thread_id", None)

    # 🃏 deck setup
    deck = CARDS.copy()
    random.shuffle(deck)

    table["bet"] = 500
    table["deck"] = deck
    table["state"] = "playing"
    table["turn_index"] = 0

    # 👤 deal players
    for uid in table["players"]:
        table["hands"][uid] = [deck.pop(), deck.pop()]

    # 🏦 dealer
    table["dealer"] = [deck.pop(), deck.pop()]

    # 🛑 stop timer precedente
    old_timer = table.get("timer_task")
    if old_timer and not old_timer.done():
        old_timer.cancel()

    # 🎬 animazione start
    try:
        await q.message.edit_caption(
            caption="🎬 DISTRIBUZIONE CARTE...\n\n🔥 Preparati al tavolo...",
            reply_markup=None
        )
    except:
        await q.message.edit_text(
            "🎬 DISTRIBUZIONE CARTE...\n\n🔥 Preparati al tavolo..."
        )

    await asyncio.sleep(1.2)

    # 🔥 aggiorna tavolo
    await update_table(context.bot, table)

    await asyncio.sleep(0.3)

    # ▶️ primo turno
    return await next_turn(context, table_id)
# =========================
# TURNO CON TIMER PVP
# =========================
async def next_turn(context, table_id):
    table = pvp_tables.get(table_id)

    if not table or table.get("state") != "playing":
        return

    players = table["players"]

    # 🏁 fine → dealer
    if table["turn_index"] >= len(players):
        table["state"] = "dealer"
        return await dealer_phase(context, table_id)

    uid = players[table["turn_index"]]
    name = table.get("names", {}).get(uid, f"User {uid}")
    hand = table["hands"].get(uid, [])

    # ⏱️ timer
    table["deadline"] = time.time() + PVP_TIME
    table["current_turn_uid"] = uid

    # 🧠 stop timer precedente
    old_timer = table.get("timer_task")
    if old_timer and not old_timer.done():
        old_timer.cancel()

    # 🔥 LOG CHIARO (NON SOSTITUISCE UI)
    table["last_action"] = f"🎮 Tocca a {name}"

    # 📊 aggiorna tavolo
    await update_table(context.bot, table)

    # ⏱️ avvia timer
    table["timer_task"] = asyncio.create_task(
        timer_auto(context, table_id)
    )
# =========================
# TIMER AUTO AFK PVP (FIXED)
# =========================
async def timer_auto(context, table_id):
    table = pvp_tables.get(table_id)
    thread_id = table.get("thread_id")

    if not table or table.get("state") != "playing":
        return

    # ⏱️ attesa “soft”
    await asyncio.sleep(PVP_TIME)

    # 🔒 se turno è già cambiato → IGNORA COMPLETAMENTE
    if time.time() > table.get("deadline", 0):
        return

    # 🔥 sicurezza anti doppio trigger
    if table.get("turn_index") >= len(table.get("players", [])):
        return

    # 🎯 avanza turno
    table["turn_index"] += 1

    chat_id = table.get("chat_id")

    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text="⏱️ Tempo scaduto → STAND automatico"
        )

    # 🔁 vai al prossimo turno
    return await next_turn(context, table_id)
# =========================
# HIT PVP (FIXED STABLE)
# =========================
async def pvp_hit(update, context, table_id):
    async with pvp_lock:
        q = update.callback_query
        table = pvp_tables.get(table_id)

        if not table or table.get("state") != "playing":
            return await q.answer("Tavolo non valido", show_alert=True)

        idx = table["turn_index"]

        if idx >= len(table["players"]):
            return await q.answer("Turno finito", show_alert=True)

        uid = str(table["players"][idx])

        if str(q.from_user.id) != uid:
            return await q.answer("⛔ Non è il tuo turno", show_alert=True)

        if not table.get("deck"):
            return await q.answer("Mazzo finito", show_alert=True)

        # 🃏 carta
        card = table["deck"].pop()
        table["hands"][uid].append(card)

        score = card_value(table["hands"][uid])
        name = table.get("names", {}).get(uid, uid)

        # 🔥 log chiaro
        table["last_action"] = f"🃏 {name} pesca {card} → {score}"

        # 💥 bust → cambio turno immediato
        if score > 21:
            table["last_action"] += " 💥 BUST"
            table["turn_index"] += 1

            # 🔁 passa turno SUBITO
            await next_turn(context, table_id)

            # feedback solo utente
            return await q.answer(f"💥 BUST | {score}", show_alert=False)

        # 🔁 update tavolo (solo se NON bust)
        await update_table(context.bot, table)

        await q.answer(f"🃏 {card} | {score}", show_alert=False)
# =========================
# STAND PVP (FIXED STABLE)
# =========================
async def pvp_stand(update, context, table_id):
    q = update.callback_query
    table = pvp_tables.get(table_id)

    if not table or table.get("state") != "playing":
        return await q.answer("Tavolo non valido", show_alert=True)

    if table.get("action_lock"):
        return await q.answer("⏳ Attendi...", show_alert=True)

    table["action_lock"] = True

    try:
        idx = table["turn_index"]

        if idx >= len(table["players"]):
            return await q.answer("Turno finito", show_alert=True)

        uid = str(table["players"][idx])

        if str(q.from_user.id) != uid:
            return await q.answer("⛔ Non è il tuo turno", show_alert=True)

        await q.answer("STAND")

        # 🛑 stop timer
        old_timer = table.get("timer_task")
        if old_timer and not old_timer.done():
            old_timer.cancel()

        # ➡️ next player
        table["turn_index"] += 1

        # 🔥 update UI
        await update_table(context.bot, table)

        return await next_turn(context, table_id)

    finally:
        table["action_lock"] = False

# =========================
# DEALER PHASE PVP
# =========================
async def dealer_phase(context, table_id):
    table = pvp_tables.get(table_id)

    if not table:
        return

    thread_id = table.get("thread_id")
    chat_id = table.get("chat_id")

    if not chat_id:
        print("❌ chat_id mancante nel finale PVP")
        return

    # 🛑 stop timer
    old_timer = table.get("timer_task")
    if old_timer and not old_timer.done():
        old_timer.cancel()

    await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text="🎩 Il Banco sta giocando..."
    )

    await asyncio.sleep(2)

    # 🎬 dealer pesca
    while card_value(table.get("dealer", [])) < 17:
        if not table.get("deck"):
            break

        table["dealer"].append(table["deck"].pop())
        await asyncio.sleep(2)

    dealer_hand = table.get("dealer", [])
    dealer_score = card_value(dealer_hand)

    # =========================
    # 🏆 RESULT BUILD
    # =========================

    result = (
        "🏆🏆 RISULTATO PARTITA 🏆🏆\n\n"
        f"🎩 Banco: {' '.join(dealer_hand) if dealer_hand else '—'}\n"
        f"💯 Totale Banco: {dealer_score}\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    bet = table.get("bet", 500)

    winner_block = ""
    others_block = ""

    for uid in table.get("players", []):

        name = (table.get("names") or {}).get(uid, f"User {uid}")

        hand = table.get("hands", {}).get(uid, [])
        score = card_value(hand)

        hand_text = " ".join(hand) if hand else "—"

        u = get_user(str(uid))
        chips = u.get("chips", 0)

        # =========================
        # 🏆 VINTO (UNICO BLOCCO WINNER)
        # =========================
        if dealer_score <= 21 and score <= 21 and score > dealer_score:

            u["wins"] = u.get("wins", 0) + 1
            u["chips"] = chips + bet

            winner_block = (
                "━━━━━━━━━━━━━━━━━━\n"
                "        🏆 VINCITORE 🏆\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"        👑 {name}\n"
                f"        🃏 {hand_text}\n"
                f"        💯 {score}\n"
                f"        💰 +{bet} 🪙\n"
                f"        🏦 Chips: {u['chips']}\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
            )

            save_user(u)
            continue

        # =========================
        # ❌ RISULTATI NORMALI
        # =========================

        if score > 21:
            res = f"💥 PERSO (-{bet} 🪙)"
            u["losses"] = u.get("losses", 0) + 1
            u["chips"] = max(0, chips - bet)

        elif dealer_score > 21:
            res = f"🏆 VINTO (+{bet} 🪙)"
            u["wins"] = u.get("wins", 0) + 1
            u["chips"] = chips + bet

        elif score == dealer_score:
            res = "🤝 PAREGGIO (±0 🪙)"
            u["chips"] = chips

        else:
            res = f"💥 PERSO (-{bet} 🪙)"
            u["losses"] = u.get("losses", 0) + 1
            u["chips"] = max(0, chips - bet)

        save_user(u)

        others_block += (
            f"👤 {name}\n"
            f"🃏 Mano: {hand_text}\n"
            f"💯 Totale: {score}\n"
            f"{res}\n"
            f"🏦 Saldo: {u['chips']} 🪙\n\n"
            "──────────────\n\n"
        )

    # =========================
    # FINAL COMPOSITION
    # =========================

    result += winner_block + others_block

    # =========================
    # FINAL BUTTONS
    # =========================

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 GIOCA DI NUOVO", callback_data="pvp")],
        [InlineKeyboardButton("🏠 MENU", callback_data="menu")]
    ])

    if len(result) > 3900:
        result = result[:3900] + "\n\n... (troncato)"

    table["state"] = "finished"

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=result,
            reply_markup=keyboard
        )
    except Exception as e:
        print("❌ ERROR FINAL SEND:", e)

    # 🧹 CLEANUP
    old_timer = table.get("timer_task")
    if old_timer and not old_timer.done():
        old_timer.cancel()

    table["deleted"] = True
    pvp_tables.pop(table_id, None)
#=======================
# UPDATE_TABLE
#======================
async def update_table(bot, t):
    async with update_ui_lock:

        if not t:
            return

        if t.get("state") == "finished" or t.get("deleted"):
            return

        chat_id = t.get("chat_id")
        message_id = t.get("message_id")

        if not chat_id or not message_id:
            return

        players = t.get("players", [])
        idx = t.get("turn_index", 0)
        state = t.get("state", "waiting")

        # =========================
        # 🎯 GIOCATORE DI TURNO (SAFE)
        # =========================
        current_uid = players[idx] if (players and idx < len(players)) else None
        current_name = (t.get("names") or {}).get(current_uid, "—")

        # =========================
        # 👤 PLAYERS LIST
        # =========================
        players_text = "👥 GIOCATORI:\n\n"

        for uid in players:

            hand = t.get("hands", {}).get(uid, [])
            score = card_value(hand)
            name = (t.get("names") or {}).get(uid, f"User {uid}")

            # 🔥 FIX UID TYPE SAFETY
            is_turn = str(uid) == str(current_uid)

            if is_turn:
                players_text += (
                    "━━━━━━━━━━━━━━\n"
                    "🔥 🎮 TURNO ORA 🔥\n"
                    "━━━━━━━━━━━━━━\n"
                    f"👑 {name}\n"
                    f"🃏 {' '.join(hand) if hand else '—'} ({score})\n"
                    "━━━━━━━━━━━━━━\n\n"
                )
            else:
                players_text += (
                    f"👤 {name}\n"
                    f"   🃏 {' '.join(hand) if hand else '—'} ({score})\n\n"
                )

        # =========================
        # 🏦 DEALER
        # =========================
        dealer = t.get("dealer", [])
        dealer_score = card_value(dealer)

        dealer_text = f"🎩 BANCO: {' '.join(dealer) if dealer else '—'} ({dealer_score})"

        if state == "waiting":
            dealer_text += "\n⏳ In attesa giocatori..."
        elif state == "playing":
            dealer_text += "\n🎮 Partita in corso..."
        elif state == "dealer":
            dealer_text += "\n🎩 Il banco sta giocando..."

        # =========================
        # 🔥 LAST ACTION
        # =========================
        action_text = ""
        if t.get("last_action"):
            action_text = f"\n🔥 {t['last_action']}"

        # =========================
        # 🎮 FINAL TEXT
        # =========================
        text = (
            "🎮 PVP BLACKJACK\n\n"
            f"📊 Stato: {state.upper()}\n\n"
            + players_text
            + "\n"
            + dealer_text
            + action_text
        )

        keyboard = table_buttons(t)

        # =========================
        # 📸 EDIT TEXT FIRST
        # =========================
        try:
            return await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard
            )
        except Exception as e:
            print("edit_text fail:", e)

        # =========================
        # 📸 FALLBACK CAPTION
        # =========================
        try:
            return await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=keyboard
            )
        except Exception as e:
            print("edit_caption fail:", e)

        print("❌ update_table FAILED COMPLETELY")  

# =========================
# BUTTONS (IMPORTANTISSIMO)
# =========================

def table_buttons(t):
    # ⚠️ usa SEMPRE l'id del tavolo reale, non una costante globale
    table_id = t.get("table_id", CURRENT_PVP_TABLE)
    state = t.get("state", "waiting")

    # =========================
    # 🎮 FASE LOBBY (WAITING)
    # =========================
    if state != "playing":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎯 ENTRA TAVOLO",
                    callback_data=f"pvp_join_{table_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 AVVIA PARTITA",
                    callback_data=f"pvp_start_{table_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 MENU",
                    callback_data="menu"
                )
            ]
        ])

    # =========================
    # 🎮 FASE GAME (PLAYING)
    # =========================
    players = t.get("players", [])
    turn_index = t.get("turn_index", 0)

    # 🔥 sicurezza: evita bottoni attivi se fuori turno
    is_valid_game = len(players) > 0 and turn_index < len(players)

    if not is_valid_game:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏠 MENU", callback_data="menu")
            ]
        ])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ CARTA",
                callback_data=f"pvp_hit_{table_id}"
            ),
            InlineKeyboardButton(
                "🖐️ STAI",
                callback_data=f"pvp_stand_{table_id}"
            )
        ],
        [
            InlineKeyboardButton("🏠 MENU", callback_data="menu")
        ]
    ])




# =========================
# STAND MP (FIXED)
# =========================
async def stand_mp(update, context):
    q = update.callback_query
    await q.answer()

    uid = str(update.effective_user.id)  # 👈 FIX: NO STRING

    table_id = user_tables.get(uid)
    t = tables.get(table_id)

    if not t:
        return await q.answer("Tavolo non trovato", show_alert=True)

    # 🛑 safety state
    if t.get("state") != "playing":
        return await q.answer("Partita non attiva", show_alert=True)

    order = t.get("order", [])
    idx = t.get("turn_index", 0)

    # 🛑 safety index
    if idx >= len(order):
        return

    # ⛔ check turno
    if order[idx] != uid:
        return await q.answer("⛔ Non è il tuo turno", show_alert=True)

    # 🎯 next turn
    t["turn_index"] += 1
    t["last_action"] = time.time()

    # 🔥 optional: log debug
    print(f"STAND -> user {uid} turn_index {t['turn_index']}")

    # 🎮 update safe
    try:
        await update_table(context.bot, t)
    except Exception as e:
        print("UPDATE ERROR:", e)


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
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(30, 37)],
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
# 🎡 AVVIA ROULETTE NUMERO
# =========================
async def bet_number_value(update, context):
    q = update.callback_query
    await q.answer()

    # sicurezza
    if "bet_number" not in context.user_data:
        return await q.answer(
            "🎯 Prima scegli un numero!",
            show_alert=True
        )

    # avvia la roulette in modalità numero
    return await roulette_spin(
        update,
        context,
        "number"
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
    chat_id = q.message.chat.id
    thread_id = q.message.message_thread_id

    await context.bot.send_animation(
        chat_id=chat_id,
        message_thread_id=thread_id,
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

    chat_id = q.message.chat.id
    thread_id = q.message.message_thread_id

    if thread_id is None:
        thread_id = getattr(q.message, "message_thread_id", None)

    await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=(
            "╔════════════════╗\n"
            f"{'🎉 VITTORIA  🎉' if victory else '   💀  PERSO  💀'}\n"
            "╚════════════════╝\n\n"
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

    chat_id = q.message.chat.id
    thread_id = q.message.message_thread_id

    await context.bot.send_animation(
        chat_id=chat_id,
        message_thread_id=thread_id,
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

    chat_id = q.message.chat.id
    thread_id = q.message.message_thread_id

    await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=(
            "╔════════════════╗\n"
            f"{'🎉 VITTORIA  🎉' if victory else '   💀  PERSO  💀'}\n"
            "╚════════════════╝\n\n"
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

    # 🔒 BLOCCO TOPIC
    if not in_casino_topic(update):
        return await q.answer(
            "🎰 Vai nel topic CASINO per giocare!",
            show_alert=True
        )

    await q.answer()

    try:
        await q.message.edit_caption(
            caption="🏠 MENU PRINCIPALE\n\nScegli un gioco:",
            reply_markup=main_menu_keyboard()
        )
    except:
        await q.message.edit_text(
            "🏠 MENU PRINCIPALE\n\nScegli un gioco:",
            reply_markup=main_menu_keyboard()
        )

#==========================
# FILEID PVP
#=========================
async def fileid(update, context):
    msg = update.effective_message

    target = msg.reply_to_message or msg

    # 📸 FOTO
    if target.photo:
        return await msg.reply_text(target.photo[-1].file_id)

    # 🎥 VIDEO
    if target.video:
        return await msg.reply_text(target.video.file_id)

    # 🎞️ ANIMAZIONE
    if target.animation:
        return await msg.reply_text(target.animation.file_id)

    # 📄 DOCUMENTO
    if target.document:
        return await msg.reply_text(target.document.file_id)

    return await msg.reply_text(
        "❌ Nessun file trovato.\nInvia o rispondi a un media."
    )
        

# =========================
# 🎮 CALLBACK ROUTER UNICO
# =========================

handlers = {
    "profile": profile,
    "bonus": daily_bonus,
    "shop": shop,
    "leaderboard": leaderboard,
    "blackjack": blackjack,
    "roulette": roulette,
    "pvp": pvp,
}

# =========================
# 📎 FILEID COMMAND (UNICO E CORRETTO)
# =========================
async def fileid(update, context):
    msg = update.message
    if not msg:
        return

    target = msg.reply_to_message or msg

    if target.photo:
        await msg.reply_text(f"📸 FOTO:\n{target.photo[-1].file_id}")
        return

    if target.video:
        await msg.reply_text(f"🎬 VIDEO:\n{target.video.file_id}")
        return

    if target.animation:
        await msg.reply_text(f"🎞️ GIF:\n{target.animation.file_id}")
        return

    if target.document:
        await msg.reply_text(f"📎 FILE:\n{target.document.file_id}")
        return

    if target.video_note:
        await msg.reply_text(f"🔵 VIDEO NOTE:\n{target.video_note.file_id}")
        return

    await msg.reply_text("❌ Rispondi a un media per ottenere il file_id")


# =========================
# 🎮 CALLBACK ROUTER FIXED
# =========================
async def cb_router(update, context):

    q = update.callback_query
    data = q.data
    uid = str(update.effective_user.id)

    print("🔥 CALLBACK DEBUG:", repr(data), "USER:", uid)

    # =====================
    # SAFE ANSWER
    # =====================
    try:
        await q.answer()
    except:
        pass

    # =====================
    # TOPIC CHECK
    # =====================
    ALLOWED_OUTSIDE_TOPIC = {"menu", "go_menu", "shop", "bonus"}

    if not in_casino_topic(update) and data not in ALLOWED_OUTSIDE_TOPIC:
        try:
            await q.answer("🎰 Vai nel topic CASINO per giocare!", show_alert=True)
        except:
            pass
        return

    # =====================
    # 🏠 MENU
    # =====================
    if data in ["menu", "go_menu"]:
        return await menu(update, context)

    # =====================
    # 🃏 SLOT MENU
    # =====================
    if data == "slot":
        return await slot(update, context)

    # =====================
    # 🃏 SLOT roulette
    # =====================
    if data == "roulette":
        return await roulette(update, context)

    # =====================
    # 🃏BLACKJACK MENU
    # =====================
    if data == "blackjack":
        return await blackjack(update, context)

    if data.startswith("blackjack_bet_"):
        try:
            amount = int(data.split("_")[-1])
        except:
            amount = 100

        return await blackjack_bet(update, context, amount)

    if data == "hit":
        return await hit(update, context)

    if data == "stand":
        return await stand(update, context)

    # =====================
    # 🎰 SLOT
    # =====================
    if data.startswith("spin_slot_"):
        try:
            bet = int(data.split("_")[-1])
        except:
            bet = 100

        slot_games[uid] = {"bet": bet}
        return await spin_slot(update, context)

    if data == "spin_slot":
        return await spin_slot(update, context)

    # =====================
    # 🎲 ROULETTE
    # =====================
    
    if data.startswith("num_"):
        return await select_number(update, context)

    if data == "bet_number":
        return await bet_number(update, context)

    if data == "bet_number_value":
        return await bet_number_value(update, context)

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

    # =====================
    # 🎮 PVP
    # =====================
    if data.startswith("pvp_join_"):
        table_id = data.split("_", 2)[2]
        return await pvp_join(update, context, table_id)

    if data.startswith("pvp_start_"):
        table_id = data.split("_", 2)[2]
        return await pvp_start(update, context, table_id)

    if data.startswith("pvp_hit_"):
        table_id = data.split("_", 2)[2]
        return await pvp_hit(update, context, table_id)

    if data.startswith("pvp_stand_"):
        table_id = data.split("_", 2)[2]
        return await pvp_stand(update, context, table_id)

    # =====================
    # BASE HANDLERS
    # =====================
    handlers = {
        "profile": profile,
        "bonus": daily_bonus,
        "shop": shop,
        "leaderboard": leaderboard,
        "pvp": pvp,
    }

    if data in handlers:
        return await handlers[data](update, context)

    # =====================
    # SHOP HANDLERS
    # =====================
    SHOP_HANDLERS = {
        "buy_vip": buy_vip,
        "buy_slotboost": buy_slotboost,
        "buy_bjpro": buy_bjpro,
    }

    if data in SHOP_HANDLERS:
        return await SHOP_HANDLERS[data](update, context)

    # =====================
    # FALLBACK
    # =====================
    print("❌ CALLBACK NON GESTITA:", data)
    return
# =========================
# 🧠 TEXT HANDLER
# =========================
async def text_handler(update, context):
    msg = update.message

    if not msg or not msg.text:
        return

    text = msg.text.lower().strip()

    if "bonus" in text:
        await msg.reply_text("🎁 Usa /bonus per ricevere le chips!")

    elif text == "slot":
        await msg.reply_text("🎰 Vai nella slot dal menu!")
# =========================
# 🧠 MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("casino", start))
    app.add_handler(CommandHandler("fileid", fileid))

    app.add_handler(CallbackQueryHandler(cb_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🟢 CASINO ONLINE FIXED")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
