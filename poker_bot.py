import random
import time
import json
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from treys import Card, Evaluator

# =========================
# TOKEN
# =========================
TOKEN = "INSERISCI_TOKEN_QUI"

# =========================
# GLOBALS
# =========================
games = {}
players = {}
SAVE_FILE = "players.json"

AUTHORIZED_GROUPS = [
    -1003664350829,
    -1002229066951,
]

OWNER_ID = 977247490

# =========================
# ACCESS CONTROL
# =========================
async def check_access(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    print(f"CHAT ID = {chat.id} | TYPE = {chat.type} | USER = {user.id}")

    if chat.type == "private":
        if user.id == OWNER_ID:
            return True
        await update.message.reply_text("⛔ NON AUTORIZZATO")
        return False

    if chat.type in ["group", "supergroup"]:
        if chat.id not in AUTHORIZED_GROUPS:
            await update.message.reply_text("⛔ GRUPPO NON AUTORIZZATO")
            return False

    return True


# =========================
# UTILITIES
# =========================
def create_deck():
    suits = ['s', 'h', 'd', 'c']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    deck = [r + s for r in ranks for s in suits]
    random.shuffle(deck)
    return deck


def current_player(game):
    return game["players"][game["turn_index"]]


# =========================
# KEYBOARD
# =========================
def game_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="join"),
            InlineKeyboardButton("🚪 ESCI", callback_data="leave"),
        ],
        [
            InlineKeyboardButton("🎲 START", callback_data="start"),
        ],
        [
            InlineKeyboardButton("➡️ NEXT", callback_data="next"),
        ],
        [
            InlineKeyboardButton("❌ FOLD", callback_data="fold"),
            InlineKeyboardButton("🔥 ALL-IN", callback_data="allin"),
        ],
    ])


# =========================
# COMMAND: POKER
# =========================
async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update):
        return

    chat_id = update.effective_chat.id

    if chat_id in games:
        await update.message.reply_text("⚠️ Partita già attiva")
        return

    games[chat_id] = {
        "players": [],
        "started": False,
        "deck": [],
        "community": [],
        "pot": 0,
        "turn_index": 0,
        "current_bet": 0,
    }

    await update.message.reply_text(
        "🃏 TEXAS HOLD'EM - LOBBY",
        reply_markup=game_keyboard()
    )


# =========================
# CALLBACK BUTTONS
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user

    if chat_id not in games:
        await query.edit_message_text("❌ Nessuna partita attiva")
        return

    game = games[chat_id]

    if query.data == "join":
        if game["started"]:
            return await query.answer("Partita già iniziata")

        if any(p["id"] == user.id for p in game["players"]):
            return await query.answer("Sei già dentro")

        game["players"].append({
            "id": user.id,
            "name": user.first_name,
            "chips": players.get(user.id, {}).get("chips", 5000),
            "hand": [],
            "folded": False,
        })

        await query.edit_message_text("✔️ Giocatore aggiunto")

    elif query.data == "leave":
        game["players"] = [p for p in game["players"] if p["id"] != user.id]
        await query.edit_message_text("🚪 Uscito")

    elif query.data == "start":
        if len(game["players"]) < 2:
            return await query.answer("Min 2 giocatori")

        game["started"] = True
        game["deck"] = create_deck()

        for p in game["players"]:
            p["hand"] = [game["deck"].pop(), game["deck"].pop()]

        await query.edit_message_text("🟢 Gioco iniziato")

    elif query.data == "next":
        await query.edit_message_text("➡️ Next fase")

    elif query.data == "fold":
        player = current_player(game)
        player["folded"] = True
        await query.edit_message_text("❌ Fold")

    elif query.data == "allin":
        player = current_player(game)
        game["pot"] += player["chips"]
        player["chips"] = 0
        await query.edit_message_text("🔥 ALL-IN")


# =========================
# COMMANDS BASE
# =========================
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Saldo OK")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Stats OK")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎁 Daily OK\n"
                                    "Torna domani!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 Help OK")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏆 Top OK")


# =========================
# APP (DOPO FUNZIONI!)
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("poker", poker))
app.add_handler(CommandHandler("saldo", saldo))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("daily", daily))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("top", top))
app.add_handler(CallbackQueryHandler(buttons))


# =========================
# MAIN
# =========================

def main():
    print("🃏 Poker Bot avviato!")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
