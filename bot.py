import os
import logging
import sqlite3
from flask import Flask
from threading import Thread
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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
    return "RM Media 10x Fully Automated & Secure Bot is Live!"

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

# 🛑 SECURITY SETTING: እዚህ ጋር የራስህን Telegram Numerical User ID ብቻ አስገባ!
# (የቴሌግራም ID ህን ለማወቅ @userinfobot ን በቴሌግራም መጠቀም ትችላለህ)
ADMIN_USER_ID = 2133585693  # 👈 እዚህ ጋር ቁጥርህን ተካ!

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone_number TEXT,
            language TEXT DEFAULT 'am',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Auto-migration check for existing DBs
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'phone_number' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
        
    conn.commit()
    conn.close()

init_db()

TEXTS = {
    'am': {
        'welcome': (
            "🔥 **የንግድዎን ሽያጭ እና እይታ በጥራት ያሳድጉ!** 🔥\n\n"
            "እንኳን ወደ **RM Media | Result & Momentum** በደህና መጡ። 🚀\n\n"
            "⭐ *ከ 120+ በላይ እርካታ ያገኙ ደንበኞች የመረጡን የብራንዲንግ እና የቪዲዮ ፕሮዳክሽን ማዕከል!*\n\n"
            "📞 **የቀጥታ መስመር:** +251967830825\n"
            "💬 **የባለሙያ ምክክር:** [ከዋና አዘጋጁ ጋር ይወያዩ](https://t.me/Respect_for_God)\n"
            "🎨 **ፖርትፎሊዮ:** [የሰራናቸውን ስራዎች ይመልከቱ](https://t.me/Real_Works_Ethiopia)\n\n"
            "👇 *እባክዎን ከታች ከሚገኙት አማራጮች የሚፈልጉትን ይምረጡ:*"
        ),
        'phone_prompt': "👋 ሰላም {name}! አገልግሎታችንን ለመጀመር እባክዎን ከታች ያለውን አዝራር በመጫን ስልክ ቁጥርዎን ያጋሩት፡",
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
        'order_now': "🚀 አሁኑኑ ያዝዙ (In-Bot Order)",
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
            "⚡ *አሁኑኑ በማዘዝ ከባለሙያችን ጋር ይገናኙ:*"
        ),
        'social_desc': (
            "📱 **የሶሻል ሚዲያ ግብይት እና አስተዳደር (SMM)**\n\n"
            "💰 **ዋጋ:** 8,000 - 15,000 ብር / በወር\n\n"
            "• ሙሉ የገጽ አስተዳደር እና የይዘት ስትራቴጂ\n"
            "• ታዳሚዎን ወደ ቋሚ ደንበኛ የሚቀይር አሰራር\n\n"
            "⚡ *አሁኑኑ በማዘዝ ስትራቴጂክ ውይይት ይጀምሩ:*"
        ),
        'checkout_text': (
            "💳 **የትዕዛዝ እና የክፍያ ማረጋገጫ (Checkout)**\n\n"
            "ትዕዛዝዎን ለማረጋገጥ እባክዎን በታች ያሉት የክፍያ አማራጮች ይጠቀሙ፡\n\n"
            "🔹 **CBE (ኢትዮጵያ ንግድ ባንክ):** `1000570870487`\n"
            "👤 **Account Name:** BIZUAYEHU MOGES MEKONNEN\n\n"
            "🔹 **Telebirr:** `0967830825`\n"
            "👤 **Name:** MOGES MEKONNEN\n\n"
            "📸 *ክፍያ ከፈጸሙ በኋላ የደረሰኝ ፎቶ (Receipt Image) ወይም የትራንስፎርሜሽን ቁጥር እዚሁ ቦት ላይ ይላኩ።*"
        ),
        'receipt_received': "✅ **የክፍያ ደረሰኝዎ ደርሶናል!**\n\nአመሰግናለን! በቅርብ ደቂቃዎች ውስጥ ክፍያዎ ተረጋግጦ ስራችንን እንጀምራለን። 🚀",
        'review_prompt': "✍️ **እባክዎን ስለ አገልግሎታችን ያለዎትን እውነተኛ አስተያየት (ቢያንስ 5 ፊደላት) ይጻፉልን:**",
        'review_error': "⚠️ **ማሳሰቢያ:** የጻፉት አስተያየት አጭር ነው። እባክዎን ትርጉም ያለው አስተያየት በድጋሚ ይጻፉ:",
        'review_success': "🎉 **አስተያየትዎ በተሳካ ሁኔታ ተመዝግቧል! እናመሰግናለን።** 🚀"
    },
    'en': {
        'welcome': (
            "🔥 **Elevate Your Brand & Double Your Sales!** 🔥\n\n"
            "Welcome to **RM Media | Result & Momentum**. 🚀\n\n"
            "⭐ *Trusted by 120+ Verified Clients across Ethiopia!*\n\n"
            "📞 **Direct Line:** +251967830825\n"
            "💬 **Direct Consultation:** [Chat with Lead Expert](https://t.me/Respect_for_God)\n"
            "🎨 **Portfolio:** [Explore Our Works](https://t.me/Real_Works_Ethiopia)\n\n"
            "👇 *Choose a service below to transform your business:*"
        ),
        'phone_prompt': "👋 Hello {name}! To get started, please share your phone number using the button below:",
        'phone_btn': "📲 Share Contact",
        'skip_phone': "Skip ➡️",
        'btn_design': "🖼 1-Hour Fast Design (From 1,500 ETB)",
        'btn_video': "🎬 Video Production (From 4,500 ETB)",
        'btn_social': "📱 Social Media Marketing (8,000 - 15,000 ETB)",
        'btn_portfolio': "🎨 Official Portfolio Archive",
        'btn_reviews': "⭐ Verified Client Testimonials",
        'btn_leave_review': "✍️ Leave a Review",
        'btn_settings': "⚙️ Language / Settings",
        'back_menu': "🔙 Main Menu",
        'order_now': "🚀 Order Now (In-Bot Order)",
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
            "⚡ *Order now to consult directly with our expert:*"
        ),
        'social_desc': (
            "📱 **Social Media Marketing & SMM Retainer**\n\n"
            "💰 **Price:** 8,000 - 15,000 ETB / Month\n\n"
            "• Full Page Management & Content Strategy\n"
            "• Systems designed to convert audience into loyal clients\n\n"
            "⚡ *Order now to start your strategy session:*"
        ),
        'checkout_text': (
            "💳 **In-Bot Order & Payment Confirmation**\n\n"
            "To confirm your order, please process payment to:\n\n"
            "🔹 **CBE Bank:** `1000570870487`\n"
            "👤 **Account Name:** BIZUAYEHU MOGES MEKONNEN\n\n"
            "🔹 **Telebirr:** `0967830825`\n"
            "👤 **Name:** MOGES MEKONNEN\n\n"
            "📸 *Once paid, please upload your Receipt Screenshot right here in this chat.*"
        ),
        'receipt_received': "✅ **Receipt Received!**\n\nThank you! Our team will verify your payment and start your project shortly. 🚀",
        'review_prompt': "✍️ **Please write your review (at least 5 characters) below:**",
        'review_error': "⚠️ **Notice:** Your review is too short. Please write a meaningful review:",
        'review_success': "🎉 **Your review has been successfully recorded! Thank you.** 🚀"
    }
}

def get_user_lang(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 'am'

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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)",
        (user.id, user.full_name),
    )
    conn.commit()

    lang = get_user_lang(user.id)
    t = TEXTS.get(lang, TEXTS['am'])

    cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    conn.close()

    if row and not row[0]:
        reply_markup = ReplyKeyboardMarkup(
            [[KeyboardButton(t['phone_btn'], request_contact=True)], [KeyboardButton(t['skip_phone'])]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        if update.message:
            await update.message.reply_text(t['phone_prompt'].format(name=user.first_name), reply_markup=reply_markup)
        return

    welcome_text = t['welcome'].format(name=user.first_name)
    reply_markup = build_main_keyboard(t)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# 🔒 RESTRICTED ADMIN STATS
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        return  # ባለቤቱ ካልሆነ ምንም አይነት ምላሽ አይሰጥም (ባዶ ይተዋል)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE phone_number IS NOT NULL AND phone_number != 'SKIPPED'")
    phone_leads = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    conn.close()

    stats_msg = (
        "📊 **RM Media Private Admin Analytics**\n\n"
        f"👥 **አጠቃላይ የቦት ተጠቃሚዎች:** {total_users}\n"
        f"📱 **የተመዘገቡ ስልክ ቁጥሮች (Leads):** {phone_leads}\n"
        f"🛒 **የተደረጉ አጠቃላይ ትዕዛዞች:** {total_orders}\n"
        f"⭐ **የተጻፉ ሪቪውዎች:** {total_reviews}\n"
    )
    await update.message.reply_text(stats_msg, parse_mode="Markdown")

# 📢 ADMIN BROADCAST COMMAND (/broadcast Your Message)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ **አጠቃቀም:** `/broadcast የ መልእክት ጽሁፍ`", parse_mode="Markdown")
        return

    broadcast_msg = " ".join(context.args)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    sent_count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=broadcast_msg, parse_mode="Markdown")
            sent_count += 1
        except Exception:
            continue

    await update.message.reply_text(f"✅ **መልእክቱ ለ {sent_count} ተጠቃሚዎች በተሳካ ሁኔታ ተልኳል!**")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    t = TEXTS.get(lang, TEXTS['am'])

    if data in ["serv_design", "serv_video", "serv_social"]:
        service_key = data.replace("serv_", "")
        desc_key = f"{service_key}_desc"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(t['order_now'], callback_data=f"order_{service_key}")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t[desc_key], reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("order_"):
        service_name = data.replace("order_", "")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO orders (user_id, service_name) VALUES (?, ?)", (user_id, service_name))
        conn.commit()
        conn.close()

        context.user_data["waiting_for_receipt"] = True
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(t['back_menu'], callback_data="main_menu")]])
        await query.edit_message_text(t['checkout_text'], reply_markup=markup, parse_mode="Markdown")

    elif data == "serv_portfolio":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 የጥራት ማህደራችንን ይጎብኙ (Explore Archive)", url="https://t.me/Real_Works_Ethiopia")],
            [InlineKeyboardButton(t['back_menu'], callback_data="main_menu")],
        ])
        await query.edit_message_text(t['portfolio_desc'], reply_markup=markup, parse_mode="Markdown")

    elif data == "show_reviews":
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, rating, review_text FROM reviews WHERE approved = 1 ORDER BY id DESC LIMIT 3")
        rows = cursor.fetchall()
        conn.close()

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
        await query.edit_message_text("⚙️ **ቋንቋ ይምረጡ / Choose Language:**", reply_markup=markup, parse_mode="Markdown")

    elif data in ["lang_am", "lang_en"]:
        new_lang = "am" if data == "lang_am" else "en"
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (new_lang, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(TEXTS[new_lang]['welcome'].format(name=query.from_user.first_name), reply_markup=build_main_keyboard(TEXTS[new_lang]), parse_mode="Markdown")

    elif data == "main_menu":
        context.user_data["waiting_for_review"] = False
        context.user_data["waiting_for_receipt"] = False
        welcome_text = t['welcome'].format(name=query.from_user.first_name)
        await query.edit_message_text(welcome_text, reply_markup=build_main_keyboard(t), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_user_lang(user.id)
    t = TEXTS.get(lang, TEXTS['am'])

    if update.message.contact:
        phone = update.message.contact.phone_number
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone_number = ? WHERE user_id = ?", (phone, user.id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text("✅ እናመሰግናለን! ስልክ ቁጥርዎ ተመዝግቧል።", reply_markup=ReplyKeyboardRemove())
        await start(update, context)
        return

    if update.message.text in ["ዝለል / Skip ➡️", "Skip ➡️"]:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone_number = 'SKIPPED' WHERE user_id = ?", (user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("እንቀጥል...", reply_markup=ReplyKeyboardRemove())
        await start(update, context)
        return

    if context.user_data.get("waiting_for_receipt"):
        context.user_data["waiting_for_receipt"] = False
        await update.message.reply_text(t['receipt_received'], parse_mode="Markdown")
        await start(update, context)
        return

    if context.user_data.get("waiting_for_review"):
        review_text = update.message.text
        if not review_text or len(review_text.strip()) < 5:
            await update.message.reply_text(t['review_error'])
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reviews (user_id, full_name, rating, review_text, approved) VALUES (?, ?, ?, ?, ?)",
            (user.id, user.full_name, 5, review_text.strip(), 1),
        )
        conn.commit()
        conn.close()

        context.user_data["waiting_for_review"] = False
        await update.message.reply_text(t['review_success'], parse_mode="Markdown")
        await start(update, context)

def main():
    keep_alive()
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("RM Media Secured 10x Automation Engine Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
