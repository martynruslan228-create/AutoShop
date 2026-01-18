import os
import asyncio
import logging
import threading
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes,
    ConversationHandler, filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = "8076199435:AAGSWx8kZnZTno2R-_7bxiIcMwHksWGtiyI"
CHANNEL_ID = "@autochopOdessa"

(
    BRAND, MODEL, YEAR, ENGINE, FUEL, GEARBOX, DRIVE,
    DESC, PRICE, PHOTO, DISTRICT, CITY, TG_CONTACT,
    PHONE, WAIT_EDIT_VALUE
) = range(15)

# ---------- DATABASE ----------
def init_db():
    with sqlite3.connect("ads.db") as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            msg_id INTEGER,
            brand TEXT,
            model TEXT,
            year TEXT,
            price TEXT,
            desc TEXT,
            full_text TEXT,
            photo_ids TEXT
        )
        """)

init_db()

# ---------- UI ----------
MAIN_KB = ReplyKeyboardMarkup(
    [["➕ Нове оголошення"], ["🗂 Мої оголошення"]],
    resize_keyboard=True
)

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Головне меню:", reply_markup=MAIN_KB)
    return ConversationHandler.END

# ---------- MY ADS ----------
async def my_ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with sqlite3.connect("ads.db") as conn:
        ads = conn.execute(
            "SELECT id, brand, model, price FROM ads WHERE user_id=?",
            (user_id,)
        ).fetchall()

    if not ads:
        await update.message.reply_text("❌ У вас ще немає оголошень", reply_markup=MAIN_KB)
        return ConversationHandler.END

    for ad in ads:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Редагувати", callback_query_data=f"edit_{ad[0]}"),
                InlineKeyboardButton("🗑 Видалити", callback_query_data=f"del_{ad[0]}")
            ]
        ])
        await update.message.reply_text(
            f"🚗 {ad[1]} {ad[2]} — {ad[3]}$",
            reply_markup=kb
        )

    return ConversationHandler.END

# ---------- CALLBACKS ----------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("del_"):
        ad_id = data.split("_")[1]
        with sqlite3.connect("ads.db") as conn:
            msg_id = conn.execute(
                "SELECT msg_id FROM ads WHERE id=?",
                (ad_id,)
            ).fetchone()
            if msg_id:
                try:
                    await context.bot.delete_message(CHANNEL_ID, msg_id[0])
                except:
                    pass
            conn.execute("DELETE FROM ads WHERE id=?", (ad_id,))

        await q.edit_message_text("✅ Оголошення видалено")

    elif data.startswith("edit_"):
        ad_id = data.split("_")[1]
        context.user_data["edit_ad"] = ad_id
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Ціна", callback_query_data="field_price")],
            [InlineKeyboardButton("📝 Опис", callback_query_data="field_desc")]
        ])
        await q.edit_message_text("Що змінюємо?", reply_markup=kb)

    elif data.startswith("field_"):
        field = data.split("_")[1]
        context.user_data["edit_field"] = field
        await q.message.reply_text(
            "Введіть нове значення:",
            reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True)
        )
        return WAIT_EDIT_VALUE

# ---------- SAVE EDIT ----------
async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_val = update.message.text
    ad_id = context.user_data["edit_ad"]
    field = context.user_data["edit_field"]

    with sqlite3.connect("ads.db") as conn:
        msg_id, full_text = conn.execute(
            "SELECT msg_id, full_text FROM ads WHERE id=?",
            (ad_id,)
        ).fetchone()

        if field == "price":
            full_text = "\n".join(
                "💰 Ціна: " + new_val + "$" if "💰 Ціна" in l else l
                for l in full_text.split("\n")
            )
        else:
            full_text = full_text.split("📝 Опис:")[0] + f"📝 Опис:\n{new_val}"

        await context.bot.edit_message_text(
            full_text, CHANNEL_ID, msg_id
        )

        conn.execute(
            f"UPDATE ads SET {field}=?, full_text=? WHERE id=?",
            (new_val, full_text, ad_id)
        )

    await update.message.reply_text("✅ Оновлено", reply_markup=MAIN_KB)
    return ConversationHandler.END

# ---------- NEW AD ----------
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Марка авто:", reply_markup=ReplyKeyboardRemove())
    return BRAND

async def get_brand(u, c): c.user_data["brand"]=u.message.text; await u.message.reply_text("Модель:"); return MODEL
async def get_model(u, c): c.user_data["model"]=u.message.text; await u.message.reply_text("Рік:"); return YEAR
async def get_year(u, c): c.user_data["year"]=u.message.text; await u.message.reply_text("Обʼєм:"); return ENGINE
async def get_engine(u, c): c.user_data["engine"]=u.message.text; await u.message.reply_text("Опис:"); return DESC
async def get_desc(u, c): c.user_data["desc"]=u.message.text; await u.message.reply_text("Ціна $:"); return PRICE

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    text = (
        f"🚗 {ud['brand']} {ud['model']} ({ud['year']})\n"
        f"📝 {ud['desc']}\n"
        f"💰 Ціна: {ud['price']}$"
    )

    msg = await context.bot.send_message(CHANNEL_ID, text)

    with sqlite3.connect("ads.db") as conn:
        conn.execute(
            "INSERT INTO ads (user_id,msg_id,brand,model,year,price,desc,full_text,photo_ids)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (update.effective_user.id, msg.message_id,
             ud['brand'], ud['model'], ud['year'],
             ud['price'], ud['desc'], text, "")
        )

    await update.message.reply_text("✅ Опубліковано", reply_markup=MAIN_KB)
    return ConversationHandler.END

# ---------- MAIN ----------
async def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad)],
        states={
            BRAND: [MessageHandler(filters.TEXT, get_brand)],
            MODEL: [MessageHandler(filters.TEXT, get_model)],
            YEAR: [MessageHandler(filters.TEXT, get_year)],
            ENGINE: [MessageHandler(filters.TEXT, get_engine)],
            DESC: [MessageHandler(filters.TEXT, get_desc)],
            PRICE: [MessageHandler(filters.TEXT, finish_ad)],
            WAIT_EDIT_VALUE: [MessageHandler(filters.TEXT, save_edit)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), start)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🗂 Мої оголошення$"), my_ads_menu))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(callbacks))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
