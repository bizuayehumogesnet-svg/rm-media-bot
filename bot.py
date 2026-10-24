            pass


async def notify_admin(context, text, markup=None):
    try:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=text, reply_markup=markup)
        return True
    except TelegramError as e:
        logger.error("Could not notify admin (has the admin pressed /start in the bot?): %s", e)
        return False


# ---------------------------------------------------------------------------
# Order / review processing (shared by buttons and commands)
# ---------------------------------------------------------------------------
async def process_order(context, order_id, confirm):
    row = db_one("SELECT user_id, status FROM orders WHERE id = ?", (order_id,))
    if not row:
        return False, f"Order #{order_id} not found."
    user_id, status = row
    if status in ("confirmed", "rejected", "cancelled"):
        return False, f"Order #{order_id} is already {status}."

    new_status = "confirmed" if confirm else "rejected"
    db_exec("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))

    t = TEXTS[get_user_lang(user_id)]
    key = "order_confirmed" if confirm else "order_rejected"
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=t[key].format(order_id=order_id),
            parse_mode="Markdown",
        )
        delivered = "customer notified"
    except TelegramError:
        delivered = "could NOT message the customer (they may have blocked the bot)"
    return True, f"Order #{order_id} -> {new_status.upper()} ({delivered})."

