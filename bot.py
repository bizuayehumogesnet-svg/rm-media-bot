import os
from flask import Flask
from threading import Thread
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# የድር ሰርቨር ለ Render keep-alive
app = Flask('')

@app.route('/')
def home():
    return "Advanced RM Media Bot is running!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ሎግ ማስተካከያ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_FILE = "rm_media_advanced.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # ተጠቃሚዎችን እና ቋንቋቸውን መመዝገቢያ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            language TEXT DEFAULT 'am',
            subscribed INTEGER DEFAULT 1,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # የደንበኞች ግምገማ ሠንጠረዥ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            rating INTEGER,
            review_text TEXT,
            approved INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

init_db()

# የቋንቋ መዝገበ-ቃላት (Localization Dictionary)
TEXTS = {
    'am': {
        'welcome': "ሰላም **{name}**!\n\nእንኳን ወደ **RM Media | Result & Momentum** በደህና መጡ።\nመሪ ቃል: **ውጤት እና ፍጥነት 🚀**\n\nእባክዎ ከታች ካሉት አማራጮች የሚፈልጉትን አገልግሎት ይምረጡ:",
        'btn_design': "🖼 የ1 ሰዓት ፈጣን ዲዛይን (Fast Design)",
        'btn_video': "🎬 የቪዲዮ ፕሮዳክሽን (Video Production)",
        'btn_social': "📱 የሶሻል ሚዲያ አስተዳደር (Social Media)",
        'btn_portfolio': "🎨 የቀደሙ ስራዎች (Portfolio)",
        'btn_reviews': "⭐ የደንበኞች አስተያየት (Reviews)",
        'btn_settings': "⚙️ ቋንቋ / ቅንብር (Settings)",
        'back_menu': "🔙 ወደ ዋናው ምናሌ",
        'order_now': "📥 ትዕዛዝ ለመስጠት (Order Now)",
        'design_desc': "🖼 **የ1 ሰዓት ፈጣን ዲዛይን እና ታምብሌን**\n\n- የዩቲዩብ እና ቲክቶክ ታምብሌኖች\n- ማራኪ የሶሻል ሚዲያ ፖስተሮች\n\nትዕዛዝ ለመስጠት ከታች ያለውን ይጫኑ:",
        'video_desc': "🎬 **የቪዲዮ ፕሮዳክሽን እና ፕሮሞ ኤዲት**\n\n- የምረቃ እና የልደት ቪዲዮ ኤዲቲንግ\n- የንግድ ድርጅት ማስታወቂያ ቪዲዮዎች\n\nለማዘዝ ያግኙን:",
        'social_desc': "📱 **የሶሻል ሚዲያ አስተዳደር**\n\n- ሙሉ የገጽ (Page) አስተዳደር\n- የይዘት ስትራቴጂ እና የጊዜ ሰሌዳ",
        'portfolio_desc': "🎨 **የቀደሙ ስራዎች ማከማቻ (Portfolio Archive)**\n\nጥራት ያላቸውን ስራዎቻችንን በታች ባለው ቻናል ይመልከቱ:",
        'settings_title': "⚙️ **ቅንብር እና ቋንቋ ማስተካከያ (Settings)**\n\nየሚፈልጉትን ቋንቋ ይምረጡ / Choose your language:"
    },
    'en': {
        'welcome': "Hello **{name}**!\n\nWelcome to **RM Media | Result & Momentum**.\nMotto: **Result & Momentum 🚀**\n\nPlease select your desired service below:",
        'btn_design': "🖼 1-Hour Fast Design",
        'btn_video': "🎬 Video Production & Editing",
        'btn_social': "📱 Social Media Management",
        'btn_portfolio': "🎨 Portfolio Showcase",
        'btn_reviews': "⭐ Client Reviews",
        'btn_settings': "⚙️ Language / Settings",
        'back_menu': "🔙 Back to Main Menu",
        'order_now': "📥 Order Now",
        'design_desc': "🖼 **1-Hour Fast Design & Thumbnails**\n\n- YouTube & TikTok Thumbnails\n- Attractive Social Media Posters\n\nClick below to order:",
        'video_desc': "🎬 **Video Production & Promo Edit**\n\n- Graduation & Birthday Video Editing\n- Commercial Promo Videos\n\nContact us to order:",
        'social_desc': "📱 **Social Media Management**\n\n- Full Page Management\n- Content Strategy & Scheduling",
        'portfolio_desc': "🎨 **Official Portfolio Archive**\n\nCheck out our high-quality works in our channel below:",
        'settings_title': "⚙️ **Settings & Language**\n\nChoose your preferred language:"
    }
}

def get_user_lang(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 'am'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)",
        (user.id, user.full_name),
    )
    conn.commit()
    conn.close()

    lang = get_user_lang(user.id)
    t = TEXTS[lang]

    keyboard = [
        [InlineKeyboardButton(t['btn_design'], callback_data="serv_design")],
        [InlineKeyboardButton(t['btn_video'], callback_data="serv_video")],
        [InlineKeyboardButton(t['btn_social'], callback_data="serv_social")],
        [InlineKeyboardButton(t['btn_portfolio'], callback_data="serv_portfolio")],
        [InlineKeyboardButton(t['btn_reviews'], callback_data="show_reviews")],
        [InlineKeyboardButton(t['btn_settings'], callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = t['welcome'].format(name=user.first_name)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    if data == "serv_design":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t['order_now'], url="https://t.me/Respect_for_God")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['design_desc'], reply_markup=markup, parse_mode="Markdown")

    elif data == "serv_video":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t['order_now'], url="https://t.me/Respect_for_God")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['video_desc'], reply_markup=markup, parse_mode="Markdown")

    elif data == "serv_social":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t['order_now'], url="https://t.me/Respect_for_God")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['social_desc'], reply_markup=markup, parse_mode="Markdown")

    elif data == "serv_portfolio":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 ቻናሉን ይጎብኙ (Visit Channel)", url="https://t.me/RM_Real_Works_Ethiopia")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['portfolio_desc'], reply_markup=markup, parse_mode="Markdown")

    elif data == "show_reviews":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, rating, review_text FROM reviews WHERE approved = 1 ORDER BY id DESC LIMIT 3")
        rows = cursor.fetchall()
        conn.close()

        rev_text = "⭐ **Client Testimonials / የደንበኞች አስተያየት** ⭐\n\n"
        for name, rating, r_text in rows:
            stars = "⭐" * rating
            rev_text += f"👤 **{name}** {stars}\n💬 \"{r_text}\"\n\n"

        markup = InlineKeyboardMarkup([[InlineKeyboardButton(t['back_menu'], callback_data="main_menu")]])
        await query.edit_message_text(rev_text, reply_markup=markup, parse_mode="Markdown")

    elif data == "settings":
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            ],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['settings_title'], reply_markup=markup, parse_mode="Markdown")

    elif data == "lang_am":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = 'am' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await start(update, context)

    elif data == "lang_en":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = 'en' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await start(update, context)

    elif data == "main_menu":
        await start(update, context)

def main():
    keep_alive()
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Advanced RM Media Bot is up and running 24/7...")
    app.run_polling()

if __name__ == "__main__":
    main()
