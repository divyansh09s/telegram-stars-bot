import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
)
import sqlite3

# --- Configuration ---
TOKEN = "7551744666:AAF7I4Z5pLWmR4-YbbQaQVcTk3O2uPE787k"
CHANNEL_USERNAME = "@kids_coder"  # With @
ADMIN_IDS = [5623125970]
DATABASE = "bot.db"

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Database Init ---
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            is_banned BOOLEAN DEFAULT 0,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS withdrawals (
            withdrawal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item TEXT,
            cost INTEGER,
            status TEXT DEFAULT 'pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """
    )

    for admin_id in ADMIN_IDS:
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))

    conn.commit()
    conn.close()


init_db()


# --- Helpers ---
def get_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user(user_id, username, first_name, last_name, referrer_id=None):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, referrer_id)
        VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, username, first_name, last_name, referrer_id),
    )
    conn.commit()
    conn.close()


def update_balance(user_id, amount):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def is_member(user_id, context: CallbackContext):
    try:
        member = context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"is_member check failed for user {user_id}: {e}")
        return False


def is_admin(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result


# --- Keyboards ---
def main_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Balance", callback_data="balance"),
            InlineKeyboardButton("Refer", callback_data="refer"),
            InlineKeyboardButton("Withdraw", callback_data="withdraw")],
        ]
    )


def withdraw_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Heart (15⭐)", callback_data="withdraw_heart")],
            [InlineKeyboardButton("Teddy (15⭐)", callback_data="withdraw_teddy")],
            [InlineKeyboardButton("Gift Box (25⭐)", callback_data="withdraw_giftbox")],
            [InlineKeyboardButton("Cake (50⭐)", callback_data="withdraw_cake")],
            [InlineKeyboardButton("Diamond (100⭐)", callback_data="withdraw_diamond")],
            [InlineKeyboardButton("Back", callback_data="main_menu")],
        ]
    )


def confirm_keyboard(item, cost):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Yes", callback_data=f"confirm_{item}_{cost}")],
            [InlineKeyboardButton("No", callback_data="withdraw")],
        ]
    )


# --- Commands ---
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""

    if get_user(user_id) is None:
        referrer_id = None
        if context.args:
            try:
                referrer_id = int(context.args[0])
                if not get_user(referrer_id):
                    referrer_id = None
            except Exception:
                referrer_id = None

        create_user(user_id, username, first_name, last_name, referrer_id)
        if referrer_id:
            update_balance(referrer_id, 1)
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                (referrer_id, user_id),
            )
            conn.commit()
            conn.close()

    if is_member(user_id, context):
        update.message.reply_text("👋 Welcome!\n🎉 You’ve just joined the best way to earn free Telegram Stars!\n🎁 Don’t forget to share your referral link to earn even more!", reply_markup=main_menu_keyboard())
    else:
        update.message.reply_text(
            f"Please join our channel {CHANNEL_USERNAME} to use this bot.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
                    ],
                    [InlineKeyboardButton("I've Joined", callback_data="check_join")],
                ]
            ),
        )


# --- Button Callback ---
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    query.answer()

    if not is_member(user_id, context) and data != "check_join":
        query.answer("Please join the channel first.", show_alert=True)
        return

    user = get_user(user_id)
    if not user or user[6]:  # is_banned is index 6
        query.edit_message_text("Access denied.")
        return

    if data == "check_join":
        if is_member(user_id, context):
            query.edit_message_text("Thanks for joining!", reply_markup=main_menu_keyboard())
        else:
            query.answer("Still not joined.", show_alert=True)
    elif data == "main_menu":
        query.edit_message_text("Main Menu:", reply_markup=main_menu_keyboard())
    elif data == "balance":
        query.edit_message_text(f"Your current balance: {user[4]} stars", reply_markup=main_menu_keyboard())
    elif data == "refer":
        ref_link = f"https://t.me/{context.bot.username}?start={user_id}"
        query.edit_message_text(
            f"👥 Invite Friends & Earn Telegram Stars!\n✨ For every friend who joins using your link, you’ll earn +1 Star — instantly!\n\n🔗 Your Referral Link:\n{ref_link}\n\n💡 More invites = More stars = Faster withdrawals!\nStart sharing now and boost your earnings! 🚀",
            reply_markup=main_menu_keyboard(),
        )
    elif data == "withdraw":
        query.edit_message_text("Choose an item:", reply_markup=withdraw_menu_keyboard())
    elif data.startswith("withdraw_"):
        item = data.split("_", 1)[1]
        prices = {"heart": 15, "teddy": 15, "giftbox": 25, "cake": 50, "diamond": 100}
        cost = prices.get(item, 0)
        if user[4] >= cost:
            query.edit_message_text(
                f"Redeem {item.capitalize()} for {cost} stars?", reply_markup=confirm_keyboard(item, cost)
            )
        else:
            query.edit_message_text(
                f"Not enough stars. You need {cost}, you have {user[4]}.", reply_markup=withdraw_menu_keyboard()
            )
    elif data.startswith("confirm_"):
        parts = data.split("_")
        if len(parts) >= 3:
            item = parts[1]
            try:
                cost = int(parts[2])
            except ValueError:
                query.edit_message_text("Invalid confirmation data.", reply_markup=main_menu_keyboard())
                return
            if user[4] >= cost:
                update_balance(user_id, -cost)
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO withdrawals (user_id, item, cost) VALUES (?, ?, ?)", (user_id, item, cost)
                )
                conn.commit()
                conn.close()

                for admin_id in ADMIN_IDS:
                    try:
                        context.bot.send_message(
                            admin_id,
                            f"🔔 Withdrawal request:\nUser: @{user[1]} ({user_id})\nItem: {item}\nCost: {cost}\nNew balance: {user[4] - cost}",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send withdrawal notification to admin {admin_id}: {e}")

                query.edit_message_text("Your request has been submitted!", reply_markup=main_menu_keyboard())
            else:
                query.edit_message_text("Not enough stars!", reply_markup=withdraw_menu_keyboard())
        else:
            query.edit_message_text("Invalid confirmation data.", reply_markup=main_menu_keyboard())


# --- Admin Commands ---
def admin(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("Unauthorized.")
        return

    args = context.args
    if not args:
        update.message.reply_text(
            "/admin broadcast <msg>\n"
            "/admin setbalance <user_id> <amount>\n"
            "/admin ban <user_id>\n"
            "/admin unban <user_id>\n"
            "/admin message <user_id> <msg>\n"
            "/admin referrals <user_id>"
        )
        return

    cmd = args[0].lower()

    try:
        if cmd == "broadcast":
            message = " ".join(args[1:])
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
            users = cursor.fetchall()
            conn.close()

            sent_count = 0
            for user in users:
                try:
                    context.bot.send_message(user[0], f"📢 {message}")
                    sent_count += 1
                except Exception:
                    pass
            update.message.reply_text(f"Sent to {sent_count} users.")

        elif cmd == "setbalance":
            user_id_set = int(args[1])
            amount = int(args[2])
            user = get_user(user_id_set)
            if user:
                update_balance(user_id_set, amount - user[4])
                update.message.reply_text(f"Balance set to {amount}.")
            else:
                update.message.reply_text("User not found.")

        elif cmd in ["ban", "unban"]:
            user_id_ban = int(args[1])
            status = 1 if cmd == "ban" else 0
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (status, user_id_ban))
            conn.commit()
            conn.close()
            update.message.reply_text(f"User {user_id_ban} {'banned' if status else 'unbanned'}.")

        elif cmd == "message":
            user_id_msg = int(args[1])
            message = " ".join(args[2:])
            context.bot.send_message(user_id_msg, f"📨 Admin: {message}")
            update.message.reply_text("Sent.")

        elif cmd == "referrals":
            user_id_ref = int(args[1])
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id_ref,))
            count = cursor.fetchone()[0]
            conn.close()
            update.message.reply_text(f"{count} referrals.")

        else:
            update.message.reply_text("Unknown admin command.")
    except Exception as e:
        logger.error(f"Error processing admin command: {e}")
        update.message.reply_text("Error processing admin command.")


# --- Error Handler ---
def error(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")


# --- Main ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()

