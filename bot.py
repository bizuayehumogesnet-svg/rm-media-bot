import os
from flask import Flask
from threading import Thread

# አጭር የድር ሰርቨር መፍጠር (ለ Render ፖርት እንዲያሟላ)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ከዚህ በታች ያለው የእርስዎ የቦት ኮድ ይቀጥላል ---


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

# የሎግ ማስተካከያ (Logging Setup)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_FILE = "rm_media.db"


def init_db():
  """የውሂብ ጎታ (SQLite) ማዋቀሪያ እና ሠንጠረዦችን መፍጠሪያ"""
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  # ተጠቃሚዎችን መመዝገቢያ ሠንጠረዥ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            language TEXT DEFAULT 'am',
            subscribed INTEGER DEFAULT 1,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

  # የደንበኞች አስተያየት እና ምስክርነት ሠንጠረዥ
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

  # ለመጀመሪያ ጊዜ የሙከራ ግምገማዎችን ማስገባት (ሰንጠረዡ ባዶ ከሆነ)
  cursor.execute("SELECT COUNT(*) FROM reviews")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO reviews (user_id, full_name, rating, review_text, approved)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            101,
            "አቤል ከበደ",
            5,
            "አር ኤም ሚዲያ በሰዓት ውስጥ የሠራልኝ ቪዲዮ እና ፖስተር በጣም ድንቅ ነው! በጣም ፈጣኖች"
            " ናቸው።",
            1,
        ),
    )
    cursor.execute(
        "INSERT INTO reviews (user_id, full_name, rating, review_text, approved)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            102,
            "ሳራ ዮሐንስ",
            5,
            "የሶሻል ሚዲያ አስተዳደር አገልግሎታቸው ድርጅቴን በከፍተኛ ፍጥነት እንዲያድግ አድርጎታል።"
            " እናመሰግናለን!",
            1,
        ),
    )

  conn.commit()
  conn.close()


# ዳታቤዙን ማስጀመር
init_db()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """የ /start ትዕዛዝ ሲጠራ የሚሰጥ ምላሽ እና ዋናው ማውጫ"""
  user = update.effective_user

  # ተጠቃሚውን በዳታቤዝ መመዝገብ
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)",
      (user.id, user.full_name),
  )
  conn.commit()
  conn.close()

  # የዋናው ምናሌ አዝራሮች
  keyboard = [
      [
          InlineKeyboardButton(
              "🖼 የ1 ሰዓት ፈጣን ዲዛይን (Fast Design)", callback_data="serv_design"
          )
      ],
      [
          InlineKeyboardButton(
              "🎬 የቪዲዮ ፕሮዳክሽን እና ኤዲት (Video Production)",
              callback_data="serv_video",
          )
      ],
      [
          InlineKeyboardButton(
              "📱 የሶሻል ሚዲያ አስተዳደር (Social Media)",
              callback_data="serv_social",
          )
      ],
      [
          InlineKeyboardButton(
              "⭐ የደንበኞች አስተያየት (Client Reviews)", callback_data="show_reviews"
          ),
          InlineKeyboardButton(
              "✍️ አስተያየት መስጫ (Leave Review)", callback_data="leave_review"
          ),
      ],
      [
          InlineKeyboardButton(
              "⚙️ ማስተካከያ / ቅንብር (Settings)", callback_data="settings"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      f"ሰላም **{user.first_name}**!\n\n"
      "እንኳን ወደ **RM Media | Result & Momentum** በደህና መጡ።\n"
      "የእኛ መሪ ቃል: **ውጤት እና ፍጥነት (Result & Momentum)** 🚀\n\n"
      "ለድርጅትዎ፣ ለብራንድዎ ወይም ለግል ስራዎ የሚያስፈልጉትን ፈጣን እና ጥራት ያላቸውን"
      " የዲጂታል ግብይት እና የሚዲያ ፈጠራ አገልግሎቶች ከታች ካሉት አማራጮች በመምረጥ ይጀምሩ!"
  )

  if update.message:
    await update.message.reply_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )
  elif update.callback_query:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """የተጠቃሚዎችን የប៊ተን ንክኪዎች የሚያስተናግድ ዋና ተግባር"""
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "serv_design":
    text = (
        "🖼 **የ1 ሰዓት ፈጣን ዲዛይን እና ታምብሌን (Fast Design & Thumbnails)**\n\n- የዩቲዩብ"
        " እና ቲክቶክ ታምብሌኖች\n- ማራኪ የሶሻል ሚዲያ ፖስተሮች\n- የንግድ ማስታወቂያ ግራፊክስ\n\n"
        "በጣም በአጭር ሰዓት ውስጥ ጥራት ያለው ስራ እንሰራለን። ትዕዛዝ ለመስጠት ከታች"
        " ያለውን ይጫኑ:"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📥 ትዕዛዝ ለመስጠት (Order Now)", url="https://t.me/RM_Media_Admin"
            )
        ],
        [InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        text, reply_markup=markup, parse_mode="Markdown"
    )

  elif data == "serv_video":
    text = (
        "🎬 **የቪዲዮ ፕሮዳክሽን እና ፕሮሞ ኤዲት (Video Production & Promo)**\n\n- የምረቃ"
        " እና የልደት ቪዲዮ ኤዲቲንግ\n- የንግድ ድርጅት ማስታወቂያ ቪዲዮዎች\n- አጭር ቲክቶክ እና ሪልስ"
        " ቪዲዮዎች\n\nጥራት ያለው እና ፈጣን ስራ ለማግኘት ያግኙን:"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📥 ትዕዛዝ ለመስጠት (Order Now)", url="https://t.me/RM_Media_Admin"
            )
        ],
        [InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        text, reply_markup=markup, parse_mode="Markdown"
    )

  elif data == "serv_social":
    text = (
        "📱 **የሶሻል ሚዲያ አስተዳደር (Social Media Management & VA)**\n\n- ሙሉ የገጽ"
        " (Page) አስተዳደር\n- የይዘት ስትራቴጂ እና የጊዜ ሰሌዳ\n- ተከታዮችን ማሳደግ እና"
        " ማስተዋወቅ\n\nድርጅትዎን በዲጂታል ዓለም ታዋቂ ለማድረግ አብረን እንስራ!"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📥 የውይይት ጥያቄ (Book Consultation)",
                url="https://t.me/RM_Media_Admin",
            )
        ],
        [InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        text, reply_markup=markup, parse_mode="Markdown"
    )

  elif data == "show_reviews":
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT full_name, rating, review_text FROM reviews WHERE approved = 1"
        " ORDER BY id DESC LIMIT 5"
    )
    rows = cursor.fetchall()
    conn.close()

    rev_text = (
        "⭐ **የደንበኞቻችን ምስክርነት እና ግምገማዎች (Client Testimonials)** ⭐\n\n"
    )
    for name, rating, r_text in rows:
      stars = "⭐" * rating
      rev_text += f"👤 **{name}** {stars}\n💬 \"{r_text}\"\n\n"

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✍️ አስተያየት መስጠት (Leave Review)", callback_data="leave_review"
            )
        ],
        [InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        rev_text, reply_markup=markup, parse_mode="Markdown"
    )

  elif data == "leave_review":
    context.user_data["waiting_for_review"] = True
    text = (
        "✍️ **አስተያየትዎን ወይም ምስክርነትዎን ያጋሩን!**\n\nእባክዎ ስለ አገልግሎታችን ያለዎትን"
        " ሃሳብ ወይም የተሰማዎትን እርካታ በዚህ ቻት ውስጥ ጽሁፍ በመላክ ያሳውቁን።"
    )
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 ሰርዝ / ተመለስ", callback_data="main_menu")]]
    )
    await query.edit_message_text(
        text, reply_markup=markup, parse_mode="Markdown"
    )

  elif data == "settings":
    user_id = query.from_user.id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT subscribed FROM users WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    sub_status = row[0] if row else 1
    conn.close()

    sub_btn_text = (
        "🔕 መልእክት አቁም (Unsubscribe)"
        if sub_status == 1
        else "🔔 ማሳወቂያ ፍቀድ (Subscribe)"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(sub_btn_text, callback_data="toggle_sub")],
        [InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")],
    ])
    await query.edit_message_text(
        "⚙️ **የመቆጣጠሪያ ማስተካከያ (Settings)**\n\nከዚህ በታች ያሉትን አማራጮች በመጠቀም"
        " የቦቱን ማሳወቂያዎች መቆጣጠር ይችላሉ።",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif data == "toggle_sub":
    user_id = query.from_user.id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT subscribed FROM users WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    current_sub = row[0] if row else 1
    new_sub = 0 if current_sub == 1 else 1
    cursor.execute(
        "UPDATE users SET subscribed = ? WHERE user_id = ?",
        (new_sub, user_id),
    )
    conn.commit()
    conn.close()

    status_msg = (
        "✅ ማሳወቂያዎች ተቋርጠዋል (Unsubscribed). ከእንግዲህ የብሮድካስት መልእክቶች"
        " አይደርሱዎትም።"
        if new_sub == 0
        else "✅ ማሳወቂያዎች ተፈቅደዋል (Subscribed)።"
    )
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]]
    )
    await query.edit_message_text(
        status_msg, reply_markup=markup, parse_mode="Markdown"
    )

  elif data == "main_menu":
    context.user_data["waiting_for_review"] = False
    await start(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """ተጠቃሚው የሚጽፋቸውን ጽሁፎች መቀበያ"""
  user = update.effective_user
  if context.user_data.get("waiting_for_review"):
    review_text = update.message.text
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (user_id, full_name, rating, review_text, approved)"
        " VALUES (?, ?, ?, ?, ?)",
        (user.id, user.full_name, 5, review_text, 1),
    )
    conn.commit()
    conn.close()

    context.user_data["waiting_for_review"] = False
    await update.message.reply_text(
        "🎉 **አስተያየትዎ በእጅጉ ተመዝግቧል! እናመሰግናለን።**\nአገልግሎታችንን ስለመረጡ ደስተኞች ነን።",
        parse_mode="Markdown",
    )
    await start(update, context)


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """ለአስተዳዳሪዎች ብቻ የተዘጋጀ የብሮድካስት ሲስተም"""
  text_args = " ".join(context.args)
  if not text_args:
    await update.message.reply_text(
        "⚠️ እባክዎ የሚተላለፈውን መልእክት ከአስተዳዳሪ ትእዛዝ ጋር ይጻፉ።\nምሳሌ: /admin"
        " የዛሬው ልዩ ቅናሽ ጀመረ!"
    )
    return

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT user_id FROM users WHERE subscribed = 1")
  users = cursor.fetchall()
  conn.close()

  success_count = 0
  for (u_id,) in users:
    try:
      await context.bot.send_message(
          chat_id=u_id,
          text=f"📢 **RM Media | Result & Momentum ማስታወቂያ**\n\n{text_args}",
          parse_mode="Markdown",
      )
      success_count += 1
    except Exception as e:
      logger.error(f"Failed to send broadcast to {u_id}: {e}")

  await update.message.reply_text(
      f"✅ መልእክቱ በተሳካ ሁኔታ ለ {success_count} ተጠቃሚዎች ተልኳል!"
  )


def main():
  # ቶከኑን ከ Render Environment Variables በደህንነት እንቀበላለን
  TOKEN = os.getenv("BOT_TOKEN")

  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("admin", admin_broadcast))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
  )

  print("RM Media Bot is up and running 24/7...")
  app.run_polling()


if __name__ == "__main__":
  main()
