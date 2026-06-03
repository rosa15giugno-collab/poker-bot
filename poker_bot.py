import random
import os
import json
import threading
import traceback

from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from treys import Card, Evaluator


# =========================
# CONFIG
# =========================
TOKEN = "8081123271:AAG4roWz5LRsD0SvxBoezCWG2TDvj_9zG50"

DATA_FILE = "partite.json"

GRUPPI_AUTORIZZATI = [
    -1003664350829,
    -1002229066951,
]

OWNER_ID = 977247490

evaluator = Evaluator()

partite = {}


# =========================
# WEB SERVER (Render keep alive)
# =========================
def run_web():
    port = int(os.environ.get("PORT", 10000))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


# =========================
# UTILS
# =========================
def crea_mazzo():
    semi = ['s', 'h', 'd', 'c']
    valori = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    mazzo = [v + s for v in valori for s in semi]
    random.shuffle(mazzo)
    return mazzo


def giocatore_corrente(partita):
    attivi = [g for g in partita["giocatori"] if not g["fold"]]
    if not attivi:
        return None
    return attivi[partita["turno"] % len(attivi)]


def turno_successivo(partita):
    partita["turno"] += 1


# =========================
# KEYBOARD
# =========================
def tastiera():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="entra"),
            InlineKeyboardButton("🚪 ESCI", callback_data="esci"),
        ],
        [InlineKeyboardButton("🎲 START", callback_data="start")],
        [
            InlineKeyboardButton("❌ PASSA", callback_data="passa"),
            InlineKeyboardButton("✔️ CHIAMA", callback_data="chiama"),
        ],
        [
            InlineKeyboardButton("⬆️ RILANCIA", callback_data="rilancia"),
            InlineKeyboardButton("🔥 ALL-IN", callback_data="allin"),
        ],
        [InlineKeyboardButton("➡️ NEXT", callback_data="next")]
    ])


# =========================
# ACCESS
# =========================
async def check_access(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return user.id == OWNER_ID

    return chat.id in GRUPPI_AUTORIZZATI


# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Poker Bot Online")


async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update):
        await update.message.reply_text("⛔ NON AUTORIZZATO")
        return

    chat_id = str(update.effective_chat.id)

    if chat_id in partite:
        await update.message.reply_text("⚠️ Partita già attiva")
        return

    partite[chat_id] = {
        "giocatori": [],
        "mazzo": [],
        "comune": [],
        "piatto": 0,
        "turno": 0,
        "fase": "lobby",
        "puntata_corrente": 0
    }

    await update.message.reply_text("🃏 POKER LOBBY", reply_markup=tastiera())


# =========================
# CALLBACK
# =========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat_id = str(q.message.chat.id)
    user = q.from_user

    partita = partite.get(chat_id)

    if not partita:
        await q.edit_message_text("❌ Nessuna partita attiva")
        return

    # JOIN
    if q.data == "entra":
        if any(p["id"] == user.id for p in partita["giocatori"]):
            return await q.answer("Sei già dentro")

        partita["giocatori"].append({
            "id": user.id,
            "nome": user.first_name,
            "chips": 5000,
            "mano": [],
            "fold": False,
            "puntata": 0
        })

        await q.edit_message_text("✔️ Entrato")
        return

    # LEAVE
    if q.data == "esci":
        partita["giocatori"] = [g for g in partita["giocatori"] if g["id"] != user.id]
        await q.edit_message_text("🚪 Uscito")
        return

    # START
    if q.data == "start":
        if len(partita["giocatori"]) < 2:
            return await q.answer("Min 2 giocatori")

        partita["mazzo"] = crea_mazzo()
        partita["fase"] = "preflop"

        for g in partita["giocatori"]:
            g["mano"] = [partita["mazzo"].pop(), partita["mazzo"].pop()]
            g["fold"] = False
            g["puntata"] = 0

        await q.edit_message_text("🟢 Partita iniziata")
        return

    player = giocatore_corrente(partita)

    if not player or player["id"] != user.id:
        return await q.answer("Non è il tuo turno")

    # FOLD
    if q.data == "passa":
        player["fold"] = True
        turno_successivo(partita)
        await q.edit_message_text("❌ Fold")
        return

    # CALL
    if q.data == "chiama":
        diff = partita["puntata_corrente"] - player["puntata"]
        if diff > 0:
            player["chips"] -= diff
            player["puntata"] += diff
            partita["piatto"] += diff

        turno_successivo(partita)
        await q.edit_message_text("✔️ Chiama")
        return

    # RAISE
    if q.data == "rilancia":
        raise_amount = 100
        partita["puntata_corrente"] += raise_amount

        diff = partita["puntata_corrente"] - player["puntata"]

        player["chips"] -= diff
        player["puntata"] += diff
        partita["piatto"] += diff

        turno_successivo(partita)
        await q.edit_message_text("⬆️ Rilancio")
        return

    # ALL IN
    if q.data == "allin":
        partita["piatto"] += player["chips"]
        player["chips"] = 0
        turno_successivo(partita)
        await q.edit_message_text("🔥 ALL-IN")
        return

    # NEXT
    if q.data == "next":
        if partita["fase"] == "preflop":
            partita["comune"] = [partita["mazzo"].pop() for _ in range(3)]
            partita["fase"] = "flop"

        elif partita["fase"] == "flop":
            partita["comune"].append(partita["mazzo"].pop())
            partita["fase"] = "turn"

        elif partita["fase"] == "turn":
            partita["comune"].append(partita["mazzo"].pop())
            partita["fase"] = "river"

        elif partita["fase"] == "river":
            winner = max(partita["giocatori"], key=lambda g: len(g["mano"]))
            winner["chips"] += partita["piatto"]

            partita["piatto"] = 0
            partita["fase"] = "lobby"

            await q.edit_message_text(f"🏆 Vince {winner['nome']}")
            return

        turno_successivo(partita)
        await q.edit_message_text(f"Fase: {partita['fase']}")


# =========================
# MAIN (FIX DEFINITIVO RENDER)
# =========================
def main():
    print("🃏 BOT AVVIATO")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("poker", poker))
    app.add_handler(CallbackQueryHandler(buttons))

    threading.Thread(target=run_web, daemon=True).start()

    # IMPORTANTISSIMO: evita conflitti Render
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("CRASH:")
        traceback.print_exc()
