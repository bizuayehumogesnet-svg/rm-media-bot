import os
import logging
import aiosqlite
from flask import Flask
from threading import Thread
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Render Keep-Alive Server
app = Flask('')

@app.route('/')
def home():
    return "RM Media Fast 10x Sales Bot is Live!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_FILE = "rm_media_advanced.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone_number TEXT,
                language TEXT DEFAULT 'am',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                full_name TEXT,
                rating INTEGER,
                review_text TEXT,
                approved INTEGER DEFAULT 1
            )
        """)
        await db.commit()

TEXTS = {
    'am': {
        'welcome': (
            "🔥 **የንግድዎን ሽያጭ እና እይታ በጥራት ያሳድጉ!** 🔥\n\n"
            "እንኳን ወደ **RM Media | Result & Momentum** በደህና መጡ። 🚀\n\n"
            "📞 **የቀጥታ መስመር:** +251967830825\n"
            "💬 **የባለሙያ ምክክር:** [ከዋና አዘጋጁ ጋር ይወያዩ](https://t.me/Respect_for_God)\n"
            "🎨 **ፖርትፎሊዮ:** [የሰራናቸውን ስራዎች ይመልከቱ](https://t.me/Real_Works_Ethiopia)\n\n"
            "👇 *እባክዎን ከታች ከሚገኙት አማራጮች የሚፈልጉትን ይምረጡ:*"
        ),
        'phone_prompt': "📱 እባክዎን ስልክ ቁጥርዎን ለማጋራት ከታች ያለውን አዝራር ይጫኑ (ለቀላል ግንኙነት):",
        'phone_btn': "📲 ስልክ ቁጥሬን አጋራ (Share Contact)",
        'skip_phone': "ዝለል / Skip ➡️",
        'btn_design': "🖼 የ1 ሰዓት ፈጣን ዲዛይን (ከ 1,500 ብር)",
        'btn_video': "🎬 የቪዲዮ ፕሮዳክሽን (ከ 4,500 ብር)",
        'btn_social': "📱 የሶሻል ሚዲያ ግብይት (SMM)",
        'btn_portfolio': "🎨 ኦፊሴላዊ የፖርትፎሊዮ ማህደር",
        'btn_reviews': "⭐ የተረጋገጡ የደንበኞች ግምገማዎች",
        'btn_leave_review': "✍️ አስተያየት መስጠት",
        'btn_settings': "⚙️ ቋንቋ / Settings",
        'back_menu': "🔙 ወደ ዋናው ማውጫ",
        'order_now': "🚀 አሁኑኑ ያዝዙ (ቅድሚያ ያግኙ)",
        'design_desc': (
            "🖼 **የ1 ሰዓት ፈጣን ዲዛይን እና የታምብሌን ፓኬጅ**\n\n"
            "💰 **ዋጋ:** 1,500 - 3,500 ብር\n\n"
            "• የዩቲዩብ እና ቲክቶክ እይታን የሚጨምሩ ታምብሌኖች\n"
            "• የሽያጭ መጠንን የሚጨምሩ የፌስቡክ/ቴሌግራም ፖስተሮች\n\n"
            "⚠️ *የቦታ እጥረት ስላለ አሁኑኑ በማዘዝ ስራዎን ያስጀምሩ!*"
        ),
        'video_desc': (
            "🎬 **የቪዲዮ ፕሮዳክሽን እና ሲነማቲክ ኤዲት ፓኬጅ**\n\n"
            "💰 **ዋጋ:** 4,500 - 10,000 ብር\n\n"
            "• ተመልካቹን የሚማርክ የምረቃ እና የልደት ቪዲዮ ኤዲቲንግ\n"
            "• የንግድ ድርጅትዎን ሽያጭ የሚያነቃቁ የማስታወቂያ ቪዲዮዎች\n\n"
            "⚡ *ከባለሙያው ጋር ለመነጋገር ከታች ያለውን ይጫኑ:*"
        ),
        'social_desc': (
            "📱 **የሶሻል ሚዲያ ግብይት እና አስተዳደር (SMM)**\n\n"
            "💰 **ዋጋ:** 8,000 - 15,000 ብር / በወር\n\n"
            "• ሙሉ የገጽ አስተዳደር እና የይዘት ስትራቴጂ\n"
            "• ታዳሚዎን ወደ ቋሚ ደንበኛ የሚቀይር አሰራር\n\n"
            "⚡ *ስትራቴጂክ ውይይት ለመጀመር ከታች ያለውን ይጫኑ:*"
        ),
        'portfolio_desc': "🎨 **ኦፊሴላዊ የፖርትፎሊዮ ማህደር**\n\nእስካሁን የሰራናቸውን ከፍተኛ ጥራት ያላቸውን ስራዎች ከታች ባለው ሊንክ ይመልከቱ:",
        'settings_title': "⚙️ **ቋንቋ ይምረጡ / Choose Language:**",
        'review_prompt': "✍️ **እባክዎን ስለ አገልግሎታችን ያለዎትን እውነተኛ አስተያየት (ቢያንስ 5 ፊደላት) ይጻፉልን:**",
        'review_error': "⚠️ **ማሳሰቢያ:** የጻፉት አስተያየት አጭርពេዟል። እባክዎን ትርጉም ያለው አስተያየት በድጋሚ ይጻፉ:",
        'review_success': "🎉 **አስተያየትዎ በተሳካ ሁኔታ ተመዝግቧል! እናመሰግናለን።** 🚀"
    },
    'en': {
        'welcome': (
            "🔥 **Elevate Your Brand & Double Your Sales!** 🔥\n\n"
            "Welcome to **RM Media | Result & Momentum**. 🚀\n\n"
            "📞 **Direct Line:** +251967830825\n"
            "💬 **Direct Consultation:** [Chat with Lead Expert](https://t.me/Respect_for_God)\n"
            "🎨 **Portfolio:** [Explore Our Works](https://t.me/Real_Works_Ethiopia)\n\n"
            "👇 *Choose a service below to transform your business:*"
        ),
        'phone_prompt': "📱 Please share your phone number using the button below for quick communication:",
        'phone_btn': "📲 Share Contact",
        'skip_phone': "Skip ➡️",
        'btn_design': "🖼 1-Hour Fast Design (From 1,500 ETB)",
        'btn_video': "🎬 Video Production (From 4,500 ETB)",
        'btn_social': "📱 Social Media Marketing (SMM)",
        'btn_portfolio': "🎨 Official Portfolio Archive",
        'btn_reviews': "⭐ Verified Client Testimonials",
        'btn_leave_review': "✍️ Leave a Review",
        'btn_settings': "⚙️ Language / Settings",
        'back_menu': "🔙 Main Menu",
        'order_now': "🚀 Order Now (High Priority)",
        'design_desc': (
            "🖼 **1-Hour Fast Design & Thumbnails Package**\n\n"
            "💰 **Price:** 1,500 - 3,500 ETB\n\n"
            "• High CTR YouTube & TikTok Thumbnails\n"
            "• High-Converting Social Media Posters\n\n"
            "⚠️ *Limited slots available today. Initiate your order now!*"
        ),
        'video_desc': (
            "🎬 **Video Production & Cinematic Edit Package**\n\n"
            "💰 **Price:** 4,500 - 10,000 ETB\n\n"
            "• Engaging Graduation & Birthday Video Editing\n"
            "• Commercial Promo Videos to Boost Sales\n\n"
            "⚡ *Click below to consult with our experts:*"
        ),
        'social_desc': (
            "📱 **Social Media Marketing & SMM Retainer**\n\n"
            "💰 **Price:** 8,000 - 15,000 ETB / Month\n\n"
            "• Full Page Management & Content Strategy\n"
            "• Systems designed to convert audience into loyal clients\n\n"
            "⚡ *Click below to book a strategy session:*"
        ),
        'portfolio_desc': "🎨 **Official Portfolio Archive**\n\nReview our high-quality works in our channel below:",
        'settings_title': "⚙️ **Choose Language / ቋንቋ ይምረጡ:**",
        'review_prompt': "✍️ **Please write your review (at least 5 characters) below:**",
        'review_error': "⚠️ **Notice:** Your review is too short. Please write a meaningful review:",
        'review_success': "🎉 **Your review has been successfully recorded! Thank you.** 🚀"
    }
}

async def get_user_lang_cached(user_id, context: ContextTypes.DEFAULT_TYPE):
    """የቋንቋ መረጃን በሜሞሪ (Cache) በመያዝ ዳታቤዝ እንዳይጠራና ቦቱ እንዲፈጥን ማድረግ"""
    if "lang" in context.user_data:
        return context.user_data["lang"]
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            lang = row[0] if row else 'am'
            context.user_data["lang"] = lang
            return lang

def build_main_keyboard(t):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t['btn_design'], callback_data="serv_design")],
        [InlineKeyboardButton(t['btn_video'], callback_data="serv_video")],
        [InlineKeyboardButton(t['btn_social'], callback_data="serv_social")],
        [InlineKeyboardButton(t['btn_portfolio'], callback_data="serv_portfolio")],
        [
            InlineKeyboardButton(t['btn_reviews'], callback_data="show_reviews"),
            InlineKeyboardButton(t['btn_leave_review'], callback_data="leave_review"),
        ],
        [InlineKeyboardButton(t['btn_settings'], callback_data="settings")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)",
            (user.id, user.full_name),
        )
        await db.commit()

    lang = await get_user_lang_cached(user.id, context)
    t = TEXTS.get(lang, TEXTS['am'])

    # Lead Capture Check
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT phone_number FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and not row[0]:
                reply_markup = ReplyKeyboardMarkup(
                    [[KeyboardButton(t['phone_btn'], request_contact=True)], [KeyboardButton(t['skip_phone'])]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                if update.message:
                    await update.message.reply_text(t['phone_prompt'], reply_markup=reply_markup)
                return

    welcome_text = t['welcome'].format(name=user.first_name)
    reply_markup = build_main_keyboard(t)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # ⚡ 1. በቅጽበት መልስ መስጠት (Loading Spinner ን ወዲያው ለማጥፋት)
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    lang = await get_user_lang_cached(user_id, context)
    t = TEXTS.get(lang, TEXTS['am'])

    # ⚡ 2. ፈጣን አዝራሮች ምላሽ (Instant UI Switching)
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
            [InlineKeyboardButton("🔗 የጥራት ማህደራችንን ይጎብኙ (Explore Archive)", url="https://t.me/Real_Works_Ethiopia")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['portfolio_desc'], reply_markup=markup, parse_mode="Markdown")

    elif data == "show_reviews":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT full_name, rating, review_text FROM reviews WHERE approved = 1 ORDER BY id DESC LIMIT 3") as cursor:
                rows = await cursor.fetchall()

        rev_text = "⭐ **Verified Client Testimonials / የተረጋገጡ የደንበኞች ግምገማዎች** ⭐\n\n"
        for name, rating, r_text in rows:
            stars = "⭐" * rating
            rev_text += f"👤 **{name}** {stars}\n💬 \"{r_text}\"\n\n"

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t['btn_leave_review'], callback_data="leave_review")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")]
        ])
        await query.edit_message_text(rev_text, reply_markup=markup, parse_mode="Markdown")

    elif data == "leave_review":
        context.user_data["waiting_for_review"] = True
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(t['back_menu'], callback_data="main_menu")]])
        await query.edit_message_text(t['review_prompt'], reply_markup=markup, parse_mode="Markdown")

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
        context.user_data["lang"] = "am"
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET language = 'am' WHERE user_id = ?", (user_id,))
            await db.commit()
        await query.edit_message_text(TEXTS['am']['welcome'].format(name=query.from_user.first_name), reply_markup=build_main_keyboard(TEXTS['am']), parse_mode="Markdown")

    elif data == "lang_en":
        context.user_data["lang"] = "en"
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET language = 'en' WHERE user_id = ?", (user_id,))
            await db.commit()
        await query.edit_message_text(TEXTS['en']['welcome'].format(name=query.from_user.first_name), reply_markup=build_main_keyboard(TEXTS['en']), parse_mode="Markdown")

    elif data == "main_menu":
        context.user_data["waiting_for_review"] = False
        welcome_text = t['welcome'].format(name=query.from_user.first_name)
        await query.edit_message_text(welcome_text, reply_markup=build_main_keyboard(t), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = await get_user_lang_cached(user.id, context)
    t = TEXTS.get(lang, TEXTS['am'])

    if update.message.contact:
        phone = update.message.contact.phone_number
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET phone_number = ? WHERE user_id = ?", (phone, user.id))
            await db.commit()
        
        await update.message.reply_text("✅ እናመሰግናለን! ስልክ ቁጥርዎ ተመዝግቧል።", reply_markup=ReplyKeyboardMarkup([[]], remove_keyboard=True))
        await start(update, context)
        return

    if update.message.text in ["ዝለል / Skip ➡️", "Skip ➡️"]:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET phone_number = 'SKIPPED' WHERE user_id = ?", (user.id,))
            await db.commit()
        await update.message.reply_text("እንቀጥል...", reply_markup=ReplyKeyboardMarkup([[]], remove_keyboard=True))
        await start(update, context)
        return

    if context.user_data.get("waiting_for_review"):
        review_text = update.message.text
        if not review_text or len(review_text.strip()) < 5:
            await update.message.reply_text(t['review_error'])
            return

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT INTO reviews (user_id, full_name, rating, review_text, approved) VALUES (?, ?, ?, ?, ?)",
                (user.id, user.full_name, 5, review_text.strip(), 1),
            )
            await db.commit()

        context.user_data["waiting_for_review"] = False
        await update.message.reply_text(t['review_success'], parse_mode="Markdown")
        await start(update, context)

def main():
    keep_alive()
    import asyncio
    asyncio.run(init_db())

    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.CONTACT, handle_message))

    print("RM Media Ultra-Fast Sales Bot Engine Running 24/7...")
    app.run_polling()

if __name__ == "__main__":
    main()
