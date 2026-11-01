import os
import logging
import sqlite3
from datetime import datetime
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
from telegram.error import TelegramError

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

# 🔒 SECURITY SETTING: የነጠላ ባለቤት (Admin) የቴሌግራም ID
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "2133585693"))

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
            "📸 **ክፍያ ከፈጸሙ በኋላ ቀጣይ ስቴፕ:**\n"
            "1️⃣ የደረሰኝ ፎቶ (Receipt Image) ወይም የትራንስፎርሜሽን ቁጥር **እዚሁ ቦት ላይ ይላኩ**፤ ወይም\n"
            "2️⃣ የትዕዛዝ ማረጋገጫዎን ለማፋጠን [ወዲያውኑ ስክሪንሾቱን እዚህ ይላኩልን (Direct Inbox)](https://t.me/Respect_for_God) 👈"
        ),
        'receipt_received': "✅ **የክፍያ ደረሰኝዎ ደርሶናል!**\n\nአመሰግናለን! በቅርብ ደቂቃዎች ውስጥ ክፍያዎ ተረጋግጦ ስራችንን እንጀምራለን። 🚀",
        'review_prompt': "✍️ **እባክዎን ስለ አገልግሎታችን ያለዎትን እውነተኛ አስተያየት (ቢያንስ 5 ፊደላት) ይጻፉልን:**",
        'review_error': "⚠️ **ማሳሰቢያ:** የጻፉት አስተያየት አጭር ነው። እባክዎን ትርጉም ያለው አስተያየት በድጋሚ ይጻፉ:",
        'review_success': "🎉 **አስተያየትዎ በተሳካ ሁኔታ ተመዝግቧል! እናመሰግናለን።** 🚀",
        'portfolio_desc': (
            "🎨 **ኦፊሴላዊ የፖርትፎሊዮ ማህደር**\n\n"
            "እስካሁን የሰራናቸውን ዲዛይኖች፣ ታምብሌኖች እና ቪዲዮዎች በቴሌግራም ቻናላችን ላይ ማየት ይችላሉ።\n\n"
            "👇 *ከታች ያለውን አዝራር በመጫን ማህደራችንን ይጎብኙ:*"
        ),
        'receipt_invalid': "⚠️ እባክዎን የክፍያ ደረሰኝ ፎቶ (ስክሪንሾት) ወይም የትራንዛክሽን ቁጥር ይላኩ።",
        'order_label': "🧾 የትዕዛዝ ቁጥር",
        'order_confirmed': "✅ **ትዕዛዝዎ ተረጋግጧል!**\n\n🧾 ትዕዛዝ #{order_id}\nክፍያዎ ተረጋግጧል። ባለሙያችን ስራውን ጀምሯል፤ በቅርቡ እናገኝዎታለን። 🚀",
        'order_rejected': "❌ **ክፍያዎን ማረጋገጥ አልቻልንም**\n\n🧾 ትዕዛዝ #{order_id}\nእባክዎን ትክክለኛ ደረሰኝ ይላኩ ወይም በ[Direct Inbox](https://t.me/Respect_for_God) ያነጋግሩን።",
        'no_reviews': "_እስካሁን የታተመ ግምገማ የለም።_\n\n"
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
            "📸 **Next Step After Payment:**\n"
            "1️⃣ Upload your Receipt Screenshot right here in this bot; or\n"
            "2️⃣ Send screenshot directly to our expert: [Send Screenshot to Direct Inbox](https://t.me/Respect_for_God) 👈"
        ),
        'receipt_received': "✅ **Receipt Received!**\n\nThank you! Our team will verify your payment and start your project shortly. 🚀",
        'review_prompt': "✍️ **Please write your review (at least 5 characters) below:**",
        'review_error': "⚠️ **Notice:** Your review is too short. Please write a meaningful review:",
        'review_success': "🎉 **Your review has been successfully recorded! Thank you.** 🚀",
        'portfolio_desc': (
            "🎨 **Official Portfolio Archive**\n\n"
            "Browse the designs, thumbnails and videos we have delivered on our Telegram channel.\n\n"
            "👇 *Tap the button below to explore our archive:*"
        ),
        'receipt_invalid': "⚠️ Please send a payment receipt photo (screenshot) or the transaction reference number.",
        'order_label': "🧾 Order No.",
        'order_confirmed': "✅ **Your order is confirmed!**\n\n🧾 Order #{order_id}\nYour payment is verified. Our expert has started working; we will be in touch shortly. 🚀",
        'order_rejected': "❌ **We could not verify your payment**\n\n🧾 Order #{order_id}\nPlease send a valid receipt or contact us via [Direct Inbox](https://t.me/Respect_for_God).",
        'no_reviews': "_No published reviews yet._\n\n"
    }
}

def get_user_lang(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 'am'

SERVICE_LABELS = {
    'design': '🖼 Fast Design / Thumbnail',
    'video': '🎬 Video Production',
    'social': '📱 Social Media Marketing',
}

def md_escape(text):
    """Escape characters that break Telegram legacy Markdown."""
    text = str(text or "")
    for ch in ("\\", "_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text

def first_name_only(full_name):
    parts = (full_name or "").strip().split()
    return parts[0] if parts else "Customer"

def get_or_create_pending_order(user_id, preferred_id=None, service_name=None):
    """Return (order_id, service_name) of the user's pending order.
    Reuses an existing pending order instead of creating duplicates."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    row = None
    if preferred_id:
        cursor.execute(
            "SELECT id, service_name FROM orders WHERE id = ? AND user_id = ? AND status = 'pending'",
            (preferred_id, user_id),
        )
        row = cursor.fetchone()
    if not row and service_name:
        cursor.execute(
            "SELECT id, service_name FROM orders WHERE user_id = ? AND service_name = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (user_id, service_name),
        )
        row = cursor.fetchone()
    if not row and not service_name:
        cursor.execute(
            "SELECT id, service_name FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
    if not row:
        name = service_name or "unspecified"
        cursor.execute("INSERT INTO orders (user_id, service_name) VALUES (?, ?)", (user_id, name))
        conn.commit()
        row = (cursor.lastrowid, name)
    conn.close()
    return row[0], row[1]

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
        return

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

# 📢 ADMIN BROADCAST COMMAND (/broadcast መልእክት)
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
        order_id, _ = get_or_create_pending_order(user_id, service_name=service_name)

        context.user_data["waiting_for_receipt"] = True
        context.user_data["current_order_id"] = order_id
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(t['back_menu'], callback_data="main_menu")]])
        checkout = f"{t['order_label']}: #{order_id}\n\n" + t['checkout_text']
        await query.edit_message_text(checkout, reply_markup=markup, parse_mode="Markdown")

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
        if not rows:
            rev_text += t['no_reviews']
        for name, rating, r_text in rows:
            stars = "⭐" * max(1, min(int(rating or 5), 5))
            safe_name = md_escape(first_name_only(name))
            rev_text += f"👤 **{safe_name}** {stars}\n💬 \"{md_escape(r_text)}\"\n\n"

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

# 🔒 ADMIN: ✅ Confirm / ❌ Reject buttons under each receipt
async def admin_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_USER_ID:
        await query.answer("⛔ Not allowed", show_alert=True)
        return

    try:
        _, action, order_id = query.data.split("_")
        order_id = int(order_id)
    except ValueError:
        await query.answer("Invalid data", show_alert=True)
        return

    confirm = action == "ok"
    new_status = "confirmed" if confirm else "rejected"

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, status FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        await query.answer(f"Order #{order_id} not found", show_alert=True)
        return

    customer_id, status = row
    cursor.execute(
        "UPDATE orders SET status = ? WHERE id = ? AND status NOT IN ('confirmed', 'rejected')",
        (new_status, order_id),
    )
    changed = cursor.rowcount
    conn.commit()
    conn.close()

    if not changed:
        await query.answer(f"Order #{order_id} is already {status}", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass
        return

    t = TEXTS.get(get_user_lang(customer_id), TEXTS['am'])
    key = "order_confirmed" if confirm else "order_rejected"
    try:
        await context.bot.send_message(
            chat_id=customer_id,
            text=t[key].format(order_id=order_id),
            parse_mode="Markdown",
        )
        delivered = "customer notified"
    except TelegramError:
        delivered = "could NOT message the customer (they may have blocked the bot)"

    await query.answer("Done")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except TelegramError:
        pass
    await query.message.reply_text(f"Order #{order_id} -> {new_status.upper()} ({delivered}).")

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
        msg = update.message
        photo = msg.photo[-1] if msg.photo else None
        doc = msg.document
        ref_text = (msg.text or "").strip()
        if not photo and not doc and len(ref_text) < 4:
            await msg.reply_text(t['receipt_invalid'])
            return

        context.user_data["waiting_for_receipt"] = False
        order_id, service = get_or_create_pending_order(user.id, context.user_data.get("current_order_id"))

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (user.id,))
        prow = cursor.fetchone()
        conn.close()
        phone = prow[0] if prow and prow[0] and prow[0] != 'SKIPPED' else "-"

        caption = (
            "🧾 NEW PAYMENT RECEIPT\n\n"
            f"🆔 Order: #{order_id}\n"
            f"🛍 Service: {SERVICE_LABELS.get(service, service)}\n"
            f"👤 Name: {user.full_name}\n"
            f"🔗 Username: {'@' + user.username if user.username else '-'}\n"
            f"🪪 User ID: {user.id}\n"
            f"📱 Phone: {phone}\n"
            f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        if ref_text and not photo and not doc:
            caption += f"\n\n📝 Reference:\n{ref_text[:1500]}"

        admin_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"adm_ok_{order_id}"),
            InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"adm_no_{order_id}"),
        ]])
        try:
            if photo:
                await context.bot.send_photo(chat_id=ADMIN_USER_ID, photo=photo.file_id, caption=caption, reply_markup=admin_markup)
            elif doc:
                await context.bot.send_document(chat_id=ADMIN_USER_ID, document=doc.file_id, caption=caption, reply_markup=admin_markup)
            else:
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=caption, reply_markup=admin_markup)
        except TelegramError as e:
            logger.error("Could not notify admin about order #%s (has the admin pressed /start?): %s", order_id, e)

        await msg.reply_text(f"{t['receipt_received']}\n\n{t['order_label']}: #{order_id}", parse_mode="Markdown")
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
    app.add_handler(CallbackQueryHandler(admin_order_callback, pattern=r"^adm_(ok|no)_\d+$"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("RM Media Secured 10x Automation Engine Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
