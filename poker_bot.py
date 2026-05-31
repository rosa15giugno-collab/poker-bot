import random
import time
import json
import os

from telegram import Update
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from treys import Card, Evaluator

# =========================
# TOKEN
# =========================
TOKEN = "8081123271:AAE347XgC8S0nsnujYMNnXdXwjARkJZHXN8"

# =========================
# GLOBALS
# =========================
games = {}
players = {}

SAVE_FILE = "players.json"

AUTHORIZED_GROUPS = [
    -1003664350829, # ID SCACCO MATTO
    -1002229066951, # ID MONOPOLI
]

OWNER_ID = 977247490

async def check_access(update):
    chat = update.effective_chat
    user = update.effective_user

    print(
        f"CHAT ID = {CHAT.ID} | TYPE = {chat.type} | USER = {user.id}"
    )

    # Chat privata
    if chat.type == "private":
        if user.id == OWNER_ID:
            return True

        await update.message.reply_text(
            "⛔ NON SEI AUTORIZZATO A USARE QUESTO BOT."
        )
        return False
    
    # Gruppi
    if chat.type in ["group", "supergroup"]:
        if chat.id not in AUTHORIZED_GROUPS:
            await update.message.reply_text(
                "⛔ QUESTO GRUPPO NON E' AUTORIZZATO."
            )
            return False

    return True

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_access(update):
        return
    
    user = update.effective_user

    if user.id not in players:

        players[user.id] = {
            "name": user.first_name,
            "chips": 5000,
            "wins": 0,
            "losses": 0,
            "games": 0,
            "last_daily": 0
        }

        save_balances ()

    now = time.time()

    last_daily = players[user.id].get("last_daily", 0)

    cooldown = 86400

    if now - last_daily < cooldown:

        remaining = int(cooldown - (now - last_daily))

        hours = remaining // 3600
        minutes = (remaining % 3600) // 60

        await update.message.reply_text(
            f"⏳ Hai già preso il daily!\n\n"
            f"Torna tra {hours}h {minutes}m."
        )
        return

    reward = 1000

    players[user.id]["chips"] += reward
    players[user.id]["last_daily"] = now

    save_balances()

    await update.message.reply_text(
        f"🎁 DAILY REWARD\n\n"
        f"💰 Hai ricevuto {reward} chips!"
    )

def load_balances():
    global players

    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            players = json.load(f)

            players = {
                int(k): v
                for k, v in players.items()
            }


def save_balances():
    with open(SAVE_FILE, "w") as f:
        json.dump(players, f)

evaluator = Evaluator()

suits = ['s', 'h', 'd', 'c']
ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']

# =========================
# DECK
# =========================
def create_deck():
    deck = [rank + suit for rank in ranks for suit in suits]
    random.shuffle(deck)
    return deck


def pretty(card):

    suits = {
        "s": "♠️",
        "h": "♥️",
        "d": "♦️",
        "c": "♣️"
    }

    rank = card[:-1].upper()
    suit = suits[card[-1]]

    return f"{suit}{rank}"


def current_player(game):
    return game["players"][game["turn_index"]]


def next_turn(game):
    game["turn_index"] += 1

    if game["turn_index"] >= len(game["players"]):
        game["turn_index"] = 0


# =========================
# COMMUNITY CARDS
# =========================
def show_community(game):
    if not game["community"]:
        return "Nessuna"

    return " ".join(pretty(card) for card in game["community"])


# =========================
# GAME STATUS
# =========================
def game_text(game):
    text = "🃏 TEXAS HOLD'EM\n\n"

    text += f"🏦 Pot: {game['pot']} chips\n"
    text += f"🎴 Tavolo: {show_community(game)}\n"
    text += f"📍 Fase: {game['phase']}\n\n"

    for p in game["players"]:
        status = ""

        if p.get("folded"):
            status = " ❌ Passo"

        text += f"• {p['name']} - {p['chips']} chips{status}\n"

    text += f"\n🎮 Turno: {current_player(game)['name']}"

    return text


# =========================
# KEYBOARD ITALIANA
# =========================
def game_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="join"),
            InlineKeyboardButton("🚪 ESCI", callback_data="leave"),
        ],
        [
            InlineKeyboardButton("🎲 INIZIA", callback_data="start"),
            InlineKeyboardButton("🃏 CONTINUA", callback_data="next"),
        ],
        [
            InlineKeyboardButton("💵 Punta", callback_data="bet"),
            InlineKeyboardButton("📞 VEDO", callback_data="call"),
        ],
        [
            InlineKeyboardButton("👀 Check", callback_data="check"),
            InlineKeyboardButton("❌ PASSO", callback_data="fold"),
        ],
        [
            InlineKeyboardButton("🔥 ALL-IN", callback_data="allin"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# POKER COMMAND
# =========================
async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_access(update):
        return

    chat_id = update.effective_chat.id

    if chat_id in games:
        await update.message.reply_text("⚠️ Partita già attiva.")
        return

    games[chat_id] = {
        "players": [],
        "started": False,
        "deck": [],
        "community": [],
        "pot": 0,
        "phase": "lobby",
        "turn_index": 0,
        "current_bet": 0,
    }

    await update.message.reply_text(
        "🃏 TEXAS HOLD'EM\n\nPremi ENTRA per unirti al tavoro.",
        reply_markup=game_keyboard()
    )


# =========================
# BUTTONS
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user

    if chat_id not in games:
        await query.edit_message_text("❌ Partita non trovata.")
        return

    game = games[chat_id]

    # =========================
    # JOIN
    # =========================
    if query.data == "join":

        if game["started"]:
            await query.answer("Partita già iniziata!")
            return

        for p in game["players"]:
            if p["id"] == user.id:
                await query.answer("Sei già dentro!")
                return

        if user.id not in players:
            players[user.id] = {
                "name": user.first_name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "games": 0,
                "last_daily": 0
            }

        if user.id not in players:

            players[user.id] = {
                "name": user.first_name,
                "chips": 5000,
                "wins": 0,
                "losses": 0,
                "games": 0,
                "last_daily": 0
    }

        if "chips" not in players[user.id]:
            players[user.id]["chips"] = 5000

        if "wins" not in players[user.id]:
            players[user.id]["wins"] = 0

        if "losses" not in players[user.id]:
            players[user.id]["losses"] = 0

        if "games" not in players[user.id]:
            players[user.id]["games"] = 0

        if "last_daily" not in players[user.id]:
            players[user.id]["last_daily"] = 0

        save_balances()


        game["players"].append({
            "id": user.id,
            "name": user.first_name,
            "chips": players[user.id].get("chips", 5000),
            "hand": [],
            "folded": False,
        })

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # LEAVE
    # =========================
    elif query.data == "leave":

        game["players"] = [
            p for p in game["players"]
            if p["id"] != user.id
        ]

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # START
    # =========================
    elif query.data == "start":

        if game["started"]:
            await query.answer("Partita già iniziata!")
            return

        if len(game["players"]) < 2:
            await query.answer("Servono almeno 2 giocatori!")
            return

        game["started"] = True
        game["deck"] = create_deck()
        game["phase"] = "preflop"
        game["pot"] = 0
        game["community"] = []
        game["turn_index"] = 0

        for player in game["players"]:
            player["folded"] = False
            player["hand"] = [
                game["deck"].pop(),
                game["deck"].pop()
            ]

        text = (
            "🟢━━━━━━━━━━━━━━━━🟢\n"
            "♠️ TEXAS HOLD'EM ♥️\n"
            "🟢━━━━━━━━━━━━━━━━🟢\n\n"
        )

        community = " ".join([pretty(card) for card in game["community"]])

        if community:
            text += f"🃏 Tavolo: {community}\n\n"

        text += f"💰 Pot: {game['pot']} chips\n\n"


        for player in game["players"]:
            hand = " ".join(pretty(c) for c in player["hand"])
            text += f"{player['name']}: {hand}\n"

        text += (
            f"👤 {player['name']}\n"
            f"💰 Chips: {player['chips']}\n"
            f"🃏 {pretty(player['hand'][0])}  {pretty(player['hand'][1])}\n\n"
        )

        await query.edit_message_text(
            text,
            reply_markup=game_keyboard()
        )

    # =========================
    # NEXT PHASE
    # =========================
    elif query.data == "next":

        if game["phase"] == "preflop":
            game["community"] = [
                game["deck"].pop(),
                game["deck"].pop(),
                game["deck"].pop(),
            ]
            game["phase"] = "flop"

        elif game["phase"] == "flop":
            game["community"].append(game["deck"].pop())
            game["phase"] = "turn"

        elif game["phase"] == "turn":
            game["community"].append(game["deck"].pop())
            game["phase"] = "river"

        elif game["phase"] == "river":
            await showdown(query, game)
            return

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # BET
    # =========================
    elif query.data == "bet":

        player = current_player(game)

        if player["id"] != user.id:
            await query.answer("Non è il tuo turno!")
            return

        amount = 100

        if player["chips"] < amount:
            await query.answer("Non hai abbastanza chips!")
            return

        player["chips"] -= amount
        game["pot"] += amount
        game["current_bet"] = amount

        next_turn(game)

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # CALL
    # =========================
    elif query.data == "call":

        player = current_player(game)

        if player["id"] != user.id:
            await query.answer("Non è il tuo turno!")
            return

        amount = game["current_bet"]

        if player["chips"] < amount:
            amount = player["chips"]

        player["chips"] -= amount
        game["pot"] += amount

        next_turn(game)

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # CHECK
    # =========================
    elif query.data == "check":

        player = current_player(game)

        if player["id"] != user.id:
            await query.answer("Non è il tuo turno!")
            return

        next_turn(game)

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # FOLD
    # =========================
    elif query.data == "fold":

        player = current_player(game)

        if player["id"] != user.id:
            await query.answer("Non è il tuo turno!")
            return

        player["folded"] = True

        active_players = [
            p for p in game["players"]
            if not p["folded"]
        ]

        if len(active_players) == 1:
            winner = active_players[0]
            winner["chips"] += game["pot"]

            await query.edit_message_text(
                f"🏆 {winner['name']} vince il piatto di {game['pot']} chips!"
            )

            del games[chat_id]
            return

        next_turn(game)

        await query.edit_message_text(
            game_text(game),
            reply_markup=game_keyboard()
        )

    # =========================
    # ALL IN
    # =========================
    elif query.data == "allin":

        player = current_player(game)

        if player["id"] != user.id:
            await query.answer("Non è il tuo turno!")
            return

        amount = player["chips"]

        player["chips"] = 0
        game["pot"] += amount
        game["current_bet"] = amount

        next_turn(game)

        await query.edit_message_text(
            f"🔥 {player['name']} va ALL-IN!\n\n" + game_text(game),
            reply_markup=game_keyboard()
        )


# =========================
# SHOWDOWN
# =========================
async def showdown(query, game):

    board = [Card.new(c) for c in game["community"]]

    winner = None
    best_score = 999999

    text = "♠️ SHOWDOWN FINALE ♣️\n\n"

    for player in game["players"]:

        if player["id"] != winner [id]:
            players[player["id"]]["losses"] += 1
            players[player["id"]]["games"] += 1

        if player["folded"]:
            continue

        hand = [Card.new(c) for c in player["hand"]]

        score = evaluator.evaluate(board, hand)

        cards = " ".join(pretty(c) for c in player["hand"])

        text += f"{player['name']}: {cards}\n"

        if score < best_score:
            best_score = score
            winner = player

    winner["chips"] += game["pot"]
    players[winner["id"]]["chips"] = winner ["chips"]
    players[winner["id"]]["wins"] += 1
    players[winner["id"]]["games"] += 1
    balances[winner["id"]] = winner["chips"]
    save_balances()

    text += f"\n🏆 Vince: {winner['name']}!"
    text += f"\n💰 Piato vinto: {game['pot']} chips"

    save_balances()

    await query.edit_message_text(text)


# =========================
# SALDO
# =========================
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_access(update):
        return
    
    user = update.effective_user

    if user.id not in players:
        players[user.id] =  {
            "name": user.first_name,
            "chips": 5000,
            "wins": 0,
            "losses": 0,
            "games": 0,
            "lat_daily": 0
        }

        save_balances()

    await update.message.reply_text(
        f"🪙 {user.first_name}, hai {players[user.id]['chips']} chips."
    )


# =========================
# HELP
# =========================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_access(update):
        return

    text = (
        "🃏 COMANDI POKER\n\n"
        "/poker → crea tavolo\n"
        "/saldo → mostra chips\n"
        "/help → aiuto\n"
    )

    await update.message.reply_text(text)


# =========================
# APP
# =========================

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_access(update):
        return

    if not players:
        await update.message.reply_text("Nessun giocatore registrato.")
        return

    sorted_players = sorted(
        players.items(),
        key=lambda x: x[1]["chips"],
        reverse=True
    )

    text = "🏆 CLASSIFICA CHIPS\n\n"

    for i, (user_id, data) in enumerate(sorted_players[:10], start=1):
        name = data["name"]
        chips = data["chips"]
        text += f"{i}. {name} - {chips} 💰\n"

    await update.message.reply_text(text)

load_balances()

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_access(update):
        return

    user = update.effective_user

    if user.id not in players:

        players[user.id] = {
            "name": user.first_name,
            "chips": 5000,
            "wins": 0,
            "losses": 0,
            "games": 0,
            "last_daily": 0
        }

        save_balances()

    data = players[user.id]

    games = data["games"]
    wins = data["wins"]

    if games > 0:
        winrate = round((wins / games) * 100)
    else:
        winrate = 0

    text = (
        f"📊 STATISTICHE\n\n"
        f"👤 {data['name']}\n"
        f"💰 Chips: {data['chips']}\n"
        f"🏆 Vittorie: {data['wins']}\n"
        f"❌ Sconfitte: {data['losses']}\n"
        f"🎮 Partite: {data['games']}\n"
        f"📈 Winrate: {winrate}%"
    )

    await update.message.reply_text(text)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("poker", poker))
app.add_handler(CommandHandler("saldo", saldo))
app.add_handler(CommandHandler("top", top))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("daily", daily))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CallbackQueryHandler(buttons))

def main():
    print("🃏 Poker Bot avviato!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
