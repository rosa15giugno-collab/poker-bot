import telegram.request
telegram.request._httpxrequest.HTTPXRequest.TIMEOUT = 30

import random
import os

if os.environ.get("RENDER"):
    print("Render mode: single instance safe")
    
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from treys import Card, Evaluator

TOKEN = "8081123271:AAG4roWz5LRsD0SvxBoezCWG2TDvj_9zG50"
DATA_FILE = "partite.json"

GRUPPI_AUTORIZZATI = [
    -1003664350829,
    -1002229066951,
]

OWNER_ID = 977247490

evaluator = Evaluator()

# =========================
# SALVATAGGIO PARTITE
# =========================
def carica_partite():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def salva_partite(partite):
    with open(DATA_FILE, "w") as f:
        json.dump(partite, f)


partite = carica_partite()


# =========================
# CONTROLLO ACCESSO
# =========================
async def controllo_accesso(update: Update):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return user.id == OWNER_ID

    return chat.id in GRUPPI_AUTORIZZATI


# =========================
# MAZZO
# =========================
def crea_mazzo():
    semi = ['s', 'h', 'd', 'c']
    valori = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    mazzo = [v + s for v in valori for s in semi]
    random.shuffle(mazzo)
    return mazzo


def giocatori_attivi(partita):
    return [p for p in partita["giocatori"] if not p["fold"]]


def giocatore_corrente(partita):
    attivi = giocatori_attivi(partita)
    if not attivi:
        return None
    return attivi[partita["turno"] % len(attivi)]


def turno_successivo(partita):
    partita["turno"] += 1


# =========================
# TASTIERA
# =========================
def tastiera():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ ENTRA", callback_data="entra"),
            InlineKeyboardButton("🚪 ESCI", callback_data="esci"),
        ],
        [InlineKeyboardButton("🎲 AVVIA PARTITA", callback_data="start")],
        [
            InlineKeyboardButton("✔️ CHIAMA", callback_data="chiama"),
            InlineKeyboardButton("⬆️ RILANCIA", callback_data="rilancia"),
        ],
        [
            InlineKeyboardButton("❌ PASSA", callback_data="passa"),
            InlineKeyboardButton("🔥 ALL-IN", callback_data="allin"),
        ],
        [InlineKeyboardButton("➡️ PROSSIMO", callback_data="next")]
    ])


# =========================
# AVVIA LOBBY
# =========================
async def poker(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    salva_partite(partite)

    await update.message.reply_text("🃏 POKER CASINO ITALIANO", reply_markup=tastiera())


# =========================
# START BOT
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Casino Poker Online 🇮🇹")


# =========================
# CALLBACK BOTTONI
# =========================
async def bottoni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat_id = str(q.message.chat.id)
    user = q.from_user

    partita = partite.get(chat_id)
    if not partita:
        await q.edit_message_text("❌ Nessuna partita attiva")
        return

    # ================= ENTRA =================
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

        salva_partite(partite)
        await q.edit_message_text("✔️ Sei entrato nella partita")
        return

    # ================= ESCI =================
    if q.data == "esci":
        partita["giocatori"] = [g for g in partita["giocatori"] if g["id"] != user.id]
        salva_partite(partite)
        await q.edit_message_text("🚪 Sei uscito")
        return

    # ================= START =================
    if q.data == "start":
        if len(partita["giocatori"]) < 2:
            return await q.answer("Servono almeno 2 giocatori")

        partita["mazzo"] = crea_mazzo()
        partita["comune"] = []
        partita["piatto"] = 0
        partita["turno"] = 0
        partita["fase"] = "preflop"
        partita["puntata_corrente"] = 0

        for g in partita["giocatori"]:
            g["mano"] = [partita["mazzo"].pop(), partita["mazzo"].pop()]
            g["fold"] = False
            g["puntata"] = 0

        salva_partite(partite)
        await q.edit_message_text("🟢 Partita iniziata")
        return

    giocatore = giocatore_corrente(partita)

    if not giocatore or giocatore["id"] != user.id:
        return await q.answer("Non è il tuo turno")

    # ================= PASSA =================
    if q.data == "passa":
        giocatore["fold"] = True
        turno_successivo(partita)
        salva_partite(partite)
        await q.edit_message_text("❌ Hai passato")
        return

    # ================= CHIAMA =================
    if q.data == "chiama":
        diff = partita["puntata_corrente"] - giocatore["puntata"]

        if diff > 0:
            giocatore["chips"] -= diff
            giocatore["puntata"] += diff
            partita["piatto"] += diff

        turno_successivo(partita)
        salva_partite(partite)
        await q.edit_message_text("✔️ Hai chiamato")
        return

    # ================= RILANCIA =================
    if q.data == "rilancia":
        aumento = 100
        partita["puntata_corrente"] += aumento

        diff = partita["puntata_corrente"] - giocatore["puntata"]

        giocatore["chips"] -= diff
        giocatore["puntata"] += diff
        partita["piatto"] += diff

        turno_successivo(partita)
        salva_partite(partite)
        await q.edit_message_text("⬆️ Hai rilanciato")
        return

    # ================= ALL IN =================
    if q.data == "allin":
        partita["piatto"] += giocatore["chips"]
        giocatore["puntata"] += giocatore["chips"]
        giocatore["chips"] = 0

        turno_successivo(partita)
        salva_partite(partite)
        await q.edit_message_text("🔥 ALL-IN")
        return

    # ================= NEXT FASE =================
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

            miglior_punteggio = None
            vincitori = []

            for g in partita["giocatori"]:
                if g["fold"]:
                    continue

                mano = [Card.new(c) for c in g["mano"]]
                tavolo = [Card.new(c) for c in partita["comune"]]

                punteggio = evaluator.evaluate(tavolo, mano)

                if miglior_punteggio is None or punteggio < miglior_punteggio:
                    miglior_punteggio = punteggio
                    vincitori = [g]
                elif punteggio == miglior_punteggio:
                    vincitori.append(g)

            split = partita["piatto"] // len(vincitori)

            for v in vincitori:
                v["chips"] += split

            partita["fase"] = "lobby"
            partita["piatto"] = 0
            partita["turno"] = 0

            salva_partite(partite)

            await q.edit_message_text(
                "🏆 VINCITORI: " + ", ".join([v["nome"] for v in vincitori]) +
                f"\n💰 VINCITA: {split}"
            )
            return

        turno_successivo(partita)
        salva_partite(partite)
        await q.edit_message_text(f"Fase: {partita['fase']}")


# =========================
# MAIN
# =========================
def main():
    print("🔥 TEXAS HOLD'EM CASINO LIVE - SERVER ONLINE 🔥")

    app = ApplicationBuilder().token(TOKEN).build()

    # =========================
    # HANDLERS
    # =========================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("poker", poker))
    # app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CallbackQueryHandler(buttons))

    # =========================
    # SAFE POLLING (RENDER FIX)
    # =========================
    print("🟢 Avvio polling sicuro...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
     try:
        main()
    except Exception as e:
        print("CRASH:", e)
