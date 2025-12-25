#!/usr/bin/env python3
import asyncio
import logging
import os
import re
from datetime import datetime
from html import escape
import urllib.parse
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from api_handlers import APIHandler
from config import (
    BOT_TOKEN,
    ADMIN_CONTACT,
    BRANDING_FOOTER,
    CHANNEL_LINK_1,
    CHANNEL_LINK_2,
    MIN_DIAMOND_PURCHASE,
    OWNER_ID,
    REFERRAL_REWARD_DIAMOND,
    REQUIRED_CHANNELS,
    SEARCH_LOG_CHANNEL,
    START_LOG_CHANNEL,
    SUDO_USERS,
    VERSION,
)
from database import Database

# Constants
DAILY_FREE_GROUP_LIMIT = 30

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Instances
db = Database()
api_handler = APIHandler()


# Helpers
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_sudo(user_id: int) -> bool:
    return user_id in SUDO_USERS


def is_admin(user_id: int) -> bool:
    return is_owner(user_id) or is_sudo(user_id)


def safe_has_logged_start(user_id: int) -> bool:
    """
    Backward compatible helper: some older deployments may miss has_logged_start on Database.
    """
    checker = getattr(db, "has_logged_start", None)
    if callable(checker):
        return checker(user_id)
    return False


def safe_ensure_daily_counter(user_id: int) -> dict:
    """
    Backward compatible helper: falls back to get_user when ensure_daily_counter is absent.
    """
    ensure = getattr(db, "ensure_daily_counter", None)
    if callable(ensure):
        return ensure(user_id)
    return db.get_user(user_id) or {}


def queue_autodelete(message, context: ContextTypes.DEFAULT_TYPE, delay: int = 300):
    if not message:
        return
    async def _del():
        try:
            await asyncio.sleep(delay)
            await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
        except Exception:
            pass
    try:
        context.application.create_task(_del())
    except Exception:
        asyncio.create_task(_del())

def build_main_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton("🔍 Lookups", callback_data="lookups"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        [InlineKeyboardButton("🎁 Referral", callback_data="referral"),
         InlineKeyboardButton("💎 Buy Diamonds", callback_data="buy_diamonds")],
        [InlineKeyboardButton("🏷 Redeem Code", callback_data="redeem_info")],
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])
    return keyboard


def footer_buttons(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    bot_username = getattr(context.bot, "username", None) or ""
    add_to_group_url = f"https://t.me/{bot_username}?startgroup=true" if bot_username else None
    buttons = [
        [
            InlineKeyboardButton("📢 Updates", url=CHANNEL_LINK_1),
            InlineKeyboardButton("🆘 Support", url=CHANNEL_LINK_2),
        ],
    ]
    if add_to_group_url:
        buttons.append([InlineKeyboardButton("➕ Add me to your group", url=add_to_group_url)])
    buttons.append([InlineKeyboardButton("👤 Admin", url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")])
    return InlineKeyboardMarkup(buttons)


async def referral_button(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> InlineKeyboardMarkup:
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    share_text = (
        "Join this OSINT bot for free searches and earn diamonds per referral! "
        "Start here:"
    )
    share_url = (
        "https://t.me/share/url?"
        f"url={urllib.parse.quote(ref_link)}&"
        f"text={urllib.parse.quote(share_text)}"
    )
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Refer a Friend", url=share_url)]])


def format_home_text(user, user_data, referral_link: str) -> str:
    daily_user = safe_ensure_daily_counter(user.id)
    daily_used = daily_user.get("daily_search_count", 0) if daily_user else 0
    free_left = max(0, DAILY_FREE_GROUP_LIMIT - daily_used)
    return (
        f"╔════════════════════╗\n"
        f"   DataTrace OSINT Bot {VERSION}\n"
        f"╚════════════════════╝\n\n"
        f"Hello <b>{escape(user.first_name)}</b>!\n"
        "Group searches are FREE for everyone. DMs are restricted to admins/sudo.\n\n"
        f"💎 Diamonds: <b>{user_data.get('diamonds', 0)}</b>\n"
        f"🎫 Credits (group): <b>{user_data.get('credits', 0)}</b>\n"
        f"📅 Free group searches left today: <b>{free_left}</b> / {DAILY_FREE_GROUP_LIMIT}\n"
        f"👥 Referrals: <b>{user_data.get('referred_count', 0)}</b> (+{REFERRAL_REWARD_DIAMOND} diamond each)\n"
        f"🛒 Min purchase: {MIN_DIAMOND_PURCHASE} @ 5 INR each\n\n"
        "🔗 Referral link:\n"
        f"<code>{referral_link}</code>\n"
        f"{BRANDING_FOOTER}"
    )


async def safe_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str,
                    parse_mode=ParseMode.HTML, reply_markup: Optional[InlineKeyboardMarkup] = None,
                    autodelete: bool = True):
    try:
        msg = None
        if getattr(update, "message", None):
            msg = await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        else:
            chat_id = update.effective_chat.id if update and update.effective_chat else None
            if chat_id:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
        if autodelete:
            queue_autodelete(msg, context)
        return msg
    except Exception as exc:
        logger.warning(f"Failed to send message: {exc}")
    return None


async def safe_send_document(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path: str, caption: str = None,
                             reply_markup: Optional[InlineKeyboardMarkup] = None, autodelete: bool = True):
    try:
        chat_id = update.effective_chat.id if update and update.effective_chat else None
        file_name = os.path.basename(file_path)
        msg = None
        if getattr(update, "message", None):
            msg = await update.message.reply_document(
                document=InputFile(open(file_path, "rb"), filename=file_name),
                caption=caption,
                reply_markup=reply_markup
            )
        elif chat_id:
            msg = await context.bot.send_document(
                chat_id=chat_id,
                document=InputFile(open(file_path, "rb"), filename=file_name),
                caption=caption,
                reply_markup=reply_markup
            )
        if autodelete:
            queue_autodelete(msg, context)
        return msg
    except Exception as exc:
        logger.warning(f"Failed to send document: {exc}")
    return None


async def log_to_channel(context: ContextTypes.DEFAULT_TYPE, channel_id: int, message: str):
    try:
        await context.bot.send_message(chat_id=channel_id, text=message, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.error(f"Failed to log to channel {channel_id}: {exc}")


async def ensure_user_record(user: Optional[object], referrer_id: Optional[int] = None):
    if not user:
        return None
    existing = db.get_user(user.id)
    if existing:
        return existing
    db.add_user(user.id, user.username, user.first_name, referrer_id)
    return db.get_user(user.id)


async def enforce_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Ensure user joined required channels; returns True if ok."""
    user = update.effective_user
    if not user:
        return False
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel["id"], user.id)
            if member.status in ["left", "kicked"]:
                raise ValueError("not joined")
        except Exception:
            keyboard = [
                [InlineKeyboardButton("Join Updates", url=CHANNEL_LINK_1)],
                [InlineKeyboardButton("Join Support", url=CHANNEL_LINK_2)],
                [InlineKeyboardButton("Verify Membership", callback_data=f"verify_membership_{user.id}")],
            ]
            await safe_send(
                update,
                context,
                "Access restricted. Join both channels first, then tap Verify.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                autodelete=False,
            )
            return False
    return True


# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    if chat_type != "private":
        return

    referrer_id = None
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if user and referrer_id == user.id:
                referrer_id = None
        except Exception:
            referrer_id = None

    if not await enforce_membership(update, context):
        return

    user_data = await ensure_user_record(user, referrer_id)
    db.update_last_active(user.id)

    if referrer_id:
        if not safe_has_logged_start(user.id):
            await log_to_channel(
                context,
                START_LOG_CHANNEL,
                f"🚀 New user via referral\nName: {escape(user.first_name)}\nID: {user.id}\nReferrer: {referrer_id}",
            )
    else:
        if not safe_has_logged_start(user.id):
            await log_to_channel(
                context,
                START_LOG_CHANNEL,
                f"🚀 New user\nName: {escape(user.first_name)}\nID: {user.id}",
            )

    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"

    reply_markup = InlineKeyboardMarkup(build_main_keyboard(user.id))
    await safe_send(update, context, format_home_text(user, user_data, referral_link), reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 <b>Commands</b>\n"
        "• /start - Register & home\n"
        "• /help - This help\n"
        "• /diamonds - Balance\n"
        "• /credits - Group credits/daily quota\n"
        "• /refer - Referral link\n"
        "• /buydiamonds - Purchase info\n"
        "• /redeem <code>CODE</code> - Redeem code\n\n"
        "🔍 <b>Lookups (free in groups)</b>\n"
        "• /num [number] - Number info\n"
        "• /upi [upi_id] - UPI info\n"
        "• /pan [pan] - PAN info\n"
        "• /ip [ip] - IP info\n"
        "• /pak [number] - Pakistan info\n"
        "• /aadhar [number] - Aadhar info\n"
        "• /aadhar2fam [number] - Aadhar family\n"
        "• /rcpdf [plate] - Vehicle RC PDF (5💎 in DM)\n"
        "• /callhis - Call history buy info\n\n"
        "• /iginfo [user] - Instagram profile\n"
        "• /igposts [user] - Instagram posts\n"
        "• /ifsc [code] - Bank IFSC info\n\n"
        "Group: 30 free searches/day. After that, 1 credit per search (redeem-only, not for sale).\n"
        "DM lookups are restricted to admins/sudo. Everyone can search freely in groups until quota."
    )
    await safe_send(update, context, text)


async def diamonds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    user_data = db.get_user(user.id)
    if not user_data:
        await safe_send(update, context, "Use /start first.")
        return
    text = (
        "💎 <b>Diamond Balance</b>\n"
        f"• Diamonds: <b>{user_data.get('diamonds', 0)}</b>\n"
        f"• Referrals: <b>{user_data.get('referred_count', 0)}</b> (each +{REFERRAL_REWARD_DIAMOND})\n"
        f"• Minimum purchase: {MIN_DIAMOND_PURCHASE} @ {MIN_DIAMOND_PURCHASE * 5} INR\n"
        f"• Contact: {ADMIN_CONTACT}"
    )
    await safe_send(update, context, text)

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    user_data = safe_ensure_daily_counter(user.id)
    if not user_data:
        await safe_send(update, context, "Use /start first.")
        return
    free_left = max(0, DAILY_FREE_GROUP_LIMIT - user_data.get("daily_search_count", 0))
    text = (
        "🎫 <b>Group Credits</b>\n"
        f"• Credits: <b>{user_data.get('credits', 0)}</b>\n"
        f"• Free searches left today: <b>{free_left}</b> / {DAILY_FREE_GROUP_LIMIT}\n"
        "Credits are only for group searches and cannot be bought.\n"
        "Redeem codes can add credits or diamonds."
    )
    await safe_send(update, context, text)


async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    data = db.get_user(user.id)
    if not data:
        await safe_send(update, context, "Use /start first.")
        return
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    text = (
        "🔗 <b>Your Referral Link</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"Reward: +{REFERRAL_REWARD_DIAMOND} diamond per successful referral."
    )
    await safe_send(update, context, text, autodelete=False)


async def buydiamonds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Contact Admin", url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")]]
    text = (
        "🛒 <b>Buy Diamonds</b>\n"
        f"Minimum purchase: {MIN_DIAMOND_PURCHASE}\n"
        f"Price: {MIN_DIAMOND_PURCHASE * 5} INR minimum (5 INR/diamond)\n"
        "Pay manually to admin and diamonds will be added to your account."
    )
    await safe_send(update, context, text, reply_markup=InlineKeyboardMarkup(keyboard))

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if not context.args:
        return await safe_send(update, context, "Usage: /redeem <code>CODE</code>")
    code = context.args[0].strip().upper()
    success, msg = db.redeem_code(user.id, code)
    if success:
        await safe_send(update, context, f"✅ {msg}")
    else:
        await safe_send(update, context, f"⚠️ {msg}")

async def create_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    if len(context.args) < 3:
        return await safe_send(update, context, "Usage: /createcode diamonds|credits CODE AMOUNT")
    code_type = context.args[0].lower()
    code = context.args[1].strip().upper()
    try:
        amount = int(context.args[2])
    except ValueError:
        return await safe_send(update, context, "Amount must be a number.")
    if code_type not in ["diamonds", "credits"]:
        return await safe_send(update, context, "Type must be diamonds or credits.")
    if db.create_redeem_code(code, amount, code_type):
        await safe_send(update, context, f"✅ Code created: {code} (+{amount} {code_type})")
    else:
        await safe_send(update, context, "⚠️ Code already exists.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer(cache_time=120)
    except Exception:
        pass
    user = query.from_user
    user_data = db.get_user(user.id) or {}
    if not user_data:
        user_data = await ensure_user_record(user) or {}
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"

    if query.data == "lookups":
        text = (
            "🔍 <b>Lookups (free in groups)</b>\n"
            "• /num [number]\n"
            "• /upi [upi_id]\n"
            "• /pan [pan]\n"
            "• /ip [ip]\n"
            "• /pak [number]\n"
            "• /aadhar [number]\n"
            "• /aadhar2fam [number]\n"
            "• /rcpdf [plate] - 5💎 in DM\n"
            "• /iginfo [user]\n"
            "• /igposts [user]\n"
            "• /ifsc [code]\n"
            "• /callhis - Call history buy info\n\n"
            "DM lookups are restricted to admins/sudo. Use group for free searches."
        )
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))

    if query.data == "help":
        text = (
            "📜 <b>Commands</b>\n"
            "• /start - Register & home\n"
            "• /help - This help\n"
            "• /diamonds - Balance\n"
            "• /refer - Referral link\n"
            "• /buydiamonds - Purchase info\n\n"
            "🔍 <b>Lookups (free in groups)</b>\n"
            "• /num [number] - Number info\n"
            "• /upi [upi_id] - UPI info\n"
            "• /pan [pan] - PAN info\n"
            "• /ip [ip] - IP info\n"
            "• /pak [number] - Pakistan info\n"
            "• /aadhar [number] - Aadhar info\n"
            "• /aadhar2fam [number] - Aadhar family\n"
            "• /rcpdf [plate] - Vehicle RC PDF (5💎 in DM)\n"
            "• /callhis - Call history buy info\n\n"
            "DM lookups are restricted to admins/sudo. Everyone can search freely in groups."
        )
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))

    if query.data == "referral":
        text = (
            "🔗 <b>Your Referral Link</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"Reward: +{REFERRAL_REWARD_DIAMOND} diamond per successful referral."
        )
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))

    if query.data == "redeem_info":
        text = (
            "🏷 <b>Redeem Codes</b>\n"
            "Use /redeem <code>CODE</code> to apply.\n\n"
            "Types:\n"
            "• Credits: adds group credits (used after 30 free searches/day)\n"
            "• Diamonds: adds diamonds for paid DM lookups\n\n"
            "Credits cannot be bought. Diamonds are purchased via admin."
        )
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))

    if query.data == "buy_diamonds":
        keyboard = [[InlineKeyboardButton("Contact Admin", url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]
        text = (
            "🛒 <b>Buy Diamonds</b>\n"
            f"Minimum purchase: {MIN_DIAMOND_PURCHASE}\n"
            f"Price: {MIN_DIAMOND_PURCHASE * 5} INR minimum (5 INR/diamond)\n"
            "Pay manually to admin and diamonds will be added to your account."
        )
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    if query.data == "admin_panel":
        if not is_admin(user.id):
            return
        text = (
            "🛠 <b>Admin Panel</b>\n"
            "/adddiamonds [user] [amount]\n"
            "/removediamonds [user] [amount]\n"
            "/createcode diamonds|credits CODE AMOUNT\n"
            "/ban [user]\n"
            "/unban [user]\n"
            "/stats\n"
            "/gcast [message]"
        )
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]))

    if query.data == "back_main":
        text = format_home_text(user, user_data, referral_link)
        return await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(build_main_keyboard(user.id)))


async def add_diamonds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    if len(context.args) < 2:
        return await safe_send(update, context, "Usage: /adddiamonds [user_id] [amount]")
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        return await safe_send(update, context, "Invalid arguments.")
    if db.update_diamonds(user_id, amount, "add"):
        await safe_send(update, context, f"Added {amount} diamonds to {user_id}.")
    else:
        await safe_send(update, context, "Failed to add diamonds.")


async def remove_diamonds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    if len(context.args) < 2:
        return await safe_send(update, context, "Usage: /removediamonds [user_id] [amount]")
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        return await safe_send(update, context, "Invalid arguments.")
    if db.update_diamonds(user_id, amount, "deduct"):
        await safe_send(update, context, f"Removed {amount} diamonds from {user_id}.")
    else:
        await safe_send(update, context, "Failed to remove diamonds.")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    if not context.args:
        return await safe_send(update, context, "Usage: /ban [user_id]")
    try:
        target_id = int(context.args[0])
    except ValueError:
        return await safe_send(update, context, "Invalid user id.")
    db.ban_user(target_id)
    await safe_send(update, context, f"Banned {target_id}.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    if not context.args:
        return await safe_send(update, context, "Usage: /unban [user_id]")
    try:
        target_id = int(context.args[0])
    except ValueError:
        return await safe_send(update, context, "Invalid user id.")
    db.unban_user(target_id)
    await safe_send(update, context, f"Unbanned {target_id}.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    stats = db.get_stats()
    text = (
        "📊 <b>Stats</b>\n"
        f"• Users: {stats.get('total_users', 0)}\n"
        f"• Searches: {stats.get('total_searches', 0)}\n"
        f"• Banned: {stats.get('banned_users', 0)}\n"
        f"• Referrals: {stats.get('total_referrals', 0)}\n"
        f"• Diamonds in DB: {stats.get('total_diamonds', 0)}\n"
        f"• Credits in DB: {stats.get('total_credits', 0)}"
    )
    await safe_send(update, context, text)


async def gcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await safe_send(update, context, "Access denied.")
    if not context.args:
        return await safe_send(update, context, "Usage: /gcast [message]")
    message = " ".join(context.args)
    user_ids = db.get_all_user_ids()
    success = 0
    failed = 0
    await safe_send(update, context, f"Broadcasting to {len(user_ids)} users...")
    for user_id in user_ids:
        try:
            await context.bot.send_message(user_id, message, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await safe_send(update, context, f"Broadcast complete.\nSuccess: {success}\nFailed: {failed}")


# Lookup handling
async def handle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, lookup_type: str, query: str,
                        cost_diamonds: int = 0, expect_file: bool = False):
    user = update.effective_user
    chat = update.effective_chat
    user_id = user.id if user else None
    chat_type = chat.type if chat else "private"
    if not user_id:
        return

    # Enforce channel membership for non-admin users
    if not is_admin(user_id):
        ok = await enforce_membership(update, context)
        if not ok:
            return

    # Auto-register users from groups
    if not db.get_user(user_id):
        await ensure_user_record(user)
    db.update_last_active(user_id)

    if db.is_banned(user_id):
        return await safe_send(update, context, "You are banned from using this bot.")

    if chat_type == "private" and not is_admin(user_id):
        return await safe_send(
            update,
            context,
            f"Searches are disabled in DM. Use the support group: {CHANNEL_LINK_2}",
        )

    # Group quota handling (non-admin)
    if chat_type != "private" and not is_admin(user_id):
        user_data = safe_ensure_daily_counter(user_id)
        daily_used = user_data.get("daily_search_count", 0) if user_data else 0
        credits = user_data.get("credits", 0) if user_data else 0
        if daily_used >= DAILY_FREE_GROUP_LIMIT:
            if credits <= 0:
                ref_markup = await referral_button(context, user_id)
                return await safe_send(
                    update,
                    context,
                    "Daily free limit reached (30).\nAdd credits via redeem code or refer friends to earn diamonds.\nUse /refer for details.",
                    reply_markup=ref_markup,
                    autodelete=False,
                )
            else:
                db.update_credits(user_id, 1, "deduct")
        # increment daily counter
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET daily_search_count = daily_search_count + 1, last_search_date = ? WHERE user_id = ?",
            (datetime.now().strftime("%Y-%m-%d"), user_id),
        )
        conn.commit()
        conn.close()
        new_daily_count = daily_used + 1
    else:
        new_daily_count = None

    if db.is_blacklisted(query):
        return await safe_send(update, context, "This query is blacklisted.")
    if db.is_protected(query) and not is_owner(user_id):
        return await safe_send(update, context, "This number is protected.")

    # Charging logic
    charge = 0 if is_admin(user_id) else (cost_diamonds if chat_type == "private" else 0)

    if charge:
        user_data = db.get_user(user_id)
        balance = user_data.get("diamonds", 0) if user_data else 0
        if balance < charge:
            return await safe_send(
                update,
                context,
                f"Not enough diamonds ({charge} needed). Minimum top-up {MIN_DIAMOND_PURCHASE} via {ADMIN_CONTACT}.",
                parse_mode=None,
            )
        db.update_diamonds(user_id, charge, "deduct")

    await safe_send(update, context, "🔍 Searching...", autodelete=False)

    db.log_search(user_id, lookup_type, query)
    await log_to_channel(
        context,
        SEARCH_LOG_CHANNEL,
        f"🔍 Search\nUser: {escape(user.first_name)} ({user_id})\nType: {lookup_type}\nQuery: {query}",
    )

    result = None
    file_path = None
    try:
        if lookup_type == "upi":
            result = await api_handler.fetch_upi_info(query)
        elif lookup_type == "pan":
            result = await api_handler.fetch_pan_info(query)
        elif lookup_type == "number":
            result = await api_handler.fetch_number_info(query)
        elif lookup_type == "number_alt":
            result = await api_handler.fetch_number_alt_info(query)
        elif lookup_type == "ip":
            result = await api_handler.fetch_ip_info(query)
        elif lookup_type == "pakistan":
            result = await api_handler.fetch_pakistan_info(query)
        elif lookup_type == "aadhar":
            result = await api_handler.fetch_aadhar_info(query)
        elif lookup_type == "aadhar_family":
            result = await api_handler.fetch_aadhar_family(query)
        elif lookup_type == "insta_profile":
            result = await api_handler.fetch_instagram_profile(query)
        elif lookup_type == "insta_posts":
            result = await api_handler.fetch_instagram_posts(query)
        elif lookup_type == "bank_ifsc":
            result = await api_handler.fetch_ifsc_info(query)
        elif lookup_type == "vehicle_rc_pdf":
            file_path = await api_handler.fetch_vehicle_rc_pdf(query)
    except Exception as exc:
        logger.exception(f"Lookup error for {lookup_type} {query}: {exc}")
        result = f"Lookup error: {exc}"

    if expect_file:
        if file_path and os.path.exists(file_path):
            await safe_send_document(update, context, file_path, caption="RC PDF")
            try:
                os.remove(file_path)
            except OSError:
                pass
        else:
            await safe_send(update, context, "Failed to fetch RC PDF.")
        return

    if not result:
        await safe_send(update, context, "No data returned.")
        return

    try:
        # strip text footer, add button footer
        if isinstance(result, str) and BRANDING_FOOTER in result:
            result = result.replace(BRANDING_FOOTER, "").strip()

        if isinstance(result, str) and len(result) > 3500:
            safe_fname = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{lookup_type}_{query}")[:120]
            file_name = f"{safe_fname}.txt"
            with open(file_name, "w", encoding="utf-8") as handle:
                handle.write(result)
            await safe_send_document(update, context, file_name, caption="Result too long, sent as file.", reply_markup=footer_buttons(context))
            try:
                os.remove(file_name)
            except OSError:
                pass
        else:
            await safe_send(update, context, result, reply_markup=footer_buttons(context))

        # Refer prompt every 3 searches (group, non-admin)
        if new_daily_count and new_daily_count % 3 == 0 and chat_type != "private" and not is_admin(user_id):
            ref_markup = await referral_button(context, user_id)
            await safe_send(
                update,
                context,
                "🎁 Refer a friend and earn +1💎.\nTap below to share your link.\nUse /refer for details.",
                reply_markup=ref_markup,
                autodelete=False,
            )
    except Exception as exc:
        logger.exception(f"Failed to deliver result: {exc}")
        await safe_send(update, context, "Failed to deliver result.")


# Command wrappers
async def num_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /num [number]")
    await handle_lookup(update, context, "number", "".join(context.args))


async def num2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /num2 [number]")
    await handle_lookup(update, context, "number_alt", "".join(context.args))


async def upi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /upi [upi_id]")
    await handle_lookup(update, context, "upi", context.args[0])


async def pan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /pan [pan_number]")
    await handle_lookup(update, context, "pan", context.args[0].upper())


async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /ip [ip_address]")
    await handle_lookup(update, context, "ip", context.args[0])


async def pak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /pak [number]")
    await handle_lookup(update, context, "pakistan", "".join(context.args))


async def aadhar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /aadhar [number]")
    await handle_lookup(update, context, "aadhar", "".join(context.args))


async def aadhar2fam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /aadhar2fam [number]")
    await handle_lookup(update, context, "aadhar_family", "".join(context.args))


async def vehicle_rc_pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /rcpdf [plate]")
    await handle_lookup(update, context, "vehicle_rc_pdf", "".join(context.args), cost_diamonds=5, expect_file=True)

async def iginfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /iginfo [username]")
    username = context.args[0].lstrip("@")
    await handle_lookup(update, context, "insta_profile", username)

async def igposts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /igposts [username]")
    username = context.args[0].lstrip("@")
    await handle_lookup(update, context, "insta_posts", username)

async def ifsc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await safe_send(update, context, "Usage: /ifsc [code]")
    code = context.args[0].upper()
    await handle_lookup(update, context, "bank_ifsc", code)


# Direct input handler
async def handle_direct_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not getattr(update, "message", None) or not update.message.text:
        return
    text = update.message.text.strip()
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    if chat_type != "private":
        bot_username = (await context.bot.get_me()).username
        if f"@{bot_username}" not in text and not text.startswith("/"):
            return
        text = text.replace(f"@{bot_username}", "").strip()
    if text.startswith("/"):
        return
    if "@" in text and len(text.split("@")) == 2:
        return await handle_lookup(update, context, "upi", text)
    if text.startswith("+92") or (text.isdigit() and len(text) == 12 and text.startswith("92")):
        return await handle_lookup(update, context, "pakistan", text)
    if text.startswith("+91") or (text.isdigit() and len(text) == 10):
        number = text.replace("+91", "").replace("+", "")
        return await handle_lookup(update, context, "number", number)
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", text):
        return await handle_lookup(update, context, "ip", text)
    if text.isdigit() and len(text) == 12:
        return await handle_lookup(update, context, "aadhar", text)


async def call_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📞 Call History\n"
        "This is a paid add-on.\n"
        f"To buy, contact {ADMIN_CONTACT}"
    )
    await safe_send(update, context, msg, parse_mode=None)


async def verify_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    try:
        _, target_id = query.data.split("_", 1)
    except Exception:
        target_id = None
    # Allow any user to verify themselves even if they tapped another user's button
    await query.answer()
    if str(query.from_user.id) != (target_id or ""):
        # Trigger membership check for this user; enforce_membership will send their own verify prompt if needed
        if await enforce_membership(update, context):
            await safe_send(update, context, "✅ Verification done! Use /start.", autodelete=False)
        return
    if await enforce_membership(update, context):
        await query.edit_message_text("✅ Verification done! Use /start.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing.")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("diamonds", diamonds_command))
    application.add_handler(CommandHandler("credits", credits_command))
    application.add_handler(CommandHandler("refer", refer_command))
    application.add_handler(CommandHandler("buydiamonds", buydiamonds_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("createcode", create_code_command))

    application.add_handler(CommandHandler("num", num_command))
    application.add_handler(CommandHandler("num2", num2_command))
    application.add_handler(CommandHandler("upi", upi_command))
    application.add_handler(CommandHandler("pan", pan_command))
    application.add_handler(CommandHandler("ip", ip_command))
    application.add_handler(CommandHandler("pak", pak_command))
    application.add_handler(CommandHandler("aadhar", aadhar_command))
    application.add_handler(CommandHandler("aadhar2fam", aadhar2fam_command))
    application.add_handler(CommandHandler("rcpdf", vehicle_rc_pdf_command))
    application.add_handler(CommandHandler("iginfo", iginfo_command))
    application.add_handler(CommandHandler("igposts", igposts_command))
    application.add_handler(CommandHandler("ifsc", ifsc_command))
    application.add_handler(CommandHandler("callhis", call_history_command))

    application.add_handler(CommandHandler("adddiamonds", add_diamonds_command))
    application.add_handler(CommandHandler("removediamonds", remove_diamonds_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("gcast", gcast_command))

    application.add_handler(CallbackQueryHandler(button_callback, pattern="^(lookups|help|referral|buy_diamonds|admin_panel|back_main|redeem_info)$"))
    application.add_handler(CallbackQueryHandler(verify_membership_callback, pattern="^verify_membership_\\d+$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direct_input))
    application.add_error_handler(error_handler)

    logger.info("Bot started.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
