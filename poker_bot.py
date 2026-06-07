import os
import json
import random
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# CONFIGURAZIONE
# =========================

TOKEN = os.getenv("CASINO_TOKEN")

if not TOKEN:
    raise ValueError("❌ CASINO_TOKEN mancante su Railway")

DATA_FILE = "casino_db.json"

print("🟢 CASINO BOT ONLINE PID:", os.getpid())

# =========================
# DATABASE
# =========================

def load():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def save(db):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f)
    os.replace(tmp, DATA_FILE)

db = load()
users = db.get("users", {})
db["users"] = users

def save_all():
    db["users"] = users
    save(db)

# =========================
# UTENTI
# =========================

def get_user(uid, name="Giocatore"):
    uid = str(uid)

    if uid not in users:
        users[uid] = {
            "name": name,
            "chips": 5000,
            "wins": 0,
            "losses": 0,
            "best_win": 0,
            "last_daily": 0
        }
        save_all()

    return users[uid]

# =========================
# MENU PRINCIPALE
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id, update.effective_user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎰 Slot", callback_data="slot")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="blackjack")],
        [InlineKeyboardButton("🎲 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
        [InlineKeyboardButton("🎁 Bonus Giornaliero", callback_data="bonus")],
        [InlineKeyboardButton("🏆 Classifica", callback_data="classifica")]
    ]

    await update.message.reply_text(
        "🎰 CASINO BOT PRO\nScegli un gioco:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# SALDO
# =========================

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)
    await update.message.reply_text(f"💰 Il tuo saldo attuale è: {u['chips']} chips", parse_mode="Markdown")

# =========================
# BONUS GIORNALIERO
# =========================

async def bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    now = int(time.time())
    if now - u["last_daily"] < 86400:
        return await update.message.reply_text("⏳ Hai già ritirato il bonus giornaliero oggi")

    reward = random.randint(500, 2500)
    u["chips"] += reward
    u["last_daily"] = now

    save_all()
    await update.message.reply_text(f"🎁 Hai ricevuto {reward} chips!", parse_mode="Markdown")

# =========================
# SLOT MACHINE
# =========================

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except Exception:
            pass

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida o chips insufficienti")

    u["chips"] -= bet

    symbols = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
    r = [random.choice(symbols) for _ in range(3)]

    win = 0
    if r[0] == r[1] == r[2]:
        win = bet * 10
    elif r[0] == r[1] or r[1] == r[2] or r[0] == r[2]:
        win = bet * 3

    u["chips"] += win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    if win > u["best_win"]:
        u["best_win"] = win

    save_all()

    await update.message.reply_text(
        f"🎰 SLOT MACHINE\n"
        f"{r[0]} | {r[1]} | {r[2]}\n"
        f"{'🎉 Hai vinto ' + str(win) + ' chips!' if win else '💀 Hai perso'}\n"
        f"💰 Saldo: {u['chips']}",
        parse_mode="Markdown"
    )

# =========================
# BLACKJACK
# =========================

def deck():
    suits = ["♠️", "♥️", "♦️", "♣️"]
    ranks = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
    d = [r + s for r in ranks for s in suits]
    random.shuffle(d)
    return d

def value(hand):
    vals = {
        "2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,
        "J":10,"Q":10,"K":10,"A":11
    }
    total = 0
    aces = 0

    for c in hand:
        r = c[:-2] if c[-2].isdigit() else c[:-1]
        total += vals.get(r, 0)
        if r == "A":
            aces += 1

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total

blackjack_games = {}

async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    u = get_user(uid, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            pass

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida o chips insufficienti")

    u["chips"] -= bet

    d = deck()
    player = [d.pop(), d.pop()]
    dealer = [d.pop(), d.pop()]

    blackjack_games[uid] = {
        "deck": d,
        "player": player,
        "dealer": dealer,
        "bet": bet
    }

    keyboard = [[
        InlineKeyboardButton("Carta (HIT)", callback_data="hit"),
        InlineKeyboardButton("Stai (STAND)", callback_data="stand")
    ]]

    await update.message.reply_text(
        f"🃏 BLACKJACK\n"
        f"TU: {player} ({value(player)})\n"
        f"MAZZIERE: [{dealer[0]}, ?]\n"
        f"💰 Puntata: {bet}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========================
# ROULETTE
# =========================

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id, update.effective_user.first_name)

    bet = 100
    if context.args:
        try:
            bet = int(context.args[0])
        except:
            pass

    if bet <= 0 or u["chips"] < bet:
        return await update.message.reply_text("❌ Puntata non valida o chips insufficienti")

    u["chips"] -= bet

    result = random.randint(0, 36)

    if result == 0:
        win = bet * 14
    elif result % 2 == 0:
        win = bet * 2
    else:
        win = 0

    u["chips"] += win

    if win > 0:
        u["wins"] += 1
    else:
        u["losses"] += 1

    if win > u["best_win"]:
        u["best_win"] = win

    save_all()

    await update.message.reply_text(
        f"🎲 ROULETTE\n"
        f"Numero uscito: {result}\n"
        f"{'🎉 Hai vinto ' + str(win) + ' chips!' if win else '💀 Hai perso'}\n"
        f"💰 Saldo: {u['chips']}",
        parse_mode="Markdown"
    )

# =========================
# CLASSIFICA
# =========================

async def classifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = sorted(users.items(), key=lambda x: x[1]["chips"], reverse=True)[:10]

    msg = "🏆 CLASSIFICA TOP 10\n\n"
    for i, (_, u) in enumerate(top_users, 1):
        msg += f"{i}. {u['name']} — {u['chips']} chips\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# =========================
# CALLBACK
# =========================

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    u = get_user(uid)

    data = q.data

    # Pulsanti menu
    if data == "slot":
        return await q.message.reply_text("🎰 Usa il comando: /slot 100")
    if data == "blackjack":
        return await q.message.reply_text("🃏 Usa il comando: /blackjack 100")
    if data == "roulette":
        return await q.message.reply_text("🎲 Usa il comando: /roulette 100")
    if data == "saldo":
        return await q.message.reply_text(f"💰 Il tuo saldo è: {u['chips']} chips")
    if data == "bonus":
        fake = Update(update.update_id, message=q.message)
        fake.effective_user = q.from_user
        return await bonus(fake, context)
    if data == "classifica":
        fake = Update(update.update_id, message=q.message)
        fake.effective_user = q.from_user
        return await classifica(fake, context)

    # Gestione Blackjack
    if uid not in blackjack_games:
        return

    game = blackjack_games[uid]
    d = game["deck"]
    p = game["player"]
    dealer = game["dealer"]
    bet = game["bet"]

    if data == "hit":
        if d:
            p.append(d.pop())

        if value(p) > 21:
            blackjack_games.pop(uid, None)
            u["losses"] += 1
            save_all()
            return await q.message.reply_text(
                f"TU: {p} ({value(p)})\n💥 Sballato!\n💰 Saldo: {u['chips']}",
                parse_mode="Markdown"
            )

        return await q.message.reply_text(
            f"TU: {p} ({value(p)})\nMAZZIERE: [{dealer[0]}, ?]"
        )

    if data == "stand":
        while value(dealer) < 17 and d:
            dealer.append(d.pop())

        pv = value(p)
        dv = value(dealer)

        if pv > 21:
            res = "💀 Hai perso (sballato)"
            u["losses"] += 1
        elif dv > 21 or pv > dv:
            win = bet * 2
            u["chips"] += win
            u["wins"] += 1
            res = f"🎉 Hai vinto {win} chips!"
        elif pv == dv:
            u["chips"] += bet
            res = "⚖️ Pareggio (puntata restituita)"
        else:
            u["losses"] += 1
            res = "💀 Hai perso"

        blackjack_games.pop(uid, None)
        save_all()

        return await q.message.reply_text(
            f"TU: {p} ({pv})\n"
            f"MAZZIERE: {dealer} ({dv})\n"
            f"{res}\n"
            f"💰 Saldo: {u['chips']}",
            parse_mode="Markdown"
        )

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("bonus", bonus))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("blackjack", blackjack_cmd))
    app.add_handler(CommandHandler("roulette", roulette))
    app.add_handler(CommandHandler("classifica", classifica))

    app.add_handler(CallbackQueryHandler(cb))

    print("🟢 BOT ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
