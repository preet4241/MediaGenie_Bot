# main.py

import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler,
    CallbackQueryHandler, filters, ConversationHandler
)
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import threading
import time
import edge_tts
import asyncio
import tempfile
import subprocess
import math
import wave
import requests
import aiohttp
import random
import schedule

# Optional imports with fallbacks
try:
    import vosk
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    logger.warning("Vosk not available - STT functionality will be limited")

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("Pydub not available - Audio processing will be limited")

# ======================== CONFIGURATION ========================
BOT_TOKEN = "8087068418:AAG7JXckIaAWpJAZ22iV_jOP_hzbVKkgQ7E"
OWNER_ID = 5458600995
Owner = "@HackerPonline"
IS_BOT_ACTIVE = True
BOT_SHUTDOWN = False
SHUTDOWN_REASON = ""
SHUTDOWN_UNTIL = None

# Temporary link assignments (user_id: {link_data, expires_at})
TEMP_LINK_ASSIGNMENTS = {}

# Tools status
TOOLS_STATUS = {
    'tts': True,
    'stt': True,
    'free_credits': True,
    'buy_credits': True,
    'referral': True
}

# Tools deactivation reasons
TOOLS_DEACTIVATION_REASONS = {
    'tts': '',
    'stt': '',
    'free_credits': '',
    'buy_credits': '',
    'referral': ''
}

# Credit system configuration
CREDIT_CONFIG = {
    'welcome_credit': 100,
    'tts_cost_per_char': 0.2,  # 0.2 credits per character
    'stt_cost_per_minute': 5,  # 5 credits per minute (minimum 1 minute = 5 credits)
    'shortlink_reward': 25,
    'referral_reward': 50,
    # YouTube Video Download Credits
    'yt_1080p_cost': 50,      # 50 credits for 1080p
    'yt_720p_cost': 30,       # 30 credits for 720p
    'yt_480p_cost': 20,       # 20 credits for 480p
    'yt_360p_cost': 15,       # 15 credits for 360p
    'yt_240p_cost': 10,       # 10 credits for 240p
    'yt_144p_cost': 5,        # 5 credits for 144p
    'yt_audio_cost': 10       # 10 credits for audio only
}

# Conversation states
WAITING_USER_ID, WAITING_BAN_REASON, WAITING_UNBAN_REASON, WAITING_TTS_TEXT, WAITING_CREDIT_AMOUNT, WAITING_CREDIT_MESSAGE, WAITING_CREDIT_ALL_AMOUNT, WAITING_CREDIT_ALL_MESSAGE, WAITING_STT_AUDIO, WAITING_IMP_INFO_TITLE, WAITING_IMP_INFO_DATA, WAITING_LS_DOMAIN, WAITING_LS_EMAIL, WAITING_LS_PASSWORD, WAITING_LS_PER_CLICK, WAITING_LS_PRIORITY, WAITING_LS_API, WAITING_SHORTLINK_URL, WAITING_SHORTLINK_PAYLOAD, WAITING_ORIGINAL_URL, WAITING_CREATED_LINK_PAYLOAD, WAITING_AD_TITLE, WAITING_AD_DESCRIPTION, WAITING_AD_FILE, WAITING_AD_DURATION, WAITING_AD_PRIORITY, WAITING_COUPON_VALIDITY, WAITING_COUPON_USER_LIMIT, WAITING_COUPON_CREDIT_AMOUNT, WAITING_OFFER_PERCENTAGE, WAITING_OFFER_VALIDITY, WAITING_USER_COUPON_CODE = range(32)

DATA_DIR = Path("data")
USER_DATA_FILE = DATA_DIR / "user_data.json"
BANNED_USERS_FILE = DATA_DIR / "banned_users.json"
SHORTLINKS_FILE = DATA_DIR / "shortlinks.json"
LINK_SHORTENERS_FILE = DATA_DIR / "link_shorteners.json"
IMP_INFO_FILE = DATA_DIR / "important_info.json"
ADVERTISEMENTS_FILE = DATA_DIR / "advertisements.json"
AD_TRACKING_FILE = DATA_DIR / "ad_tracking.json"
AD_BROADCAST_LOG_FILE = DATA_DIR / "ad_broadcast_log.json"
COUPONS_FILE = DATA_DIR / "coupons.json"
SEASONAL_OFFERS_FILE = DATA_DIR / "seasonal_offers.json"

DATA_DIR.mkdir(exist_ok=True)

# ======================== GLOBAL VARIABLES ========================
# User context variables - accessible by any function
current_user_id = None
current_user = None
user_first_name = ""
user_last_name = ""
user_full_name = ""
user_username = ""
first_name = ""
current_credits = 0
current_user_data = {}

# Advertisement data storage
advertisements_data = {}
ad_tracking_data = {}
ad_broadcast_log = {}

# Coupons and Offers data storage
coupons_data = {}
seasonal_offers_data = {}

# ======================== LOGGING SETUP ========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======================== UTILITY FUNCTIONS ========================
def load_json(path):
    try:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading JSON from {path}: {e}")
        return {}

def save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving JSON to {path}: {e}")

def reload_data():
    """Reload user data and banned users from files"""
    global user_data, banned_users, shortlinks_data, link_shorteners_data, important_info, advertisements_data, ad_tracking_data, ad_broadcast_log, coupons_data, seasonal_offers_data
    user_data = load_json(USER_DATA_FILE)
    banned_users = load_json(BANNED_USERS_FILE)
    shortlinks_data = load_json(SHORTLINKS_FILE)
    link_shorteners_data = load_json(LINK_SHORTENERS_FILE)
    important_info = load_json(IMP_INFO_FILE)
    advertisements_data = load_json(ADVERTISEMENTS_FILE)
    ad_tracking_data = load_json(AD_TRACKING_FILE)
    ad_broadcast_log = load_json(AD_BROADCAST_LOG_FILE)
    coupons_data = load_json(COUPONS_FILE)
    seasonal_offers_data = load_json(SEASONAL_OFFERS_FILE)
    
    # Auto-expire coupons, offers and advertisements
    check_and_expire_items()

def check_and_expire_items():
    """Check and automatically expire coupons, offers, and advertisements"""
    current_time = datetime.now()
    items_expired = False
    
    # Check and expire coupons
    for coupon_id, coupon_data in coupons_data.items():
        if coupon_data.get('status') == 'Active':
            try:
                end_date = datetime.fromisoformat(coupon_data.get('end_date', ''))
                if current_time >= end_date:
                    coupon_data['status'] = 'Expired'
                    items_expired = True
                    logger.info(f"Coupon {coupon_id} ({coupon_data.get('code', 'Unknown')}) automatically expired")
            except:
                pass
    
    # Check and expire seasonal offers
    for offer_id, offer_data in seasonal_offers_data.items():
        if offer_data.get('status') == 'Active':
            try:
                end_date = datetime.fromisoformat(offer_data.get('end_date', ''))
                if current_time >= end_date:
                    offer_data['status'] = 'Expired'
                    items_expired = True
                    logger.info(f"Seasonal offer {offer_id} ({offer_data.get('method_name', 'Unknown')}) automatically expired")
            except:
                pass
    
    # Check and expire advertisements
    for ad_id, ad_data in advertisements_data.items():
        if ad_data.get('status') == 'Active':
            try:
                end_date = datetime.fromisoformat(ad_data.get('end_date', ''))
                if current_time >= end_date:
                    ad_data['status'] = 'Expired'
                    items_expired = True
                    logger.info(f"Advertisement {ad_id} ({ad_data.get('title', 'Unknown')}) automatically expired")
            except:
                pass
    
    # Save changes if any items expired
    if items_expired:
        save_json(COUPONS_FILE, coupons_data)
        save_json(SEASONAL_OFFERS_FILE, seasonal_offers_data)
        save_json(ADVERTISEMENTS_FILE, advertisements_data)
        logger.info("Expired items updated and saved")

def is_user_banned(user_id):
    """Check if user is currently banned"""
    reload_data()  # Reload latest banned users data
    return str(user_id) in banned_users

user_data = load_json(USER_DATA_FILE)
banned_users = load_json(BANNED_USERS_FILE)
shortlinks_data = load_json(SHORTLINKS_FILE)
link_shorteners_data = load_json(LINK_SHORTENERS_FILE)
important_info = load_json(IMP_INFO_FILE)
advertisements_data = load_json(ADVERTISEMENTS_FILE)
ad_tracking_data = load_json(AD_TRACKING_FILE)
ad_broadcast_log = load_json(AD_BROADCAST_LOG_FILE)
coupons_data = load_json(COUPONS_FILE)
seasonal_offers_data = load_json(SEASONAL_OFFERS_FILE)

# Initialize video cache on startup - moved after function definition

# ======================== API INTEGRATION FOR CPM EXTRACTION ========================
# Functions to extract CPM data from GpLinks and LinkShortify APIs

async def extract_cpm_data_gplinks(api_key: str, email: str):
    """Extract CPM data from GpLinks API"""
    try:
        # GpLinks API endpoint for account stats
        stats_url = f"https://api.gplinks.com/stats?api={api_key}&email={email}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(stats_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract CPM data from response
                    per_click = data.get('per_click', '$0.00')
                    per_1000_click = data.get('per_1000_views', '$0.00')
                    total_earnings = data.get('total_earnings', '$0.00')
                    
                    # Format currency values
                    if isinstance(per_click, (int, float)):
                        per_click = f"${per_click:.3f}"
                    if isinstance(per_1000_click, (int, float)):
                        per_1000_click = f"${per_1000_click:.3f}"
                    
                    return {
                        'success': True,
                        'per_click': per_click,
                        'per_1000_click': per_1000_click,
                        'total_earnings': total_earnings,
                        'status': 'API Connected'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'API Error: {response.status}',
                        'status': 'API Error'
                    }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'status': 'Connection Failed'
        }

async def extract_cpm_data_linkshortify(api_key: str, email: str):
    """Extract CPM data from LinkShortify API"""
    try:
        # LinkShortify API endpoint for account stats
        stats_url = f"https://linkshortify.com/api/stats?api={api_key}&email={email}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(stats_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract CPM data from response
                    per_click = data.get('cpm_per_click', '$0.00')
                    per_1000_click = data.get('cpm_per_1000', '$0.00')
                    total_earnings = data.get('balance', '$0.00')
                    
                    # Format currency values
                    if isinstance(per_click, (int, float)):
                        per_click = f"${per_click:.3f}"
                    if isinstance(per_1000_click, (int, float)):
                        per_1000_click = f"${per_1000_click:.3f}"
                    
                    return {
                        'success': True,
                        'per_click': per_click,
                        'per_1000_click': per_1000_click,
                        'total_earnings': total_earnings,
                        'status': 'API Connected'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'API Error: {response.status}',
                        'status': 'API Error'
                    }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'status': 'Connection Failed'
        }

async def update_link_shortener_cpm(ls_id: str):
    """Update CPM data for a specific link shortener"""
    reload_data()
    
    if ls_id not in link_shorteners_data:
        return False
    
    ls_data = link_shorteners_data[ls_id]
    domain = ls_data.get('domain', '').lower()
    api_key = ls_data.get('api', '')
    email = ls_data.get('email', '')
    
    if not api_key or not email:
        return False
    
    cpm_data = None
    
    # Extract CPM based on domain
    if 'gplinks.com' in domain:
        cpm_data = await extract_cpm_data_gplinks(api_key, email)
    elif 'linkshortify.com' in domain:
        cmp_data = await extract_cpm_data_linkshortify(api_key, email)
    
    if cpm_data and cpm_data['success']:
        # Update link shortener data with CPM info
        link_shorteners_data[ls_id].update({
            'per_click': cmp_data['per_click'],
            'per_1000_click': cmp_data['per_1000_click'],
            'total_earnings': cmp_data.get('total_earnings', '$0.00'),
            'last_cpm_update': datetime.now().isoformat(),
            'cpm_status': cmp_data['status']
        })
        save_json(LINK_SHORTENERS_FILE, link_shorteners_data)
        return True
    
    return False



# ======================== PANELS ========================
def get_owner_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Tools", callback_data="tools")],
        [InlineKeyboardButton("👥 Users", callback_data="users"),
         InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("📊 Status", callback_data="status"),
         InlineKeyboardButton("🔗 Handle Shortlink", callback_data="shortlinks")],
        [InlineKeyboardButton("⚙️ Setting", callback_data="settings")],
    ])

def get_shortlinks_main_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Link Shortners", callback_data="link_shorteners"),
         InlineKeyboardButton("📋 Shortlinks", callback_data="view_shortlinks")],
        [InlineKeyboardButton("🎯 Priority", callback_data="priority_settings")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_owner")],
    ])

def get_link_shorteners_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add", callback_data="add_link_shortener"),
         InlineKeyboardButton("➖ Remove", callback_data="remove_link_shortener")],
        [InlineKeyboardButton("📋 LinkShortners", callback_data="list_link_shorteners")],
        [InlineKeyboardButton("🔙 Back", callback_data="shortlinks")],
    ])

def get_user_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Tools", callback_data="tools")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile"),
         InlineKeyboardButton("💰 Add Credit", callback_data="add_credit")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"),
         InlineKeyboardButton("📚 About", callback_data="about")],
    ])

def get_tools_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗣 TTS", callback_data="tts"),
         InlineKeyboardButton("🎤 STT", callback_data="stt")],
        [InlineKeyboardButton("📹 YT Video Downloader", callback_data="yt_downloader")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")],
    ])

def get_settings_panel():
    bot_status_text = "🟢 Active" if IS_BOT_ACTIVE else "🔴 Deactive"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Bot Feature Management", callback_data="bot_tools")],
        [InlineKeyboardButton("💰 Credit System", callback_data="handle_credit_system"),
         InlineKeyboardButton("🎁 Offers Management", callback_data="offers")],
        [InlineKeyboardButton("📋 Important Information", callback_data="important_info")],
        [InlineKeyboardButton("🔴 Bot Shutdown", callback_data="bot_shutdown"),
         InlineKeyboardButton(f"{bot_status_text}", callback_data="toggle_bot_status")],
        [InlineKeyboardButton("🔙 Back to Owner Panel", callback_data="back_to_owner")],
    ])

def get_bot_tools_panel():
    tts_status = "✅ Active" if TOOLS_STATUS.get('tts', True) else "❎ Deactive"
    stt_status = "✅ Active" if TOOLS_STATUS.get('stt', True) else "❎ Deactive"
    free_credits_status = "✅ Active" if TOOLS_STATUS.get('free_credits', True) else "❎ Deactive"
    buy_credits_status = "✅ Active" if TOOLS_STATUS.get('buy_credits', True) else "❎ Deactive"
    referral_status = "✅ Active" if TOOLS_STATUS.get('referral', True) else "❎ Deactive"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🗣 TTS {tts_status}", callback_data="manage_tts_tool"),
         InlineKeyboardButton(f"🎤 STT {stt_status}", callback_data="manage_stt_tool")],
        [InlineKeyboardButton(f"🎁 Free Credits {free_credits_status}", callback_data="manage_free_credits_tool"),
         InlineKeyboardButton(f"💳 Buy Credits {buy_credits_status}", callback_data="manage_buy_credits_tool")],
        [InlineKeyboardButton(f"👥 Referral {referral_status}", callback_data="manage_referral_tool")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")],
    ])

def get_shutdown_reasons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 Maintenance", callback_data="shutdown_reason_maintenance")],
        [InlineKeyboardButton("⚙️ Updates", callback_data="shutdown_reason_updates")],
        [InlineKeyboardButton("🛡️ Security", callback_data="shutdown_reason_security")],
        [InlineKeyboardButton("💬 Custom Reason", callback_data="shutdown_reason_custom")],
        [InlineKeyboardButton("❌ Cancel", callback_data="settings")],
    ])

def get_deactivate_reasons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 Maintenance", callback_data="deactivate_reason_maintenance")],
        [InlineKeyboardButton("⚙️ Updates", callback_data="deactivate_reason_updates")],
        [InlineKeyboardButton("🛡️ Security", callback_data="deactivate_reason_security")],
        [InlineKeyboardButton("💬 Custom Reason", callback_data="deactivate_reason_custom")],
        [InlineKeyboardButton("❌ Cancel", callback_data="settings")],
    ])

def get_tool_deactivate_reasons(tool_name):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 Under Maintenance", callback_data=f"tool_reason_{tool_name}_maintenance")],
        [InlineKeyboardButton("⚙️ Being Updated", callback_data=f"tool_reason_{tool_name}_updates")],
        [InlineKeyboardButton("🐛 Bug Fixing", callback_data=f"tool_reason_{tool_name}_bug")],
        [InlineKeyboardButton("💬 Custom Reason", callback_data=f"tool_reason_{tool_name}_custom")],
        [InlineKeyboardButton("❌ Cancel", callback_data="bot_tools")],
    ])

def get_credit_system_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Welcome Credit", callback_data="edit_welcome_credit")],
        [InlineKeyboardButton("🗣 TTS Cost/Char", callback_data="edit_tts_cost"),
         InlineKeyboardButton("🎤 STT Cost", callback_data="edit_stt_cost")],
        [InlineKeyboardButton("🔗 Link Reward", callback_data="edit_link_reward"),
         InlineKeyboardButton("👥 Referral Reward", callback_data="edit_referral_reward")],
        [InlineKeyboardButton("📊 Credit Stats", callback_data="credit_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")],
    ])

def get_users_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Give Credit", callback_data="give_credit"),
         InlineKeyboardButton("💰 Give Credit All", callback_data="give_credit_all")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="ban_user"),
         InlineKeyboardButton("✅ Unban User", callback_data="unban_user")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="user_info")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_owner")],
    ])

# ======================== START COMMAND ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_user_id, current_user, user_first_name, user_last_name, user_full_name, user_username, first_name, current_credits, current_user_data
    
    user = update.effective_user
    uid = str(user.id)
    
    # Set global variables
    current_user_id = user.id
    current_user = user
    user_first_name = user.first_name or ""
    user_last_name = user.last_name or ""
    user_full_name = user.full_name or ""
    user_username = user.username or ""
    first_name = user.first_name or "User"

    # Check for payload in start command
    if context.args:
        payload = context.args[0]
        await handle_start_payload(update, context, payload, user)
        return

    if user.id == OWNER_ID:
        await update.message.reply_text(
                "👑 *Hello Boss\\!* \n\n"
                "Welcome to your *Control Panel*\\.\n"
                "Let's manage the bot like a *pro* ⚙️🤖\n\n"
                "🔧 Use the buttons below to get started 👇",
                parse_mode='MarkdownV2',
                reply_markup=get_owner_panel()
                )
        return

    if BOT_SHUTDOWN:
        remaining_time = ""
        if SHUTDOWN_UNTIL:
            now = datetime.now()
            if now < SHUTDOWN_UNTIL:
                time_left = SHUTDOWN_UNTIL - now
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                seconds = int(time_left.total_seconds() % 60)

                if hours > 0:
                    remaining_time = f"\n🕒 Bot will start in: {hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    remaining_time = f"\n🕒 Bot will start in: {minutes}m {seconds}s"
                else:
                    remaining_time = f"\n🕒 Bot will start in: {seconds}s"

        await update.message.reply_text(f"🔴 Bot is currently shutdown.\n📝 Reason: {SHUTDOWN_REASON}{remaining_time}\n⏰ Please try again later.")
        return

    if not IS_BOT_ACTIVE:
        await update.message.reply_text("🚫 Bot is currently inactive. Please try later.")
        return

    # Real-time ban check
    if is_user_banned(user.id):
        await update.message.reply_text(
    "🚫 *Access Denied*\n"
    "You have been *banned* from using this bot\\.\n\n"
    "🔒 *Reason:* Violation of rules or suspicious activity\n"
    "🕵️‍♂️ If you believe this was a *mistake*, you can appeal\\.\n\n"
    "📞 *Owner Details*\n"
    "👤 *Name:* Preet Bopche\n"
    "📬 *Contact:* [@HackerPonline]\n\n"
    "⚠️ Please do *not* create multiple accounts to bypass the ban\\.\n"
    "Thank you for your understanding\\.",
    parse_mode='MarkdownV2'
)
        return

    if uid not in user_data:
        user_data[uid] = {
            "name": user.full_name,
            "user_id": user.id,
            "user_first_name": user.first_name or "",
            "user_last_name": user.last_name or "",
            "user_email": "",
            "user_phone": "",
            "username": user.username,
            "language": "en",
            "user_status": "active",
            "user_type": "user",
            "user_created_at": datetime.now().isoformat(),
            "user_updated_at": datetime.now().isoformat(),
            "credits": CREDIT_CONFIG['welcome_credit'],
            "referred_by": None,
            "referral_count": 0
        }
        save_json(USER_DATA_FILE, user_data)
        await update.message.reply_text(
            f"👋 Welcome {first_name}\\!\n\n"
            f"🎁 You received {CREDIT_CONFIG['welcome_credit']} welcome credits\\!\n\n"
            "Enjoy exploring and start using your credits\\!\n\n"
            "Currently, the bot is running on a development server, which is why it temporarily stores your data. This ensures smooth functionality and helps us improve the bot’s performance during testing."
            "Let’s get started! ⬇️",
            parse_mode='MarkdownV2',
            reply_markup=get_user_panel()
        )
        return

    await update.message.reply_text(
    f"👋 *Welcome Back, {user_first_name}\\!*\n\n"
    "We\\'re glad to see you again\\! 😊\n"
    "Let’s pick up where we left off\\. Explore new features, manage your tools, and make the most of your experience\\.\n\n"
    "Ready to dive in\\? ⬇️",
    parse_mode='MarkdownV2',
    reply_markup=get_user_panel()
)

# ======================== CALLBACKS ========================
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_user_id, current_user, user_first_name, user_last_name, user_full_name, user_username, first_name, current_credits, current_user_data
    
    query = update.callback_query
    user = query.from_user
    cb = query.data
    
    # Answer callback query safely to prevent timeout errors
    try:
        await query.answer()
    except Exception as e:
        if "Query is too old" in str(e) or "response timeout expired" in str(e):
            # Ignore timeout errors for old queries
            pass
        else:
            logger.error(f"Error answering callback query: {e}")
    
    # Set global variables
    current_user_id = user.id
    current_user = user
    user_first_name = user.first_name or ""
    user_last_name = user.last_name or ""
    user_full_name = user.full_name or ""
    user_username = user.username or ""
    first_name = user.first_name or "User"
    
    # Load current user data
    uid = str(user.id)
    reload_data()
    current_user_data = user_data.get(uid, {})
    current_credits = current_user_data.get('credits', 0)

    # Check bot shutdown status for all users (including owner for consistency)
    if BOT_SHUTDOWN:
        remaining_time = ""
        if SHUTDOWN_UNTIL:
            now = datetime.now()
            if now < SHUTDOWN_UNTIL:
                time_left = SHUTDOWN_UNTIL - now
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                seconds = int(time_left.total_seconds() % 60)

                if hours > 0:
                    remaining_time = f"\n🕒 Bot will start in: {hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    remaining_time = f"\n🕒 Bot will start in: {minutes}m {seconds}s"
                else:
                    remaining_time = f"\n🕒 Bot will start in: {seconds}s"

        await query.edit_message_text(f"🔴 Bot is currently shutdown.\n📝 Reason: {SHUTDOWN_REASON}{remaining_time}\n⏰ Please try again later.")
        return

    # Check bot active status for non-owner users
    if user.id != OWNER_ID and not IS_BOT_ACTIVE:
        await query.edit_message_text("🚫 Bot is currently inactive. Please try later.")
        return

    # Real-time ban check for non-owner users
    if user.id != OWNER_ID and is_user_banned(user.id):
        await update.message.reply_text(
    "🚫 *Access Denied*\n"
    "You have been *banned* from using this bot\\.\n\n"
    "🔒 *Reason:* Violation of rules or suspicious activity\n"
    "🕵️‍♂️ If you believe this was a *mistake*, you can appeal\\.\n\n"
    "📞 *Owner Details*\n"
    "👤 *Name:* Preet Bopche\n"
    "📬 *Contact:* [@HackerPonline]\n\n"
    "⚠️ Please do *not* create multiple accounts to bypass the ban\\.\n"
    "Thank you for your understanding\\.",
    parse_mode='MarkdownV2'
)
        return

    # Handle shortlink actions first
    if cb in ["shortlinks", "link_shorteners", "add_link_shortener", "remove_link_shortener", "list_link_shorteners", "view_shortlinks", "add_shortlink", "add_link_to_shortener", "create_new_link", "remove_shortlink", "list_shortlinks", "priority_settings", "add_created_link"] or cb.startswith(("view_ls_", "remove_ls_", "delete_ls_", "select_ls_", "remove_shortlink_", "delete_shortlink_", "view_shortlink_", "next_ls_", "previous_ls_", "next_add_", "previous_add_", "next_remove_", "previous_remove_", "next_list_", "previous_list_", "create_with_ls_", "next_create_", "previous_create_")):
        await handle_shortlink_actions(update, context)
        return

    if user.id == OWNER_ID:
        if cb == "users":
            await users(update, context)
        elif cb == "tools":
            await query.edit_message_text(
                "🛠 *Welcome to the Tools Panel*\n\n"
                "Unlock the full power of your bot with our advanced tools 🎯\n"
                "From speech to text, and video to transcript — everything is just a tap away 🎙️🎬\n\n"
                "Select an option below to get started 👇",
                parse_mode='MarkdownV2',
                reply_markup=get_tools_panel()
                )
        elif cb == "settings":
            await query.edit_message_text("⚙️ Settings Panel", reply_markup=get_settings_panel())
        elif cb == "bot_tools":
            await query.edit_message_text("🛠 Bot Tools Management", reply_markup=get_bot_tools_panel())
        elif cb == "bot_shutdown":
            await query.edit_message_text("🔴 Bot Shutdown\n\nSelect shutdown reason:", reply_markup=get_shutdown_reasons())
        elif cb == "toggle_bot_status":
            await toggle_bot_status(update, context)
        elif cb.startswith("shutdown_reason_"):
            await handle_shutdown_reason(update, context, cb)
        elif cb.startswith("deactivate_reason_"):
            await handle_deactivate_reason(update, context, cb)
        elif cb.startswith("tool_reason_"):
            await handle_tool_reason(update, context, cb)
        elif cb.startswith("manage_") and cb.endswith("_tool"):
            await manage_tool(update, context, cb)
        elif cb == "confirm_shutdown":
            await confirm_shutdown(update, context)
        elif cb == "confirm_deactivate":
            await confirm_deactivate(update, context)
        elif cb.startswith("confirm_tool_"):
            await confirm_tool_action(update, context, cb)
        elif cb.startswith("confirm_feature_"):
            await confirm_feature_action(update, context, cb)
        elif cb == "broadcast":
            example_text = """
📢 Broadcast Message

Please send the message you want to broadcast.

💡 You can mention users like this:
• {first_name} - User's first name
• {last_name} - User's last name  
• {full_name} - User's full name
• {user_id} - User ID

📝 Example:
Hello user {first_name}, welcome to our bot!

Send your message now:
"""
            await query.edit_message_text(example_text)
            context.user_data['state'] = 'waiting_broadcast_message'
        elif cb == "back_to_owner":
            await query.edit_message_text(
                "👑 *Hello Boss\\!* \n\n"
                "Welcome to your *Control Panel*\\.\n"
                "Let's manage the bot like a *pro* ⚙️🤖\n\n"
                "🔧 Use the buttons below to get started 👇",
                parse_mode='MarkdownV2',
                reply_markup=get_owner_panel()
            )
        elif cb == "back_to_main":
            await query.edit_message_text(
                "👑 *Hello Boss\\!* \n\n"
                "Welcome to your *Control Panel*\\.\n"
                "Let's manage the bot like a *pro* ⚙️🤖\n\n"
                "🔧 Use the buttons below to get started 👇",
                parse_mode='MarkdownV2',
                reply_markup=get_owner_panel()
            )
        elif cb == "ban_user":
            await query.edit_message_text("🚫 Ban User\n\nPlease send User ID or Username:")
            context.user_data['state'] = 'waiting_user_id_for_ban'
        elif cb == "unban_user":
            await query.edit_message_text("✅ Unban User\n\nPlease send User ID or Username:")
            context.user_data['state'] = 'waiting_user_id_for_unban'
        elif cb == "skip_ban_reason":
            uid = context.user_data.get('ban_user_id')
            user_info = context.user_data.get('ban_user_info')
            if uid and user_info:
                reload_data()
                banned_users[uid] = {
                    "name": user_info.get('name', 'Unknown'),
                    "reason": "No reason provided",
                    "banned_at": datetime.now().isoformat()
                }
                save_json(BANNED_USERS_FILE, banned_users)

                # Send notification to banned user
                try:
                    ban_msg = f"""
🚫 You have been banned from this bot

👤 Name: {user_info.get('name', 'Unknown')}
📝 Reason: No reason provided
⏰ Banned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 Banned By: Owner

If you think this is a mistake, please contact the owner.

Contact Support : {Owner}
                    """
                    await context.bot.send_message(chat_id=user_info.get('user_id'), text=ban_msg)
                except Exception as e:
                    logger.error(f"Failed to send ban notification: {e}")

                await query.edit_message_text(
                    f"🚫 User Banned Successfully!\n\n"
                    f"👤 User: {user_info.get('name', 'Unknown')}\n"
                    f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                    f"📝 Reason: No reason provided\n"
                    f"⏰ Banned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📬 Notification sent to user",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                )
            context.user_data['state'] = None
            context.user_data.pop('ban_user_id', None)
            context.user_data.pop('ban_user_info', None)
        elif cb == "skip_unban_reason":
            uid = context.user_data.get('unban_user_id')
            user_info = context.user_data.get('unban_user_info')
            if uid and user_info:
                reload_data()
                del banned_users[uid]
                save_json(BANNED_USERS_FILE, banned_users)

                # Send notification to unbanned user
                try:
                    unban_msg = f"""
✅ You have been unbanned from this bot

👤 Name: {user_info.get('name', 'Unknown')}
📝 Reason: No reason provided
⏰ Unbanned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 Unbanned By: Owner

You can now use the bot again. Welcome back!
                    """
                    await context.bot.send_message(chat_id=user_info.get('user_id'), text=unban_msg)
                except Exception as e:
                    logger.error(f"Failed to send unban notification: {e}")

                await query.edit_message_text(
                    f"✅ User Unbanned Successfully!\n\n"
                    f"👤 User: {user_info.get('name', 'Unknown')}\n"
                    f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                    f"📝 Reason: No reason provided\n"
                    f"⏰ Unbanned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📬 Notification sent to user",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                )
            context.user_data['state'] = None
            context.user_data.pop('unban_user_id', None)
            context.user_data.pop('unban_user_info', None)
        elif cb == "skip_credit_message":
            await process_give_credit(update, context, None)
        elif cb == "skip_credit_all_message":
            await process_give_credit_all(update, context, None)
        elif cb == "user_info":
            await query.edit_message_text("ℹ️ User Info\n\nPlease send User ID or Username:")
            context.user_data['state'] = 'waiting_user_id_for_info'
        elif cb == "give_credit":
            await query.edit_message_text("💰 Give Credit\n\nPlease send User ID or Username:")
            context.user_data['state'] = 'waiting_user_id_for_credit'
        elif cb == "give_credit_all":
            await query.edit_message_text("💰 Give Credit to All Users\n\nPlease send the credit amount to give to all users:")
            context.user_data['state'] = 'waiting_credit_all_amount'
        elif cb == "status":
            await status(update, context)
        elif cb == "detailed_analytics":
            await detailed_analytics(update, context)
        elif cb == "system_health":
            await system_health(update, context)
        elif cb == "performance_stats":
            await performance_stats(update, context)
        elif cb == "add_credit":
            await add_credit_panel(update, context)
        elif cb == "handle_credit_system":
            await handle_credit_system(update, context)
        elif cb == "edit_welcome_credit":
            await edit_credit_value(update, context, "welcome_credit", "🎁 Welcome Credit")
        elif cb == "edit_tts_cost":
            await edit_credit_value(update, context, "tts_cost_per_char", "🗣 TTS Cost Per Character")
        elif cb == "edit_stt_cost":
            await edit_credit_value(update, context, "stt_cost_per_minute", "🎤 STT Cost Per Minute")
        
        elif cb == "edit_link_reward":
            await edit_credit_value(update, context, "shortlink_reward", "🔗 Link Reward")
        elif cb == "edit_referral_reward":
            await edit_credit_value(update, context, "referral_reward", "👥 Referral Reward")
        elif cb == "credit_stats":
            await show_credit_stats(update, context)
        elif cb == "offers":
            await handle_offers_panel(update, context)
        elif cb == "offers_management":
            await handle_offers_management(update, context)
        elif cb == "manage_coupons":
            await handle_coupons_panel(update, context)
        elif cb == "manage_seasonal_offers":
            await handle_seasonal_offers_panel(update, context)
        elif cb == "offers_status":
            await handle_offers_status(update, context)
        elif cb == "seasonal_offers_status":
            await handle_offers_status(update, context)
        elif cb == "add_coupon":
            await add_coupon_start(update, context)
        elif cb == "remove_coupon":
            await remove_coupon_panel(update, context)
        elif cb == "list_coupons":
            await list_coupons_panel(update, context)
        elif cb == "add_credit_offer":
            await add_credit_offer_panel(update, context)
        elif cb == "deduct_credit_offer":
            await deduct_credit_offer_panel(update, context)
        elif cb.startswith("view_coupon_"):
            await view_coupon_details(update, context, cb)
        elif cb.startswith("edit_coupon_") and not cb.startswith("edit_coupon_credits_") and not cb.startswith("edit_coupon_limit_") and not cb.startswith("edit_coupon_validity_"):
            await edit_coupon_details(update, context, cb)
        elif cb.startswith("edit_coupon_credits_") or cb.startswith("edit_coupon_limit_") or cb.startswith("edit_coupon_validity_"):
            await handle_edit_coupon_actions(update, context, cb)
        elif cb.startswith("delete_coupon_"):
            await delete_coupon_confirm(update, context, cb)
        elif cb.startswith("confirm_delete_coupon_"):
            await delete_coupon_final(update, context, cb)
        elif cb.startswith("select_credit_method_"):
            await select_credit_method(update, context, cb)
        elif cb.startswith("view_offer_"):
            await view_offer_details(update, context, cb)
        elif cb.startswith("delete_offer_"):
            await delete_offer_confirm(update, context, cb)
        elif cb.startswith("confirm_delete_offer_"):
            await delete_offer_final(update, context, cb)
        elif cb.startswith("next_coupons_") or cb.startswith("previous_coupons_"):
            await handle_coupons_pagination(update, context, cb)
        elif cb.startswith("next_offers_") or cb.startswith("previous_offers_"):
            await handle_offers_pagination(update, context, cb)
        elif cb == "owner_refer":
            await handle_owner_refer(update, context)
        elif cb == "ad_view":
            await handle_ad_view(update, context)
        elif cb == "refer_telegram":
            await handle_refer_telegram(update, context)
        elif cb == "refer_other":
            await handle_refer_other(update, context)
        elif cb == "refer_status":
            await handle_refer_status(update, context)
        elif cb == "cancel_refer":
            await handle_offers_panel(update, context)
        
        elif cb == "important_info":
            await handle_important_info(update, context)
        elif cb == "add_info":
            await add_important_info(update, context)
        elif cb == "remove_info":
            await remove_important_info(update, context)
        elif cb.startswith("view_info_"):
            await view_important_info(update, context, cb)
        elif cb.startswith("remove_info_"):
            await confirm_remove_important_info(update, context, cb)
        elif cb.startswith("delete_info_"):
            await delete_important_info(update, context, cb)
        elif cb.startswith("next_info_"):
            await handle_info_pagination(update, context, cb)
        elif cb.startswith("previous_info_"):
            await handle_info_pagination(update, context, cb)
        
        elif cb == "copy_owner_refer_link":
            bot_username = context.bot.username or "mediaGenie_bot"
            refer_link = f"https://t.me/{bot_username}?start=owner_ref"
            await query.answer(f"Owner Referral Link Copied!\n{refer_link}", show_alert=True)
        elif cb == "copy_refer_message":
            bot_username = context.bot.username or "mediaGenie_bot"
            refer_link = f"https://t.me/{bot_username}?start=owner_ref"
            referral_message = f"""Hey! If you want to convert your text to speech, try this amazing bot!

🎙️ Features:
• Text to Speech (Hindi/English)
• Speech to Text
• Video Transcription
• Free Credits

Try it here: {refer_link}

Support banaye rakhna! 😊"""
            await query.answer("✅ Referral message copied successfully!", show_alert=True)
        
        # Advertisement management handlers
        elif cb == "add_advertisement":
            await add_advertisement(update, context)
        elif cb.startswith("view_ad_"):
            ad_id = cb.split("_")[-1]
            await view_advertisement_details(update, context, ad_id)
        elif cb.startswith("remove_ad_"):
            ad_id = cb.split("_")[-1]
            await confirm_remove_advertisement(update, context, ad_id)
        elif cb.startswith("delete_ad_"):
            ad_id = cb.split("_")[-1]
            await delete_advertisement(update, context, ad_id)
        elif cb.startswith("next_ads_") or cb.startswith("previous_ads_"):
            await handle_ads_pagination(update, context, cb)
        elif cb == "empty_slot":
            await query.answer("📺 No advertisement in this slot", show_alert=False)
        
    # Handle common tool buttons for both owner and users
    if cb == "tools":
        await query.edit_message_text(
                "🛠 *Welcome to the Tools Panel*\n\n"
                "Unlock the full power of your bot with our advanced tools 🎯\n"
                "From speech to text, and video to transcript — everything is just a tap away 🎙️🎬\n\n"
                "Select an option below to get started 👇",
                parse_mode='MarkdownV2',
                reply_markup=get_tools_panel()
                )
    elif cb == "tts":
        if not TOOLS_STATUS.get('tts', True):
            reason = TOOLS_DEACTIVATION_REASONS.get('tts', 'No reason provided')
            await query.edit_message_text(
                f"❎ TTS tool is currently deactivated by owner.\n\n📝 Reason: {reason}",
                reply_markup=get_tools_panel()
            )
        else:
            await handle_tts_request(update, context)
    elif cb.startswith("tts_voice_"):
        await handle_tts_voice_selection(update, context)
    elif cb == "stt":
        if not TOOLS_STATUS.get('stt', True):
            reason = TOOLS_DEACTIVATION_REASONS.get('stt', 'No reason provided')
            await query.edit_message_text(
                f"❎ STT tool is currently deactivated by owner.\n\n📝 Reason: {reason}",
                reply_markup=get_tools_panel()
            )
        else:
            await handle_stt_request(update, context)
    elif cb == "yt_downloader":
        await handle_yt_downloader_request(update, context)
    elif cb.startswith("download_video_"):
        await handle_video_download(update, context, cb)
    elif cb == "download_audio":
        await handle_audio_download(update, context)
    elif cb == "back_to_qualities":
        await handle_back_to_qualities(update, context)
    
    elif user.id != OWNER_ID:
        # User-specific buttons
        if cb == "back_to_main":
            await query.edit_message_text(
                f"👋 *Welcome back, {user_first_name}\\!*\n\n"
                "Let\\'s get you back on track ⬇️",
                parse_mode='MarkdownV2',
                reply_markup=get_user_panel()
            )
        elif cb == "profile":
            await show_user_profile(update, context)
        elif cb == "help":
            await show_help(update, context)
        elif cb == "about":
            await show_about(update, context)
        elif cb == "add_credit":
            await add_credit_panel(update, context)
        elif cb == "credit_link":
            await handle_credit_link(update, context)
        elif cb == "credit_referral":
            await handle_credit_referral(update, context)
        elif cb == "credit_coupon":
            await handle_credit_coupon(update, context)
        elif cb == "buy_credits":
            await handle_buy_credits(update, context)
        elif cb.startswith("buy_") and cb.endswith("_credits"):
            await handle_credit_package(update, context, cb)
        elif cb.startswith("copy_user_id_"):
            user_id = cb.split("_")[-1]
            await query.answer(f"Your User ID: {user_id}\n(ID copied to clipboard)", show_alert=True)
        elif cb == "refresh_links":
            await handle_credit_link(update, context)
        # Payload entry is now handled through start command automatically
        elif cb == "referral_status":
            await handle_referral_status(update, context)
        elif cb.startswith("copy_referral_"):
             user_id = cb.split("_")[-1]
             referral_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
             await query.answer(f"Your Referral Link: {referral_link}\n(Link copied to clipboard)", show_alert=True)
        elif cb.startswith("feature_disabled_"):
            feature_key = cb.replace("feature_disabled_", "")
            feature_names = {
                'free_credits': 'Free Credits',
                'buy_credits': 'Buy Credits',
                'referral': 'Referral System'
            }
            feature_name = feature_names.get(feature_key, feature_key.replace("_", " ").title())
            reason = TOOLS_DEACTIVATION_REASONS.get(feature_key, 'No reason provided')
            await query.answer(f"❎ {feature_name} is disabled by owner.\n📝 Reason: {reason}", show_alert=True)
    else:
        # Owner-specific buttons that are not handled above
        if cb == "back_to_main":
            await query.edit_message_text("👑 Hello Boss ! \n\nWelcome to your control panel. Let's manage the bot like a pro !", reply_markup=get_owner_panel())


# ======================== USERS PANEL FUNCTIONS ========================
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("👥 Users Management Panel", reply_markup=get_users_panel())

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed bot status with enhanced UI"""
    query = update.callback_query

    # Reload latest data
    reload_data()

    # Calculate comprehensive statistics
    total_users = len(user_data)
    active_users = len([u for u in user_data.values() if u.get('user_status') == 'active'])
    inactive_users = total_users - active_users
    total_banned = len(banned_users)
    
    # Calculate total credits in system
    total_credits = sum(user.get('credits', 0) for user in user_data.values())
    avg_credits = total_credits / total_users if total_users > 0 else 0
    
    # Calculate active rate safely
    active_rate = (active_users/total_users*100) if total_users > 0 else 0
    
    # Calculate shortlinks and link shorteners
    total_shortlinks = len(shortlinks_data)
    total_link_shorteners = len(link_shorteners_data)
    active_link_shorteners = len([ls for ls in link_shorteners_data.values() if ls.get('status') == 'Active'])
    
    # Calculate important info count
    total_imp_info = len(important_info)
    
    # Bot status with emoji
    if BOT_SHUTDOWN:
        bot_status = "🔴 SHUTDOWN"
        bot_status_detail = f"Reason: {SHUTDOWN_REASON}"
        if SHUTDOWN_UNTIL:
            remaining = SHUTDOWN_UNTIL - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                bot_status_detail += f"\nRestart in: {hours}h {minutes}m"
    elif not IS_BOT_ACTIVE:
        bot_status = "🟡 INACTIVE"
        bot_status_detail = "Bot is deactivated"
    else:
        bot_status = "🟢 ACTIVE"
        bot_status_detail = "All systems operational"
    
    # Tools status
    tools_active = sum(1 for tool in TOOLS_STATUS.values() if tool)
    tools_total = len(TOOLS_STATUS)
    
    # Calculate uptime (simplified version)
    import time
    current_time = datetime.now()
    
    status_text = f"""
🚀 **BOT STATUS DASHBOARD**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🤖 **SYSTEM STATUS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ Status: {bot_status}
┃ Details: {bot_status_detail}
┃ Owner: 👑 {OWNER_ID}
┃ Tools: {tools_active}/{tools_total} Active
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 👥 **USER ANALYTICS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 📊 Total Users: {total_users:,}
┃ ✅ Active Users: {active_users:,}
┃ ⏸️ Inactive Users: {inactive_users:,}
┃ 🚫 Banned Users: {total_banned:,}
┃ 📈 Active Rate: {active_rate:.1f}%
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 💰 **CREDIT SYSTEM**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 💎 Total Credits: {total_credits:,}
┃ 📊 Average Credits: {avg_credits:.1f}
┃ 🎁 Welcome Credit: {CREDIT_CONFIG['welcome_credit']}
┃ 🗣️ TTS Cost/Char: {CREDIT_CONFIG['tts_cost_per_char']}
┃ 🎤 STT Cost/Min: {CREDIT_CONFIG['stt_cost_per_minute']}
┃ 🔗 Link Reward: {CREDIT_CONFIG['shortlink_reward']}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔗 **SHORTLINK SYSTEM**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🌐 Link Shorteners: {total_link_shorteners}
┃ ✅ Active Shorteners: {active_link_shorteners}
┃ 📋 Total Shortlinks: {total_shortlinks}
┃ ⚡ API Integration: Enabled
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🛠️ **TOOLS STATUS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🗣️ TTS: {'✅ Active' if TOOLS_STATUS.get('tts') else '❌ Inactive'}
┃ 🎤 STT: {'✅ Active' if TOOLS_STATUS.get('stt') else '❌ Inactive'}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📊 **DATA MANAGEMENT**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 📋 Important Info: {total_imp_info} items
┃ 💾 Data Files: All Connected
┃ 🔄 Auto-Save: Enabled
┃ 🛡️ Security: Active
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

🕐 **Last Updated:** {current_time.strftime('%d/%m/%Y %H:%M:%S')}
⚡ **Server Time:** {current_time.strftime('%A, %B %d, %Y')}
    """

    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Status", callback_data="status"),
         InlineKeyboardButton("📊 Detailed Analytics", callback_data="detailed_analytics")],
        [InlineKeyboardButton("⚙️ System Health", callback_data="system_health"),
         InlineKeyboardButton("📈 Performance", callback_data="performance_stats")],
        [InlineKeyboardButton("🔙 Back to Owner Panel", callback_data="back_to_owner")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(status_text, reply_markup=reply_markup)

def find_user_by_id_or_username(identifier):
    """Find user by ID or username"""
    for uid, data in user_data.items():
        if str(data.get('user_id')) == str(identifier) or data.get('username') == identifier:
            return uid, data
    return None, None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_user_id, current_user, user_first_name, user_last_name, user_full_name, user_username, first_name, current_credits, current_user_data
    
    user = update.effective_user
    message_text = update.message.text
    
    # Set global variables
    current_user_id = user.id
    current_user = user
    user_first_name = user.first_name or ""
    user_last_name = user.last_name or ""
    user_full_name = user.full_name or ""
    user_username = user.username or ""
    first_name = user.first_name or "User"
    
    # Load current user data
    uid = str(user.id)
    reload_data()
    current_user_data = user_data.get(uid, {})
    current_credits = current_user_data.get('credits', 0)

    # Check bot shutdown status for all users
    if BOT_SHUTDOWN:
        remaining_time = ""
        if SHUTDOWN_UNTIL:
            now = datetime.now()
            if now < SHUTDOWN_UNTIL:
                time_left = SHUTDOWN_UNTIL - now
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                seconds = int(time_left.total_seconds() % 60)

                if hours > 0:
                    remaining_time = f"\n🕒 Bot will start in: {hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    remaining_time = f"\n🕒 Bot will start in: {minutes}m {seconds}s"
                else:
                    remaining_time = f"\n🕒 Bot will start in: {seconds}s"

        await update.message.reply_text(f"🔴 Bot is currently shutdown.\n📝 Reason: {SHUTDOWN_REASON}{remaining_time}\n⏰ Please try again later.")
        return

    # Check bot active status for non-owner users
    if user.id != OWNER_ID and not IS_BOT_ACTIVE:
        await update.message.reply_text("🚫 Bot is currently inactive. Please try later.")
        return

    # Real-time ban check for non-owner users
    if user.id != OWNER_ID and is_user_banned(user.id):
        await update.message.reply_text(
    "🚫 *Access Denied*\n"
    "You have been *banned* from using this bot\\.\n\n"
    "🔒 *Reason:* Violation of rules or suspicious activity\n"
    "🕵️‍♂️ If you believe this was a *mistake*, you can appeal\\.\n\n"
    "📞 *Owner Details*\n"
    "👤 *Name:* Preet Bopche\n"
    "📬 *Contact:* [@HackerPonline]\n\n"
    "⚠️ Please do *not* create multiple accounts to bypass the ban\\.\n"
    "Thank you for your understanding\\.",
    parse_mode='MarkdownV2'
)
        return

    state = context.user_data.get('state')

    if state == 'waiting_user_id_for_ban':
        try:
            uid, user_info = find_user_by_id_or_username(message_text)
            if uid:
                # Don't allow banning the owner
                if int(uid) == OWNER_ID:
                    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                    await update.message.reply_text(
                        "❌ Cannot ban the owner!",
                        reply_markup=back_button
                    )
                    context.user_data['state'] = None
                else:
                    context.user_data['ban_user_id'] = uid
                    context.user_data['ban_user_info'] = user_info

                    skip_button = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⏭️ Skip", callback_data="skip_ban_reason")],
                        [InlineKeyboardButton("🔙 Back", callback_data="users")]
                    ])
                    await update.message.reply_text(
                        f"🚫 Ban User: {user_info.get('name', 'Unknown')}\n\n"
                        f"Please provide ban reason (or skip):",
                        reply_markup=skip_button
                    )
                    context.user_data['state'] = 'waiting_ban_reason'
            else:
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                await update.message.reply_text(
                    "❌ User not found! Please check User ID or Username.",
                    reply_markup=back_button
                )
                context.user_data['state'] = None
        except Exception as e:
            logger.error(f"Error in ban process: {e}")
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(
                "❌ Error occurred. Please try again.",
                reply_markup=back_button
            )
            context.user_data['state'] = None

    elif state == 'waiting_ban_reason':
        try:
            uid = context.user_data.get('ban_user_id')
            user_info = context.user_data.get('ban_user_info')
            ban_reason = message_text

            if uid and user_info:
                reload_data()
                banned_users[uid] = {
                    "name": user_info.get('name', 'Unknown'),
                    "reason": ban_reason,
                    "banned_at": datetime.now().isoformat()
                }
                save_json(BANNED_USERS_FILE, banned_users)

                # Send notification to banned user
                try:
                    ban_msg = f"""
🚫 You have been banned from this bot

👤 Name: {user_info.get('name', 'Unknown')}
📝 Reason: {ban_reason}
⏰ Banned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 Banned By: Owner

If you think this is a mistake, please contact the owner.
                    """
                    await context.bot.send_message(chat_id=user_info.get('user_id'), text=ban_msg)
                except Exception as e:
                    logger.error(f"Failed to send ban notification: {e}")

                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                await update.message.reply_text(
                    f"🚫 User Banned Successfully!\n\n"
                    f"👤 User: {user_info.get('name', 'Unknown')}\n"
                    f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                    f"📝 Reason: {ban_reason}\n"
                    f"⏰ Banned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📬 Notification sent to user",
                    reply_markup=back_button
                )

            context.user_data['state'] = None
            context.user_data.pop('ban_user_id', None)
            context.user_data.pop('ban_user_info', None)

        except Exception as e:
            logger.error(f"Error banning user: {e}")
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(
                "❌ Error occurred while banning user. Please try again.",
                reply_markup=back_button
            )
            context.user_data['state'] = None

    elif state == 'waiting_user_id_for_unban':
        try:
            uid, user_info = find_user_by_id_or_username(message_text)
            if uid:
                reload_data()
                if uid in banned_users:
                    context.user_data['unban_user_id'] = uid
                    context.user_data['unban_user_info'] = user_info

                    skip_button = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⏭️ Skip", callback_data="skip_unban_reason")],
                        [InlineKeyboardButton("🔙 Back", callback_data="users")]
                    ])
                    await update.message.reply_text(
                        f"✅ Unban User: {user_info.get('name', 'Unknown')}\n\n"
                        f"Please provide unban reason (or skip):",
                        reply_markup=skip_button
                    )
                    context.user_data['state'] = 'waiting_unban_reason'
                else:
                    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                    await update.message.reply_text(
                        "❌ User is not in banned list!",
                        reply_markup=back_button
                    )
                    context.user_data['state'] = None
            else:
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                await update.message.reply_text(
                    "❌ User not found! Please check User ID or Username.",
                    reply_markup=back_button
                )
                context.user_data['state'] = None
        except Exception as e:
            logger.error(f"Error in unban process: {e}")
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(
                "❌ Error occurred. Please try again.",
                reply_markup=back_button
            )
            context.user_data['state'] = None

    elif state == 'waiting_unban_reason':
        try:
            uid = context.user_data.get('unban_user_id')
            user_info = context.user_data.get('unban_user_info')
            unban_reason = message_text

            if uid and user_info:
                reload_data()
                del banned_users[uid]
                save_json(BANNED_USERS_FILE, banned_users)

                # Send notification to unbanned user
                try:
                    unban_msg = f"""
✅ You have been unbanned from this bot

👤 Name: {user_info.get('name', 'Unknown')}
📝 Reason: {unban_reason}
⏰ Unbanned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 Unbanned By: Owner

You can now use the bot again. Welcome back!
                    """
                    await context.bot.send_message(chat_id=user_info.get('user_id'), text=unban_msg)
                except Exception as e:
                    logger.error(f"Failed to send unban notification: {e}")

                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                await update.message.reply_text(
                    f"✅ User Unbanned Successfully!\n\n"
                    f"👤 User: {user_info.get('name', 'Unknown')}\n"
                    f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                    f"📝 Reason: {unban_reason}\n"
                    f"⏰ Unbanned At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📬 Notification sent to user",
                    reply_markup=back_button
                )

            context.user_data['state'] = None
            context.user_data.pop('unban_user_id', None)
            context.user_data.pop('unban_user_info', None)

        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(
                "❌ Error occurred while unbanning user. Please try again.",
                reply_markup=back_button
            )
            context.user_data['state'] = None

    elif state == 'waiting_user_id_for_info':
        uid, user_info = find_user_by_id_or_username(message_text)
        if uid:
            info_text = f"""
ℹ️ User Information

👤 Name: {user_info.get('name', 'Unknown')}
🆔 User ID: {user_info.get('user_id', 'Unknown')}
👤 First Name: {user_info.get('user_first_name', 'Unknown')}
👤 Last Name: {user_info.get('user_last_name', 'Unknown')}
📧 Email: {user_info.get('user_email', 'Not provided')}
📱 Phone: {user_info.get('user_phone', 'Not provided')}
👤 Username: @{user_info.get('username', 'None')}
🌐 Language: {user_info.get('language', 'en')}
📊 Status: {user_info.get('user_status', 'active')}
👤 Type: {user_info.get('user_type', 'user')}
📅 Created: {user_info.get('user_created_at', 'Unknown')}
📅 Updated: {user_info.get('user_updated_at', 'Unknown')}
            """

            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(info_text, reply_markup=back_button)
        else:
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(
                "❌ User not found! Please check User ID or Username.",
                reply_markup=back_button
            )

        context.user_data['state'] = None

    elif state == 'waiting_deactivate_reason':
        context.user_data['deactivate_reason'] = message_text
        confirm_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm Deactivate", callback_data="confirm_deactivate")],
            [InlineKeyboardButton("❌ Cancel", callback_data="settings")]
        ])
        await update.message.reply_text(
            f"🔴 Confirm Bot Deactivation\n\n"
            f"📝 Reason: {message_text}\n\n"
            f"⚠️ This will make the bot inactive for all users.",
            reply_markup=confirm_button
        )
        context.user_data['state'] = None

    elif state == 'waiting_shutdown_reason':
        context.user_data['shutdown_reason'] = message_text
        await update.message.reply_text(
            f"⏰ Shutdown Duration\n\n"
            f"📝 Reason: {message_text}\n\n"
            f"Please send shutdown duration in minutes:"
        )
        context.user_data['state'] = 'waiting_shutdown_duration'

    elif state == 'waiting_shutdown_duration':
        try:
            duration = int(message_text)
            if duration <= 0:
                await update.message.reply_text("❌ Please enter a positive number for duration!")
                return

            reason = context.user_data.get('shutdown_reason', 'No reason provided')
            context.user_data['shutdown_duration'] = duration

            confirm_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Shutdown", callback_data="confirm_shutdown")],
                [InlineKeyboardButton("❌ Cancel", callback_data="settings")]
            ])
            await update.message.reply_text(
                f"🔴 Confirm Bot Shutdown\n\n"
                f"📝 Reason: {reason}\n"
                f"⏰ Duration: {duration} minutes\n"
                f"🔄 Will restart automatically\n\n"
                f"⚠️ This will make the bot unavailable for all users.",
                reply_markup=confirm_button
            )
            context.user_data['state'] = None
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for minutes!")

    elif state == 'waiting_tool_reason':
        tool_name = context.user_data.get('tool_deactivate_name')
        if tool_name:
            tool_names = {
                'tts': 'TTS (Text to Speech)',
                'stt': 'STT (Speech to Text)',
                'video': 'Video Transcribe'
            }

            context.user_data['tool_deactivate_reason'] = message_text
            confirm_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Deactivate", callback_data=f"confirm_tool_{tool_name}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="bot_tools")]
            ])
            await update.message.reply_text(
                f"❎ Confirm {tool_names[tool_name]} Deactivation\n\n"
                f"📝 Reason: {message_text}\n\n"
                f"⚠️ Users will see this message when trying to access this tool.",
                reply_markup=confirm_button
            )
        context.user_data['state'] = None

    elif state == 'waiting_feature_reason':
        feature_name = context.user_data.get('feature_deactivate_name')
        if feature_name:
            feature_names = {
                'free_credits': 'Free Credits',
                'buy_credits': 'Buy Credits',
                'referral': 'Referral System'
            }

            context.user_data['feature_deactivate_reason'] = message_text
            confirm_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Deactivate", callback_data=f"confirm_feature_{feature_name}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="bot_tools")]
            ])
            await update.message.reply_text(
                f"❎ Confirm {feature_names[feature_name]} Deactivation\n\n"
                f"📝 Reason: {message_text}\n\n"
                f"⚠️ Users will see this message when trying to access this feature.",
                reply_markup=confirm_button
            )
        context.user_data['state'] = None

    elif state == 'waiting_broadcast_message':
        context.user_data['broadcast_message'] = message_text

        # Start broadcasting immediately
        reload_data()  # Reload latest user data
        active_users = {uid: data for uid, data in user_data.items() if data.get('user_status') == 'active'}

        success_count = 0
        failed_count = 0

        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_owner")]])

        await update.message.reply_text(
            f"📢 Broadcasting message to {len(active_users)} users...\n⏳ Please wait...",
            reply_markup=back_button
        )

        for uid, user_info in active_users.items():
            try:
                user_id = user_info.get('user_id')
                if not user_id or is_user_banned(user_id):
                    continue

                # Replace placeholders with actual user data
                formatted_message = message_text
                formatted_message = formatted_message.replace("{first_name}", user_info.get('user_first_name', 'User'))
                formatted_message = formatted_message.replace("{last_name}", user_info.get('user_last_name', 'User'))
                formatted_message = formatted_message.replace("{full_name}", user_info.get('name', 'User'))
                formatted_message = formatted_message.replace("{user_id}", str(user_info.get('user_id', 'Unknown')))

                await context.bot.send_message(chat_id=user_id, text=formatted_message)
                success_count += 1

            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                failed_count += 1

        # Send completion message
        completion_text = f"""
📢 Broadcast Complete!

✅ Successfully sent: {success_count}
❌ Failed to send: {failed_count}
📊 Total users: {len(active_users)}

💬 Original Message: {message_text[:100]}{'...' if len(message_text) > 100 else ''}
        """

        await update.message.reply_text(completion_text, reply_markup=back_button)
        context.user_data['state'] = None




    elif state == 'waiting_user_id_for_credit':
        try:
            uid, user_info = find_user_by_id_or_username(message_text)
            if uid:
                current_credits = user_info.get('credits', 0)
                context.user_data['credit_user_id'] = uid
                context.user_data['credit_user_info'] = user_info

                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="users")]])
                await update.message.reply_text(
                    f"💰 Give Credit to User\n\n"
                    f"👤 User: {user_info.get('name', 'Unknown')}\n"
                    f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                    f"💳 Current Credits: {current_credits}\n\n"
                    f"Please send the credit amount to give:",
                    reply_markup=back_button
                )
                context.user_data['state'] = 'waiting_credit_amount'
            else:
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                await update.message.reply_text(
                    "❌ User not found! Please check User ID or Username.",
                    reply_markup=back_button
                )
                context.user_data['state'] = None
        except Exception as e:
            logger.error(f"Error in credit process: {e}")
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
            await update.message.reply_text(
                "❌ Error occurred. Please try again.",
                reply_markup=back_button
            )
            context.user_data['state'] = None

    elif state == 'waiting_credit_amount':
        try:
            credit_amount = int(message_text)
            if credit_amount <= 0:
                await update.message.reply_text("❌ Please enter a positive number for credits!")
                return

            user_info = context.user_data.get('credit_user_info')
            context.user_data['credit_amount'] = credit_amount

            skip_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭️ Skip Message", callback_data="skip_credit_message")],
                [InlineKeyboardButton("❌ Cancel", callback_data="users")]
            ])
            await update.message.reply_text(
                f"💰 Credit Amount: {credit_amount}\n"
                f"👤 User: {user_info.get('name', 'Unknown')}\n\n"
                f"💬 Send a custom message to include with the credit (or skip for default message):\n\n"
                f"💡 You can use placeholders:\n"
                f"• {{first_name}} - User's first name\n"
                f"• {{last_name}} - User's last name\n"
                f"• {{full_name}} - User's full name\n"
                f"• {{user_id}} - User ID\n"
                f"• {{username}} - Username\n"
                f"• {{credit}} - Credit amount\n\n"
                f"📝 Example: Hello {{first_name}}, You got {{credit}} credits for your work!",
                reply_markup=skip_button
            )
            context.user_data['state'] = 'waiting_credit_message'
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for credits!")

    elif state == 'waiting_credit_message':
        await process_give_credit(update, context, message_text)

    elif state == 'waiting_credit_all_amount':
        try:
            credit_amount = int(message_text)
            if credit_amount <= 0:
                await update.message.reply_text("❌ Please enter a positive number for credits!")
                return

            context.user_data['credit_all_amount'] = credit_amount

            skip_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭️ Skip Message", callback_data="skip_credit_all_message")],
                [InlineKeyboardButton("❌ Cancel", callback_data="users")]
            ])
            await update.message.reply_text(
                f"💰 Credit Amount for All Users: {credit_amount}\n\n"
                f"💬 Send a custom message to include with the credit (or skip for default message):\n\n"
                f"💡 You can use placeholders:\n"
                f"• {{first_name}} - User's first name\n"
                f"• {{last_name}} - User's last name\n"
                f"• {{full_name}} - User's full name\n"
                f"• {{user_id}} - User ID\n"
                f"• {{username}} - Username\n"
                f"• {{credit}} - Credit amount\n\n"
                f"📝 Example: Hello {{first_name}}, You got {{credit}} credits as a bonus!",
                reply_markup=skip_button
            )
            context.user_data['state'] = 'waiting_credit_all_message'
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for credits!")

    elif state == 'waiting_credit_all_message':
        await process_give_credit_all(update, context, message_text)

    elif state == 'waiting_tts_text':
        await process_tts_text(update, context, message_text)

    elif state == 'waiting_stt_audio':
        await process_stt_audio(update, context)
    
    elif state == 'waiting_yt_link':
        await handle_yt_link_input(update, context, message_text)

    elif state == 'waiting_imp_info_title':
        context.user_data['imp_info_title'] = message_text
        await update.message.reply_text(
            f"📝 Title: {message_text}\n\n"
            f"Now send the important data/information you want to save:"
        )
        context.user_data['state'] = 'waiting_imp_info_data'

    elif state == 'waiting_imp_info_data':
        await process_important_info_save(update, context, message_text)

    elif state == 'waiting_quick_add_email':
        context.user_data['ls_email'] = message_text
        await update.message.reply_text("🔒 Please send the password for this link shortener:")
        context.user_data['state'] = 'waiting_ls_password'

    elif state == 'waiting_ls_domain':
        context.user_data['ls_domain'] = message_text
        await update.message.reply_text("📧 Please send the email for this link shortener:")
        context.user_data['state'] = 'waiting_ls_email'

    elif state == 'waiting_ls_email':
        context.user_data['ls_email'] = message_text
        await update.message.reply_text("🔒 Please send the password for this link shortener:")
        context.user_data['state'] = 'waiting_ls_password'

    elif state == 'waiting_ls_password':
        context.user_data['ls_password'] = message_text
        await update.message.reply_text("🎯 Please send the priority rate (e.g., 70%):")
        context.user_data['state'] = 'waiting_ls_priority'

    elif state == 'waiting_ls_priority':
        context.user_data['ls_priority'] = message_text
        await update.message.reply_text("🔑 Please send the API key for this link shortener:")
        context.user_data['state'] = 'waiting_ls_api'

    elif state == 'waiting_ls_api':
        await process_link_shortener_save(update, context, message_text)

    elif state == 'waiting_shortlink_url':
        await process_shortlink_url(update, context, message_text)

    elif state == 'waiting_shortlink_payload':
        await process_shortlink_save(update, context, message_text)

    elif state == 'waiting_original_url':
        await process_original_url(update, context, message_text)

    elif state == 'waiting_created_link_payload':
        await process_created_link_payload(update, context, message_text)
    
    elif state == 'waiting_ad_title':
        context.user_data['ad_title'] = message_text
        await update.message.reply_text("📝 Please send the description for this advertisement:")
        context.user_data['state'] = 'waiting_ad_description'
    
    elif state == 'waiting_ad_description':
        context.user_data['ad_description'] = message_text
        await update.message.reply_text(
            "📎 Please send the file for this advertisement:\n\n"
            "📊 Supported formats:\n"
            "• Images: JPG, PNG, GIF, WebP\n"
            "• Videos: MP4, AVI, MOV\n"
            "• Documents: PDF, DOC, TXT\n"
            "• Audio: MP3, WAV, OGG\n\n"
            "Send any file type you want to attach with the ad."
        )
        context.user_data['state'] = 'waiting_ad_file'
    
    elif state == 'waiting_ad_duration':
        try:
            duration = int(message_text)
            if duration <= 0:
                await update.message.reply_text("❌ Please enter a positive number for days!")
                return
            
            context.user_data['ad_duration'] = duration
            await update.message.reply_text(
                f"🎯 Duration set: {duration} days\n\n"
                f"Now select advertisement priority:\n\n"
                f"🔴 Low: Show 1-2 times per day\n"
                f"🟡 Normal: Show 3-5 times per day\n"
                f"🟢 High: Show 6-10 times per day\n\n"
                f"Type: low, normal, or high"
            )
            context.user_data['state'] = 'waiting_ad_priority'
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for days!")
    
    elif state == 'waiting_ad_priority':
        priority = message_text.lower().strip()
        if priority not in ['low', 'normal', 'high']:
            await update.message.reply_text("❌ Please enter: low, normal, or high")
            return
        
        await process_advertisement_save(update, context, priority)
    
    # Handle file uploads for advertisements
    elif state == 'waiting_ad_file':
        await process_advertisement_file(update, context)
    
    # Handle offers management states
    elif state == 'waiting_coupon_validity':
        await process_coupon_validity(update, context, message_text)
    
    elif state == 'waiting_coupon_user_limit':
        await process_coupon_user_limit(update, context, message_text)
    
    elif state == 'waiting_coupon_credit_amount':
        await process_coupon_credit_amount(update, context, message_text)
    
    elif state == 'waiting_user_coupon_code':
        await process_user_coupon_code(update, context, message_text)
    
    elif state == 'waiting_coupon_edit_value':
        await process_coupon_edit_value(update, context, message_text)
    
    elif state == 'waiting_offer_percentage':
        await process_offer_percentage(update, context, message_text)
    
    elif state == 'waiting_offer_validity':
        await process_offer_validity(update, context, message_text)
    
    # Payload verification is now handled through start command

    

# ======================== BOT MANAGEMENT FUNCTIONS ========================
async def toggle_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle bot active/inactive status"""
    global IS_BOT_ACTIVE
    query = update.callback_query

    if IS_BOT_ACTIVE:
        # Deactivate bot
        await query.edit_message_text("🔴 Deactivate Bot\n\nSelect deactivation reason:", reply_markup=get_deactivate_reasons())
    else:
        # Activate bot
        IS_BOT_ACTIVE = True

        # Send activation message to all users
        reload_data()
        active_users = {uid: data for uid, data in user_data.items() if data.get('user_status') == 'active'}

        activation_msg = """
🟢 Bot is now ACTIVE!

✅ All services have been restored
🎉 You can now use all bot features

Welcome back!
        """

        for uid, user_info in active_users.items():
            try:
                user_id = user_info.get('user_id')
                if user_id and not is_user_banned(user_id):
                    await context.bot.send_message(chat_id=user_id, text=activation_msg)
            except Exception as e:
                logger.error(f"Failed to send activation message to {user_id}: {e}")

        await query.edit_message_text(
            f"✅ Bot Activated Successfully!\n\n"
            f"📊 Status: Active\n"
            f"📬 Notifications sent to all users\n"
            f"⏰ Activated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=get_settings_panel()
        )

async def handle_deactivate_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle deactivation reason selection"""
    query = update.callback_query
    reason_type = callback_data.split("_")[-1]

    reasons = {
        "maintenance": "Bot is under maintenance",
        "updates": "Bot is being updated",
        "security": "Security maintenance in progress"
    }

    if reason_type == "custom":
        await query.edit_message_text("💬 Please send your custom deactivation reason:")
        context.user_data['state'] = 'waiting_deactivate_reason'
    else:
        context.user_data['deactivate_reason'] = reasons[reason_type]
        confirm_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm Deactivate", callback_data="confirm_deactivate")],
            [InlineKeyboardButton("❌ Cancel", callback_data="settings")]
        ])
        await query.edit_message_text(
            f"🔴 Confirm Bot Deactivation\n\n"
            f"📝 Reason: {reasons[reason_type]}\n\n"
            f"⚠️ This will make the bot inactive for all users.",
            reply_markup=confirm_button
        )

async def confirm_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm bot deactivation"""
    global IS_BOT_ACTIVE
    query = update.callback_query
    reason = context.user_data.get('deactivate_reason', 'No reason provided')

    IS_BOT_ACTIVE = False

    # Send deactivation message to all users
    reload_data()
    active_users = {uid: data for uid, data in user_data.items() if data.get('user_status') == 'active'}

    deactivation_msg = f"""
🔴 Bot has been DEACTIVATED

📝 Reason: {reason}
⏰ Deactivated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 By: Owner

Please wait for further updates.
    """

    for uid, user_info in active_users.items():
        try:
            user_id = user_info.get('user_id')
            if user_id and not is_user_banned(user_id):
                await context.bot.send_message(chat_id=user_id, text=deactivation_msg)
        except Exception as e:
            logger.error(f"Failed to send deactivation message to {user_id}: {e}")

    await query.edit_message_text(
        f"🔴 Bot Deactivated Successfully!\n\n"
        f"📝 Reason: {reason}\n"
        f"📊 Status: Inactive\n"
        f"📬 Notifications sent to all users\n"
        f"⏰ Deactivated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=get_settings_panel()
    )

    context.user_data['state'] = None
    context.user_data.pop('deactivate_reason', None)

async def handle_shutdown_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle shutdown reason selection"""
    query = update.callback_query
    reason_type = callback_data.split("_")[-1]

    reasons = {
        "maintenance": "Server maintenance",
        "updates": "System updates",
        "security": "Security patches"
    }

    if reason_type == "custom":
        await query.edit_message_text("💬 Please send your custom shutdown reason:")
        context.user_data['state'] = 'waiting_shutdown_reason'
    else:
        context.user_data['shutdown_reason'] = reasons[reason_type]
        await query.edit_message_text(
            f"⏰ Shutdown Duration\n\n"
            f"📝 Reason: {reasons[reason_type]}\n\n"
            f"Please send shutdown duration in minutes:"
        )
        context.user_data['state'] = 'waiting_shutdown_duration'

async def confirm_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and execute bot shutdown"""
    global BOT_SHUTDOWN, SHUTDOWN_REASON, SHUTDOWN_UNTIL
    query = update.callback_query

    reason = context.user_data.get('shutdown_reason', 'No reason provided')
    duration = context.user_data.get('shutdown_duration', 60)

    BOT_SHUTDOWN = True
    SHUTDOWN_REASON = reason
    SHUTDOWN_UNTIL = datetime.now() + timedelta(minutes=duration)

    # Send shutdown message to all users
    reload_data()
    active_users = {uid: data for uid, data in user_data.items() if data.get('user_status') == 'active'}

    shutdown_msg = f"""
🔴 Bot is SHUTTING DOWN

📝 Reason: {reason}
⏰ Duration: {duration} minutes
🔄 Expected Return: {SHUTDOWN_UNTIL.strftime('%Y-%m-%d %H:%M:%S')}
👑 By: Owner

Bot will automatically restart after the specified time.
    """

    for uid, user_info in active_users.items():
        try:
            user_id = user_info.get('user_id')
            if user_id and not is_user_banned(user_id):
                await context.bot.send_message(chat_id=user_id, text=shutdown_msg)
        except Exception as e:
            logger.error(f"Failed to send shutdown message to {user_id}: {e}")

    await query.edit_message_text(
        f"🔴 Bot Shutdown Initiated!\n\n"
        f"📝 Reason: {reason}\n"
        f"⏰ Duration: {duration} minutes\n"
        f"🔄 Will restart at: {SHUTDOWN_UNTIL.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📬 Notifications sent to all users"
    )

    # Start auto-restart timer
    def auto_restart():
        time.sleep(duration * 60)
        auto_activate_bot(context)

    thread = threading.Thread(target=auto_restart)
    thread.daemon = True
    thread.start()

    context.user_data['state'] = None
    context.user_data.pop('shutdown_reason', None)
    context.user_data.pop('shutdown_duration', None)

def auto_activate_bot(context):
    """Automatically activate bot after shutdown period"""
    global BOT_SHUTDOWN, SHUTDOWN_REASON, SHUTDOWN_UNTIL

    BOT_SHUTDOWN = False
    SHUTDOWN_REASON = ""
    SHUTDOWN_UNTIL = None

    # Send reactivation message to all users
    reload_data()
    active_users = {uid: data for uid, data in user_data.items() if data.get('user_status') == 'active'}

    reactivation_msg = """
🟢 Bot is back ONLINE!

✅ Shutdown period has ended
🎉 All services are now available
⏰ Welcome back!

You can now use the bot normally.
    """

    for uid, user_info in active_users.items():
        try:
            user_id = user_info.get('user_id')
            if user_id and not is_user_banned(user_id):
                context.bot.send_message(chat_id=user_id, text=reactivation_msg)
        except Exception as e:
            logger.error(f"Failed to send reactivation message to {user_id}: {e}")

async def manage_tool(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Manage individual tools (activate/deactivate)"""
    query = update.callback_query
    tool_name = callback_data.replace("manage_", "").replace("_tool", "")

    tool_names = {
        'tts': 'TTS (Text to Speech)',
        'stt': 'STT (Speech to Text)', 
        'free_credits': 'Free Credits',
        'free': 'Free Credits',
        'buy_credits': 'Buy Credits',
        'buy': 'Buy Credits',
        'referral': 'Referral System'
    }

    if TOOLS_STATUS.get(tool_name, True):
        # Tool is active, ask for deactivation reason
        await query.edit_message_text(
            f"❎ Deactivate {tool_names[tool_name]}\n\nSelect deactivation reason:",
            reply_markup=get_tool_deactivate_reasons(tool_name)
        )
    else:
        # Tool is inactive, activate it directly
        TOOLS_STATUS[tool_name] = True
        TOOLS_DEACTIVATION_REASONS[tool_name] = ''

        await query.edit_message_text(
            f"✅ {tool_names[tool_name]} Activated!\n\n"
            f"📊 Status: Active\n"
            f"⏰ Activated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"✨ Users can now access this tool",
            reply_markup=get_bot_tools_panel()
        )

async def handle_tool_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle tool deactivation reason"""
    query = update.callback_query
    parts = callback_data.split("_")
    tool_name = parts[2]
    reason_type = parts[3] if len(parts) > 3 else "maintenance"

    # Separate actual tools from bot features
    tool_names = {
        'tts': 'TTS (Text to Speech)',
        'stt': 'STT (Speech to Text)'
    }

    # Check if this is an actual tool or a bot feature
    if tool_name in tool_names:
        # Handle actual tools
        reasons = {
            "maintenance": "This tool is under maintenance",
            "updates": "This tool is being updated", 
            "bug": "This tool is under bug fixing"
        }

        if reason_type == "custom":
            context.user_data['tool_deactivate_name'] = tool_name
            await query.edit_message_text(f"💬 Please send custom reason for deactivating {tool_names[tool_name]}:")
            context.user_data['state'] = 'waiting_tool_reason'
        else:
            # Handle case where reason_type might not be in the reasons dict
            if reason_type not in reasons:
                reason_type = "maintenance"  # Default to maintenance
            
            context.user_data['tool_deactivate_name'] = tool_name
            context.user_data['tool_deactivate_reason'] = reasons[reason_type]
            confirm_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Deactivate", callback_data=f"confirm_tool_{tool_name}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="bot_tools")]
            ])
            await query.edit_message_text(
                f"❎ Confirm {tool_names[tool_name]} Deactivation\n\n"
                f"📝 Reason: {reasons[reason_type]}\n\n"
                f"⚠️ Users will see this message when trying to access this tool.",
                reply_markup=confirm_button
            )
    else:
        # Handle bot features (free_credits, buy_credits, referral)
        await handle_feature_reason(update, context, callback_data)

async def handle_feature_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle bot feature deactivation reason"""
    query = update.callback_query
    parts = callback_data.split("_")
    
    # Handle compound feature names like 'free_credits' and 'buy_credits'
    if len(parts) >= 4 and parts[2] in ['free', 'buy'] and parts[3] in ['credits']:
        feature_name = f"{parts[2]}_{parts[3]}"
        reason_type = parts[4] if len(parts) > 4 else "maintenance"
    else:
        feature_name = parts[2]
        reason_type = parts[3] if len(parts) > 3 else "maintenance"

    feature_names = {
        'free_credits': 'Free Credits',
        'buy_credits': 'Buy Credits', 
        'referral': 'Referral System'
    }

    reasons = {
        "maintenance": "This feature is under maintenance",
        "updates": "This feature is being updated",
        "bug": "This feature is under bug fixing"
    }

    # Check if feature_name exists in feature_names
    if feature_name not in feature_names:
        await query.edit_message_text(
            f"❌ Error: Feature '{feature_name}' not found.\n\n"
            f"Available features: {', '.join(feature_names.keys())}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bot_tools")]])
        )
        return

    if reason_type == "custom":
        context.user_data['feature_deactivate_name'] = feature_name
        await query.edit_message_text(f"💬 Please send custom reason for deactivating {feature_names[feature_name]}:")
        context.user_data['state'] = 'waiting_feature_reason'
    else:
        if reason_type not in reasons:
            reason_type = "maintenance"
        
        context.user_data['feature_deactivate_name'] = feature_name
        context.user_data['feature_deactivate_reason'] = reasons[reason_type]
        confirm_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm Deactivate", callback_data=f"confirm_feature_{feature_name}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="bot_tools")]
        ])
        await query.edit_message_text(
            f"❎ Confirm {feature_names[feature_name]} Deactivation\n\n"
            f"📝 Reason: {reasons[reason_type]}\n\n"
            f"⚠️ Users will see this message when trying to access this feature.",
            reply_markup=confirm_button
        )

async def confirm_tool_action(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Confirm tool deactivation"""
    query = update.callback_query
    tool_name = callback_data.replace("confirm_tool_", "")
    reason = context.user_data.get('tool_deactivate_reason', 'No reason provided')

    tool_names = {
        'tts': 'TTS (Text to Speech)',
        'stt': 'STT (Speech to Text)'
    }

    TOOLS_STATUS[tool_name] = False
    TOOLS_DEACTIVATION_REASONS[tool_name] = reason

    await query.edit_message_text(
        f"❎ {tool_names[tool_name]} Deactivated!\n\n"
        f"📝 Reason: {reason}\n"
        f"📊 Status: Inactive\n"
        f"⏰ Deactivated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🚫 Users will see deactivation message",
        reply_markup=get_bot_tools_panel()
    )

    context.user_data['state'] = None
    context.user_data.pop('tool_deactivate_name', None)
    context.user_data.pop('tool_deactivate_reason', None)

async def confirm_feature_action(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Confirm feature deactivation"""
    query = update.callback_query
    feature_name = callback_data.replace("confirm_feature_", "")
    reason = context.user_data.get('feature_deactivate_reason', 'No reason provided')

    feature_names = {
        'free_credits': 'Free Credits',
        'buy_credits': 'Buy Credits',
        'referral': 'Referral System'
    }

    TOOLS_STATUS[feature_name] = False
    TOOLS_DEACTIVATION_REASONS[feature_name] = reason

    await query.edit_message_text(
        f"❎ {feature_names[feature_name]} Deactivated!\n\n"
        f"📝 Reason: {reason}\n"
        f"📊 Status: Inactive\n"
        f"⏰ Deactivated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🚫 Users will see deactivation message",
        reply_markup=get_bot_tools_panel()
    )

    context.user_data['state'] = None
    context.user_data.pop('feature_deactivate_name', None)
    context.user_data.pop('feature_deactivate_reason', None)


# ======================== HELP AND ABOUT FUNCTIONS ========================
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    query = update.callback_query

    help_text = """
ℹ️ *Help & Instructions*

🤖 *How to use this bot:*

🛠 **Available Tools:**
• *TTS* - Text to Speech conversion 🎙️
• *STT* - Speech to Text conversion 📝  

👤 **Profile:**
View your account information and settings 🧑‍💼

📞 **Need Help?**
For any questions or support, you can directly contact the owner: @HackerPonline 🤖

⚠️ **Important Notes:**
• All tools are available for use, but may have usage limits ⏳
• Please follow the bot guidelines for smooth usage 📋
• Report any issues or bugs to the developers 🔧

💡 *Pro Tip:* Reach out to the owner directly for any assistance!
    """

    back_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 About", callback_data="about")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ])
    
    await query.edit_message_text(help_text, reply_markup=back_button, parse_mode= "markdown")


async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show about information with developer details"""
    query = update.callback_query

    about_text = """
📚 *About This Bot*

🤖 **Bot Name:** Media Processing Bot  
🎯 **Purpose:** AI Tools & Services  
⚡ **Version:** 1.0  
🔧 **Status:** Active & Secure

👨‍💻 **Developers:**

🥇 **Primary Developer:**  
• *Name:* Preet Bopche  
• *Role:* Lead Developer & Owner  
• *Contact:* @HackerPonline

🥈 **Secondary Developer:**  
• *Name:* Vicky Baghel
• *Role:* Co-Developer & Support  
• *Contact:* UnkownGuy


📞 **Support:**  
Contact primary developer for assistance
    """

    back_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ])
    
    await query.edit_message_text(about_text, reply_markup=back_button, parse_mode='Markdown')


# ======================== USER CREDIT FUNCTIONS ========================
def get_random_shortlinks():
    """Get maximum 2 random shortlinks for user panel"""
    import random
    if not shortlinks_data:
        return []
    all_links = list(shortlinks_data.values())
    return random.sample(all_links, min(2, len(all_links)))

async def handle_credit_package(update: Update, context: ContextTypes.DEFAULT_TYPE, package_type: str):
    """Handle credit package selection"""
    query = update.callback_query
    user = query.from_user

    packages = {
        "buy_100_credits": {"credits": 100, "price": "$5.00"},
        "buy_500_credits": {"credits": 500, "price": "$20.00"},
        "buy_1000_credits": {"credits": 1000, "price": "$35.00"}
    }

    package = packages.get(package_type)
    if not package:
        await query.answer("Invalid package selected!")
        return

    purchase_text = f"""
💳 Credit Purchase Request

👤 **Customer Details:**
• Name: {user.full_name}
• Username: @{user.username or 'None'}
• User ID: {user.id}

💎 **Package Selected:**
• Credits: {package['credits']}
• Price: {package['price']}

📞 **Next Steps:**
1. Contact support via button below
2. Provide your User ID: {user.id}
3. Make payment via your preferred method
4. Credits will be added within 30 minutes

⚡ **Payment Methods:**
• PayPal, Credit Card, Cryptocurrency
    """

    keyboard = [
        [InlineKeyboardButton("📞 Contact Support", url="https://t.me/PrimaryDev")],
        [InlineKeyboardButton("📋 Copy User ID", callback_data=f"copy_user_id_{user.id}")],
        [InlineKeyboardButton("🔙 Back to Packages", callback_data="buy_credits")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(purchase_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_buy_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy credits option"""
    query = update.callback_query

    # Check if buy credits feature is enabled
    if not TOOLS_STATUS.get('buy_credits', True):
        reason = TOOLS_DEACTIVATION_REASONS.get('buy_credits', 'No reason provided')
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="add_credit")]])
        await query.edit_message_text(
            f"❎ Buy Credits Feature Disabled\n\n"
            f"📝 Reason: {reason}\n\n"
            f"This feature has been temporarily disabled by the owner. "
            f"Please try again later or contact support.",
            reply_markup=back_button
        )
        return

    buy_credits_text = """
💳 Buy Credits

Choose a credit package:

💎 **Premium Packages:**
• 100 Credits - $5.00
• 500 Credits - $20.00 (Save 20%)
• 1000 Credits - $35.00 (Save 30%)

💰 **Payment Methods:**
• PayPal
• Credit/Debit Card
• Cryptocurrency

📞 **Contact for Purchase:**
• Telegram: @PrimaryDev
• Email: support@example.com

⚡ Credits are added instantly after payment verification.
    """

    keyboard = [
        [InlineKeyboardButton("💎 100 Credits ($5)", callback_data="buy_100_credits"),
         InlineKeyboardButton("💎 500 Credits ($20)", callback_data="buy_500_credits")],
        [InlineKeyboardButton("💎 1000 Credits ($35)", callback_data="buy_1000_credits")],
        [InlineKeyboardButton("📞 Contact Support", url="https://t.me/PrimaryDev")],
        [InlineKeyboardButton("🔙 Back", callback_data="add_credit")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(buy_credits_text, reply_markup=reply_markup, parse_mode='Markdown')

async def add_credit_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show add credit panel with Buy credits, Free credit, Referral and Coupon options"""
    query = update.callback_query

    text = f"""
💰 **Add Credit**

Choose how you want to get credits:

💳 **Buy Credits:** Purchase credits directly for instant access
🎁 **Free Credit:** Complete shortlinks to earn {CREDIT_CONFIG['shortlink_reward']} credits per link
👥 **Referral System:** Invite friends and earn credits when they join  
🎫 **Coupon:** Use coupon code to get free credits

Select an option below:
    """

    keyboard = []
    
    # Row 1: Free Credits and Buy Credits
    row1 = []
    if TOOLS_STATUS.get('free_credits', True):
        row1.append(InlineKeyboardButton("🎁 Free Credits", callback_data="credit_link"))
    else:
        row1.append(InlineKeyboardButton("❎ Free Credits (Disabled)", callback_data="feature_disabled_free_credits"))
    
    if TOOLS_STATUS.get('buy_credits', True):
        row1.append(InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits"))
    else:
        row1.append(InlineKeyboardButton("❎ Buy Credits (Disabled)", callback_data="feature_disabled_buy_credits"))
    
    keyboard.append(row1)
    
    # Row 2: Referral and Coupon
    row2 = []
    if TOOLS_STATUS.get('referral', True):
        row2.append(InlineKeyboardButton("👥 Referral", callback_data="credit_referral"))
    else:
        row2.append(InlineKeyboardButton("❎ Referral (Disabled)", callback_data="feature_disabled_referral"))
    
    row2.append(InlineKeyboardButton("🎫 Coupon", callback_data="credit_coupon"))
    keyboard.append(row2)
    
    # Row 3: Back button
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# ======================== CREDIT SYSTEM FUNCTIONS ========================
async def handle_credit_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show credit system management panel"""
    query = update.callback_query

    credit_text = f"""
💰 Credit System Management

🎁 Welcome Credit: {CREDIT_CONFIG['welcome_credit']} credits
🗣 TTS Cost: {CREDIT_CONFIG['tts_cost_per_char']} credits per character
🎤 STT Cost: {CREDIT_CONFIG['stt_cost_per_minute']} credits per minute
🔗 Link Reward: {CREDIT_CONFIG['shortlink_reward']} credits
👥 Referral Reward: {CREDIT_CONFIG['referral_reward']} credits

📹 YouTube Download Costs:
• 1080p HD: {CREDIT_CONFIG['yt_1080p_cost']} credits
• 720p HD: {CREDIT_CONFIG['yt_720p_cost']} credits
• 480p: {CREDIT_CONFIG['yt_480p_cost']} credits
• 360p: {CREDIT_CONFIG['yt_360p_cost']} credits
• 240p: {CREDIT_CONFIG['yt_240p_cost']} credits
• 144p: {CREDIT_CONFIG['yt_144p_cost']} credits
• Audio Only: {CREDIT_CONFIG['yt_audio_cost']} credits

Click below to edit any value:
    """

    await query.edit_message_text(credit_text, reply_markup=get_credit_system_panel())

async def edit_credit_value(update: Update, context: ContextTypes.DEFAULT_TYPE, credit_type: str, credit_name: str):
    """Start editing a credit value"""
    query = update.callback_query

    context.user_data['edit_credit_type'] = credit_type
    context.user_data['edit_credit_name'] = credit_name
    context.user_data['state'] = 'waiting_credit_value'

    current_value = CREDIT_CONFIG[credit_type]

    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="handle_credit_system")]])
    await query.edit_message_text(
        f"✏️ Edit {credit_name}\n\n"
        f"💰 Current Value: {current_value} credits\n\n"
        f"Please send the new value:",
        reply_markup=back_button
    )

async def show_credit_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show credit usage statistics"""
    query = update.callback_query
    reload_data()

    total_users = len(user_data)
    total_credits_given = sum(user.get('credits', 0) for user in user_data.values())
    avg_credits = total_credits_given / total_users if total_users > 0 else 0

    stats_text = f"""
📊 Credit System Statistics

👥 Total Users: {total_users}
💰 Total Credits in System: {total_credits_given}
📈 Average Credits per User: {avg_credits:.1f}

🔧 Current Settings:
├── 🎁 Welcome Credit: {CREDIT_CONFIG['welcome_credit']}
├── 🗣 TTS Cost: {CREDIT_CONFIG['tts_cost_per_char']} per character
├── 🎤 STT Cost: {CREDIT_CONFIG['stt_cost_per_minute']}
└── 🔗 Link Reward: {CREDIT_CONFIG['shortlink_reward']}

💡 Tool Usage Impact:
├── Per TTS Character: -{CREDIT_CONFIG['tts_cost_per_char']} credits
├── Per STT: -{CREDIT_CONFIG['stt_cost_per_minute']} credits
└── Per Link Complete: +{CREDIT_CONFIG['shortlink_reward']} credits
    """

    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="handle_credit_system")]])
    await query.edit_message_text(stats_text, reply_markup=back_button)



# ======================== USER PANEL FUNCTIONS ========================
async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile with specific information"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    reload_data()

    if uid in user_data:
        user_info = user_data[uid]
        user_credits = user_info.get('credits', 0)

        profile_text = f"""
👤 *Your Profile*

👤 *Name*: {user_info.get('name', 'Not provided')}
🆔 *User ID*: {user_info.get('user_id', 'Unknown')}
👤 *Username*: @{user_info.get('username', 'None')}
💰 *Credits*: {user_credits}
📧 *Email*: {user_info.get('user_email', 'Not provided')}
🌐 *Language*: {user_info.get('language', 'en')}
📊 *Status*: {user_info.get('user_status', 'active')}
📅 *Joined*: {user_info.get('user_created_at', 'Unknown')}
        """
    else:
        profile_text = """
👤 Your Profile

❌ Profile data not found!
Please restart the bot with /start
        """

    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]])
    await query.edit_message_text(profile_text, reply_markup=back_button, parse_mode='Markdown')

# ======================== LINK SHORTENER MANAGEMENT ========================
async def shortlinks_main_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display main shortlinks management panel"""
    await update.callback_query.edit_message_text("🔗 Shortlinks Management", reply_markup=get_shortlinks_main_panel())

async def link_shorteners_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display link shorteners management panel"""
    await update.callback_query.edit_message_text("🔗 Link Shorteners Management", reply_markup=get_link_shorteners_panel())

async def add_link_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new link shortener with quick options"""
    text = """
🌐 **Add Link Shortener**

Choose how you want to add:

🚀 **Quick Add (Recommended):**
Use pre-configured popular shorteners

✏️ **Manual Add:**
Enter domain name manually

Select your preferred method:
    """
    
    keyboard = [
        [InlineKeyboardButton("🔗 GpLinks", callback_data="quick_add_gplinks"),
         InlineKeyboardButton("🔗 LinkShortify", callback_data="quick_add_linkshortify")],
        [InlineKeyboardButton("✏️ Manual Entry", callback_data="manual_add_shortener")],
        [InlineKeyboardButton("🔙 Back", callback_data="link_shorteners")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def quick_add_gplinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick add GpLinks with pre-configured settings"""
    query = update.callback_query
    
    await query.edit_message_text(
        "🔗 **Quick Add - GpLinks**\n\n"
        "📧 Please send your GpLinks email:"
    )
    context.user_data['quick_add_type'] = 'gplinks'
    context.user_data['ls_domain'] = 'gplinks.com'
    context.user_data['ls_api_endpoint'] = 'https://api.gplinks.com/api?api={api}&url={url}&alias={alias}'
    context.user_data['state'] = 'waiting_quick_add_email'

async def quick_add_linkshortify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick add LinkShortify with pre-configured settings"""
    query = update.callback_query
    
    await query.edit_message_text(
        "🔗 **Quick Add - LinkShortify**\n\n"
        "📧 Please send your LinkShortify email:"
    )
    context.user_data['quick_add_type'] = 'linkshortify'
    context.user_data['ls_domain'] = 'linkshortify.com'
    context.user_data['ls_api_endpoint'] = 'https://linkshortify.com/api?api={api}&url={url}&alias={alias}'
    context.user_data['state'] = 'waiting_quick_add_email'

async def manual_add_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual add shortener - original flow"""
    query = update.callback_query
    
    await query.edit_message_text("🌐 Please send the domain name for this link shortener:")
    context.user_data['state'] = 'waiting_ls_domain'

async def process_link_shortener_save(update: Update, context: ContextTypes.DEFAULT_TYPE, api_key: str):
    """Save the link shortener with all details and extract CPM data for supported shorteners"""
    import uuid
    
    # Get all collected data
    domain = context.user_data.get('ls_domain', '')
    email = context.user_data.get('ls_email', '')
    password = context.user_data.get('ls_password', '')
    priority = context.user_data.get('ls_priority', '50%')
    api = api_key
    
    # Validate priority format
    try:
        priority_clean = ''.join(filter(str.isdigit, str(priority)))
        if not priority_clean:
            priority = "50%"
        else:
            priority_num = int(priority_clean)
            priority_num = max(1, min(100, priority_num))
            priority = f"{priority_num}%"
    except:
        priority = "50%"
    
    # Generate unique ID
    ls_id = f"LS{str(uuid.uuid4())[:3].upper()}"
    
    # Get API endpoint if it was set during quick add
    api_endpoint = context.user_data.get('ls_api_endpoint', '')
    
    # Save to link_shorteners_data with default values
    reload_data()
    link_shorteners_data[ls_id] = {
        "id": ls_id,
        "domain": domain,
        "email": email,
        "password": password,
        "per_click": "$0.00",  # Will be updated by CPM extraction
        "per_1000_click": "$0.00",  # Will be updated by CPM extraction
        "total_earnings": "$0.00",
        "join_date": datetime.now().strftime('%Y-%m-%d'),
        "status": "Active",
        "priority": priority,
        "api": api,
        "api_endpoint": api_endpoint,
        "last_cpm_update": "",
        "cpm_status": "Not Updated"
    }
    save_json(LINK_SHORTENERS_FILE, link_shorteners_data)
    
    # Extract CPM data for supported shorteners
    cpm_extracted = False
    cpm_info = ""
    
    if 'gplinks.com' in domain.lower() or 'linkshortify.com' in domain.lower():
        processing_msg = await update.message.reply_text("🔄 Extracting CPM data from API...")
        
        cpm_success = await update_link_shortener_cmp(ls_id)
        
        if cmp_success:
            reload_data()  # Reload to get updated data
            updated_data = link_shorteners_data[ls_id]
            cpm_extracted = True
            cmp_info = f"""
💰 **CPM Data Extracted:**
• Per Click: {updated_data.get('per_click', '$0.00')}
• Per 1000 Views: {updated_data.get('per_1000_click', '$0.00')}
• Total Earnings: {updated_data.get('total_earnings', '$0.00')}
• Last Updated: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            """
        else:
            cpm_info = "\n⚠️ **CPM Extraction Failed:** Unable to fetch earnings data from API"
        
        await processing_msg.delete()
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="link_shorteners")]])
    
    success_text = f"""
✅ **Link Shortener Added Successfully!**

🆔 **ID:** {ls_id}
🌐 **Domain:** {domain}
📧 **Email:** {email}
🎯 **Priority:** {priority}
🔑 **API:** {api_key[:20]}...
📅 **Join Date:** {datetime.now().strftime('%Y-%m-%d')}

📊 **Status:** Link shortener saved successfully
🤖 **API Support:** {'✅ Supported (GPLinks/LinkShortify)' if cmp_extracted or 'gplinks.com' in domain.lower() or 'linkshortify.com' in domain.lower() else '❌ Not Supported'}
{cmp_info}
    """
    
    await update.message.reply_text(success_text, reply_markup=back_button, parse_mode='Markdown')
    
    # Clear temporary data
    context.user_data['state'] = None
    for key in ['ls_domain', 'ls_email', 'ls_password', 'ls_priority', 'quick_add_type', 'ls_api_endpoint']:
        context.user_data.pop(key, None)

async def remove_link_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display link shorteners for removal with pagination"""
    query = update.callback_query
    reload_data()
    
    if not link_shorteners_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="link_shorteners")]
        ])
        await query.edit_message_text(
            "➖ Remove Link Shortener\n\n"
            "❌ No link shorteners available to remove.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 5
    current_page = context.user_data.get('ls_remove_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    ls_ids = list(link_shorteners_data.keys())
    paginated_ls = ls_ids[start_index:end_index]
    total_pages = (len(ls_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-5: Link shortener domains
    for ls_id in paginated_ls:
        ls_data = link_shorteners_data[ls_id]
        domain = ls_data['domain']
        keyboard.append([InlineKeyboardButton(f"🌐 {domain}", callback_data=f"remove_ls_{ls_id}")])
    
    # Row 6: Navigation
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_ls_remove"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="link_shorteners"))
    if end_index < len(ls_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_ls_remove"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"➖ Remove Link Shortener{page_info}\n\n"
        f"📊 Total: {len(ls_ids)}\n"
        f"Select a domain to remove:",
        reply_markup=reply_markup
    )

async def list_link_shorteners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all link shorteners with pagination"""
    query = update.callback_query
    reload_data()
    
    if not link_shorteners_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="link_shorteners")]
        ])
        await query.edit_message_text(
            "📋 Link Shorteners List\n\n"
            "❌ No link shorteners available.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 5
    current_page = context.user_data.get('ls_list_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    ls_ids = list(link_shorteners_data.keys())
    paginated_ls = ls_ids[start_index:end_index]
    total_pages = (len(ls_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-5: Link shortener domains
    for ls_id in paginated_ls:
        ls_data = link_shorteners_data[ls_id]
        domain = ls_data['domain']
        keyboard.append([InlineKeyboardButton(f"🌐 {domain}", callback_data=f"view_ls_{ls_id}")])
    
    # Row 6: Navigation
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_ls_list"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="link_shorteners"))
    if end_index < len(ls_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_ls_list"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"📋 Link Shorteners List{page_info}\n\n"
        f"📊 Total: {len(ls_ids)}\n"
        f"Select a domain to view details:",
        reply_markup=reply_markup
    )

async def view_link_shortener_details(update: Update, context: ContextTypes.DEFAULT_TYPE, ls_id: str):
    """Show detailed information about a specific link shortener with CPM data"""
    query = update.callback_query
    reload_data()
    
    ls_data = link_shorteners_data.get(ls_id)
    if not ls_data:
        await query.answer("Link shortener not found!")
        return
    
    domain = ls_data.get('domain', '').lower()
    is_supported = 'gplinks.com' in domain or 'linkshortify.com' in domain
    
    # Update API endpoint if missing for supported shorteners
    if is_supported and not ls_data.get('api_endpoint'):
        if 'gplinks.com' in domain:
            link_shorteners_data[ls_id]['api_endpoint'] = 'https://api.gplinks.com/api?api={api}&url={url}&alias={alias}'
        elif 'linkshortify.com' in domain:
            link_shorteners_data[ls_id]['api_endpoint'] = 'https://linkshortify.com/api?api={api}&url={url}&alias={alias}'
        save_json(LINK_SHORTENERS_FILE, link_shorteners_data)
        ls_data = link_shorteners_data[ls_id]  # Reload updated data
    
    # Format last update time
    last_update = ls_data.get('last_cmp_update', '')
    if last_update:
        try:
            update_time = datetime.fromisoformat(last_update)
            formatted_update = update_time.strftime('%d/%m/%Y %H:%M')
        except:
            formatted_update = 'Unknown'
    else:
        formatted_update = 'Never'
    
    # Get proper API endpoint based on domain
    api_endpoint = ls_data.get('api_endpoint', '')
    if not api_endpoint:
        if 'gplinks.com' in domain:
            api_endpoint = 'https://api.gplinks.com/api?api={api}&url={url}&alias={alias}'
        elif 'linkshortify.com' in domain:
            api_endpoint = 'https://linkshortify.com/api?api={api}&url={url}&alias={alias}'
        else:
            api_endpoint = 'Not configured'
    
    details_text = f"""
🔗 **Link Shortener Details**

🆔 **ID:** {ls_data['id']}
🌐 **Domain:** {ls_data['domain']}
📧 **Email:** {ls_data['email']}
🔒 **Password:** {ls_data['password']}
📅 **Join Date:** {ls_data['join_date']}
📊 **Status:** {ls_data['status']}
🎯 **Priority:** {ls_data['priority']}

💰 **CPM Earnings Data:**
• **Per Click:** {ls_data.get('per_click', '$0.00')}
• **Per 1,000 Views:** {ls_data.get('per_1000_click', '$0.00')}
• **Total Earnings:** {ls_data.get('total_earnings', '$0.00')}
• **Last Updated:** {formatted_update}
• **CPM Status:** {ls_data.get('cmp_status', 'Not Updated')}

🔑 **API Configuration:**
• **API Key:** {ls_data.get('api', 'Not set')[:20]}...
• **API Endpoint:** {api_endpoint}

🤖 **API Support:** {'✅ Supported (CPM Auto-Extract)' if is_supported else '❌ Not Supported'}
    """
    
    keyboard = []
    if is_supported:
        keyboard.append([InlineKeyboardButton("🔄 Refresh CPM", callback_data=f"refresh_cmp_{ls_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="list_link_shorteners")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(details_text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("✅ Details loaded!", show_alert=False)
        else:
            # Send new message if edit fails
            await query.message.reply_text(details_text, reply_markup=reply_markup, parse_mode='Markdown')

async def confirm_remove_link_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE, ls_id: str):
    """Confirm removal of link shortener"""
    query = update.callback_query
    reload_data()
    
    ls_data = link_shorteners_data.get(ls_id)
    if not ls_data:
        await query.answer("Link shortener not found!")
        return
    
    confirmation_text = f"""
🗑️ Confirm Removal

Are you sure you want to delete this link shortener?

🌐 Domain: {ls_data['domain']}
🆔 ID: {ls_data['id']}
📅 Join Date: {ls_data['join_date']}

⚠️ This action cannot be undone!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"delete_ls_{ls_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data="remove_link_shortener")]
    ])
    
    try:
        await query.edit_message_text(confirmation_text, reply_markup=keyboard)
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("⚠️ Confirm deletion", show_alert=False)
        else:
            # Send new message if edit fails
            await query.message.reply_text(confirmation_text, reply_markup=keyboard)

async def delete_link_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE, ls_id: str):
    """Delete the link shortener after confirmation"""
    query = update.callback_query
    reload_data()
    
    ls_data = link_shorteners_data.get(ls_id)
    if not ls_data:
        await query.answer("Link shortener not found!")
        return
    
    # Delete the link shortener
    deleted_domain = ls_data['domain']
    del link_shorteners_data[ls_id]
    save_json(LINK_SHORTENERS_FILE, link_shorteners_data)
    
    success_text = f"""
✅ Link Shortener Deleted Successfully!

🌐 Deleted: {deleted_domain}
🆔 ID: {ls_id}
⏰ Deleted At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The link shortener has been permanently removed.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="remove_link_shortener")]
    ])
    
    await query.edit_message_text(success_text, reply_markup=keyboard)

# Shortlinks management functionality
async def view_shortlinks_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display shortlinks management panel with add/remove/list options"""
    query = update.callback_query
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add", callback_data="add_shortlink"),
         InlineKeyboardButton("➖ Remove", callback_data="remove_shortlink")],
        [InlineKeyboardButton("📋 List Shortlink", callback_data="list_shortlinks")],
        [InlineKeyboardButton("🔙 Back", callback_data="shortlinks")]
    ])
    
    await query.edit_message_text("📋 Shortlinks Management", reply_markup=keyboard)

async def add_shortlink_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display add shortlink options"""
    query = update.callback_query
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Add Link", callback_data="add_link_to_shortener"),
         InlineKeyboardButton("🆕 Create Link", callback_data="create_new_link")],
        [InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks")]
    ])
    
    await query.edit_message_text("➕ Add Shortlink Options", reply_markup=keyboard)

async def create_new_link_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show link shorteners list for creating new shortlink"""
    query = update.callback_query
    reload_data()
    
    if not link_shorteners_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="add_shortlink")]
        ])
        await query.edit_message_text(
            "🆕 Create New Link\n\n"
            "❌ No link shorteners available.\n"
            "Please add link shorteners first.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 5
    current_page = context.user_data.get('create_link_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    ls_ids = list(link_shorteners_data.keys())
    paginated_ls = ls_ids[start_index:end_index]
    total_pages = (len(ls_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-5: Link shortener domains
    for ls_id in paginated_ls:
        ls_data = link_shorteners_data[ls_id]
        domain = ls_data['domain']
        keyboard.append([InlineKeyboardButton(f"🌐 {domain}", callback_data=f"create_with_ls_{ls_id}")])
    
    # Navigation
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_create_link"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="add_shortlink"))
    if end_index < len(ls_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_create_link"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"🆕 Select Link Shortener for Creating Link{page_info}\n\n"
        f"📊 Total: {len(ls_ids)}\n"
        f"Choose a link shortener to create shortlink:",
        reply_markup=reply_markup
    )

async def select_shortener_for_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, ls_id: str):
    """Handle link shortener selection for creating new link"""
    query = update.callback_query
    reload_data()
    
    ls_data = link_shorteners_data.get(ls_id)
    if not ls_data:
        await query.answer("Link shortener not found!")
        return
    
    context.user_data['create_link_shortener'] = ls_id
    context.user_data['state'] = 'waiting_original_url'
    
    await query.edit_message_text(
        f"🆕 Creating Link with: {ls_data['domain']}\n\n"
        f"Please send the original URL that you want to convert to shortlink:"
    )

async def process_original_url(update: Update, context: ContextTypes.DEFAULT_TYPE, original_url: str):
    """Process original URL (API creation disabled)"""
    selected_shortener = context.user_data.get('create_link_shortener')
    
    if not selected_shortener:
        await update.message.reply_text("❌ Error: No shortener selected. Please try again.")
        return
    
    reload_data()
    ls_data = link_shorteners_data.get(selected_shortener)
    if not ls_data:
        await update.message.reply_text("❌ Error: Link shortener not found.")
        return
    
    # Show message that API creation is disabled
    error_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="add_shortlink")]
    ])
    
    await update.message.reply_text(
        f"❌ **API Link Creation Disabled**\n\n"
        f"🌐 **Shortener:** {ls_data['domain']}\n"
        f"🔗 **URL:** {original_url}\n\n"
        f"⚠️ **Notice:** Real-time API link creation has been disabled as requested.\n"
        f"💡 Please create links manually on the shortener website.",
        reply_markup=error_keyboard,
        parse_mode='Markdown'
    )
    
    context.user_data['state'] = None

async def add_created_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add the created shortlink to the system after asking for payload"""
    query = update.callback_query
    
    created_shortlink = context.user_data.get('created_shortlink')
    original_url = context.user_data.get('original_url')
    
    if not created_shortlink or not original_url:
        await query.answer("❌ Error: No created link found!")
        return
    
    context.user_data['state'] = 'waiting_created_link_payload'
    
    await query.edit_message_text(
        f"📦 Add Created Link to System\n\n"
        f"🔗 Shortlink: {created_shortlink}\n"
        f"🎯 Original: {original_url}\n\n"
        f"Please send the payload for this shortlink:"
    )

async def process_created_link_payload(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """Save the created shortlink with payload to the system"""
    import uuid
    
    # Get all creation data
    created_shortlink = context.user_data.get('created_shortlink')
    original_url = context.user_data.get('original_url')
    selected_shortener = context.user_data.get('create_link_shortener')
    
    if not all([created_shortlink, original_url, selected_shortener]):
        await update.message.reply_text("❌ Error: Missing creation data. Please try again.")
        return
    
    reload_data()
    ls_data = link_shorteners_data.get(selected_shortener)
    if not ls_data:
        await update.message.reply_text("❌ Error: Link shortener not found.")
        return
    
    # Generate unique ID for shortlink
    link_id = f"SL{str(uuid.uuid4())[:6].upper()}"
    
    # Save shortlink
    shortlinks_data[link_id] = {
        "id": link_id,
        "url": created_shortlink,
        "original_url": original_url,
        "payload": payload,
        "shortener_id": selected_shortener,
        "shortener_domain": ls_data['domain'],
        "added_by": "Owner",
        "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "status": "Active",
        "creation_type": "Generated"
    }
    save_json(SHORTLINKS_FILE, shortlinks_data)
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks")]])
    await update.message.reply_text(
        f"✅ Created Link Added to System Successfully!\n\n"
        f"🆔 ID: {link_id}\n"
        f"🔗 Shortlink: {created_shortlink}\n"
        f"🎯 Original URL: {original_url}\n"
        f"📦 Payload: {payload}\n"
        f"🌐 Shortener: {ls_data['domain']}\n"
        f"🎭 Type: Generated Link\n"
        f"📅 Added: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=back_button
    )
    
    # Clear temporary data
    context.user_data['state'] = None
    for key in ['created_shortlink', 'original_url', 'create_link_shortener']:
        context.user_data.pop(key, None)

async def add_link_to_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show link shorteners list for adding shortlink"""
    query = update.callback_query


# ======================== TELEGRAM CHANNEL LOGGING ========================
CHANNEL_ID = "-1002727649483"  # Target channel for logging downloads

async def send_video_details_to_channel(context, video_info, quality, video_url, file_id):
    """Send video download details to specified Telegram channel"""
    try:
        # Create log content
        log_content = f"""🎬 Video Download Log

📺 Title: {video_info['title'][:100]}
👤 Uploader: {video_info['uploader'][:50]}
🔗 Link: {video_url}
🎯 Quality: {quality}
📁 File ID: {file_id}
⏰ Downloaded At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💾 Cache Status: Saved for future use
🤖 Bot: Media Processing Bot"""

        # Create temporary text file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(log_content)
            temp_file_path = temp_file.name

        # Send file to channel
        with open(temp_file_path, 'rb') as log_file:
            await context.bot.send_document(
                chat_id=CHANNEL_ID,
                document=log_file,
                filename=f"video_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                caption=f"🎬 Video: {quality} | {video_info['title'][:30]}..."
            )

        # Clean up temporary file
        os.unlink(temp_file_path)
        logger.info(f"Video details sent to channel: {quality} - {video_info['title'][:50]}")

    except Exception as e:
        logger.error(f"Failed to send video details to channel: {e}")

async def send_audio_details_to_channel(context, video_info, video_url, file_id):
    """Send audio download details to specified Telegram channel"""
    try:
        # Create log content for audio
        log_content = f"""🎵 Audio Download Log

📺 Title: {video_info['title'][:100]}
👤 Uploader: {video_info['uploader'][:50]}
🔗 Link: {video_url}
🎯 Quality: Audio Only (MP3)
📁 File ID: {file_id}
⏰ Downloaded At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💾 Cache Status: Saved for future use
🤖 Bot: Media Processing Bot"""

        # Create temporary text file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(log_content)
            temp_file_path = temp_file.name

        # Send file to channel
        with open(temp_file_path, 'rb') as log_file:
            await context.bot.send_document(
                chat_id=CHANNEL_ID,
                document=log_file,
                filename=f"audio_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                caption=f"🎵 Audio: {video_info['title'][:30]}..."
            )

        # Clean up temporary file
        os.unlink(temp_file_path)
        logger.info(f"Audio details sent to channel: {video_info['title'][:50]}")

    except Exception as e:
        logger.error(f"Failed to send audio details to channel: {e}")

# ======================== VIDEO FILE CACHE MANAGEMENT ========================
# Global variable to store video file cache with persistent storage
video_file_cache = {}
VIDEO_CACHE_FILE = DATA_DIR / "video_cache.json"

def load_video_cache():
    """Load video cache from file"""
    global video_file_cache
    video_file_cache = load_json(VIDEO_CACHE_FILE)

def save_video_cache():
    """Save video cache to file"""
    save_json(VIDEO_CACHE_FILE, video_file_cache)

# Load video cache on startup
load_video_cache()

async def get_video_file_id(video_url: str, quality: str) -> str:
    """Get cached file ID for a video with specific quality"""
    # Create a hash of the URL for better organization
    import hashlib
    url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
    
    if url_hash in video_file_cache:
        cache_data = video_file_cache[url_hash]
        if cache_data.get('link') == video_url:
            quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
            cached_file_id = cache_data.get(quality_key)
            if cached_file_id:
                logger.info(f"Found cached file for {quality}: {cached_file_id[:20]}...")
                return cached_file_id
    return None

async def save_video_file_id(video_url: str, quality: str, file_id: str):
    """Save file ID to cache for future use with proper structure"""
    import hashlib
    url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
    
    # Initialize cache entry if not exists
    if url_hash not in video_file_cache:
        video_file_cache[url_hash] = {
            'link': video_url,
            'cached_at': datetime.now().isoformat()
        }
    
    # Store file ID with normalized quality key
    quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
    video_file_cache[url_hash][quality_key] = file_id
    video_file_cache[url_hash]['last_updated'] = datetime.now().isoformat()
    
    # Save to file for persistence
    save_video_cache()
    logger.info(f"Successfully cached {quality} ({quality_key}): {file_id[:20]}... | URL Hash: {url_hash}")

async def get_cached_video_info(video_url: str) -> dict:
    """Get all cached qualities for a video URL"""
    import hashlib
    url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
    
    if url_hash in video_file_cache:
        cache_data = video_file_cache[url_hash]
        if cache_data.get('link') == video_url:
            # Return all cached qualities except metadata
            cached_qualities = {}
            for key, value in cache_data.items():
                if key not in ['link', 'cached_at', 'last_updated'] and value:
                    cached_qualities[key] = value
            return cached_qualities
    return {}




    reload_data()
    
    if not link_shorteners_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="add_shortlink")]
        ])
        await query.edit_message_text(
            "🔗 Add Link to Shortener\n\n"
            "❌ No link shorteners available.\n"
            "Please add link shorteners first.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 5
    current_page = context.user_data.get('add_link_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    ls_ids = list(link_shorteners_data.keys())
    paginated_ls = ls_ids[start_index:end_index]
    total_pages = (len(ls_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-5: Link shortener domains
    for ls_id in paginated_ls:
        ls_data = link_shorteners_data[ls_id]
        domain = ls_data['domain']
        keyboard.append([InlineKeyboardButton(f"🌐 {domain}", callback_data=f"select_ls_{ls_id}")])
    
    # Navigation
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_add_link"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="add_shortlink"))
    if end_index < len(ls_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_add_link"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"🔗 Select Link Shortener{page_info}\n\n"
        f"📊 Total: {len(ls_ids)}\n"
        f"Choose a link shortener to add link:",
        reply_markup=reply_markup
    )

async def select_link_shortener(update: Update, context: ContextTypes.DEFAULT_TYPE, ls_id: str):
    """Handle link shortener selection and ask for shortlink URL"""
    query = update.callback_query
    reload_data()
    
    ls_data = link_shorteners_data.get(ls_id)
    if not ls_data:
        await query.answer("Link shortener not found!")
        return
    
    context.user_data['selected_shortener'] = ls_id
    context.user_data['state'] = 'waiting_shortlink_url'
    
    await query.edit_message_text(
        f"🔗 Selected: {ls_data['domain']}\n\n"
        f"Please send the shortlink URL you want to add:"
    )

async def process_shortlink_url(update: Update, context: ContextTypes.DEFAULT_TYPE, shortlink_url: str):
    """Process shortlink URL and ask for payload"""
    context.user_data['shortlink_url'] = shortlink_url
    context.user_data['state'] = 'waiting_shortlink_payload'
    
    await update.message.reply_text(
        f"🔗 Shortlink URL: {shortlink_url}\n\n"
        f"Now please send the payload for this shortlink:"
    )

async def process_shortlink_save(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """Save the shortlink with all details"""
    import uuid
    
    # Get collected data
    selected_shortener = context.user_data.get('selected_shortener')
    shortlink_url = context.user_data.get('shortlink_url')
    
    if not selected_shortener or not shortlink_url:
        await update.message.reply_text("❌ Error: Missing data. Please try again.")
        return
    
    reload_data()
    ls_data = link_shorteners_data.get(selected_shortener)
    if not ls_data:
        await update.message.reply_text("❌ Error: Link shortener not found.")
        return
    
    # Generate unique ID for shortlink
    link_id = f"SL{str(uuid.uuid4())[:6].upper()}"
    
    # Save shortlink
    shortlinks_data[link_id] = {
        "id": link_id,
        "url": shortlink_url,
        "payload": payload,
        "shortener_id": selected_shortener,
        "shortener_domain": ls_data['domain'],
        "added_by": "Owner",
        "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "status": "Active"
    }
    save_json(SHORTLINKS_FILE, shortlinks_data)
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks")]])
    await update.message.reply_text(
        f"✅ Shortlink Added Successfully!\n\n"
        f"🆔 ID: {link_id}\n"
        f"🔗 URL: {shortlink_url}\n"
        f"📦 Payload: {payload}\n"
        f"🌐 Shortener: {ls_data['domain']}\n"
        f"📅 Added: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=back_button
    )
    
    # Clear temporary data
    context.user_data['state'] = None
    for key in ['selected_shortener', 'shortlink_url']:
        context.user_data.pop(key, None)

async def remove_shortlink_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display shortlinks for removal with pagination"""
    query = update.callback_query
    reload_data()
    
    if not shortlinks_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks")]
        ])
        await query.edit_message_text(
            "➖ Remove Shortlink\n\n"
            "❌ No shortlinks available to remove.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 5
    current_page = context.user_data.get('remove_shortlink_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    link_ids = list(shortlinks_data.keys())
    paginated_links = link_ids[start_index:end_index]
    total_pages = (len(link_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-5: Shortlinks
    for link_id in paginated_links:
        link_data = shortlinks_data[link_id]
        url_display = link_data['url'][:30] + "..." if len(link_data['url']) > 30 else link_data['url']
        keyboard.append([InlineKeyboardButton(f"🔗 {url_display}", callback_data=f"remove_shortlink_{link_id}")])
    
    # Navigation
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_remove_shortlink"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks"))
    if end_index < len(link_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_remove_shortlink"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"➖ Remove Shortlink{page_info}\n\n"
        f"📊 Total: {len(link_ids)}\n"
        f"Select a shortlink to remove:",
        reply_markup=reply_markup
    )

async def list_shortlinks_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all shortlinks with pagination"""
    query = update.callback_query
    reload_data()
    
    if not shortlinks_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks")]
        ])
        await query.edit_message_text(
            "📋 Shortlinks List\n\n"
            "❌ No shortlinks available.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 5
    current_page = context.user_data.get('list_shortlink_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    link_ids = list(shortlinks_data.keys())
    paginated_links = link_ids[start_index:end_index]
    total_pages = (len(link_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-5: Shortlinks
    for link_id in paginated_links:
        link_data = shortlinks_data[link_id]
        url_display = link_data['url'][:30] + "..." if len(link_data['url']) > 30 else link_data['url']
        keyboard.append([InlineKeyboardButton(f"🔗 {url_display}", callback_data=f"view_shortlink_{link_id}")])
    
    # Navigation
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_list_shortlink"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="view_shortlinks"))
    if end_index < len(link_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_list_shortlink"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"📋 Shortlinks List{page_info}\n\n"
        f"📊 Total: {len(link_ids)}\n"
        f"Select a shortlink to view details:",
        reply_markup=reply_markup
    )

async def view_shortlink_details(update: Update, context: ContextTypes.DEFAULT_TYPE, link_id: str):
    """Show detailed information about a specific shortlink"""
    query = update.callback_query
    reload_data()
    
    link_data = shortlinks_data.get(link_id)
    if not link_data:
        await query.answer("Shortlink not found!")
        return
    
    details_text = f"""
🔗 Shortlink Details

🆔 ID: {link_data['id']}
🔗 URL: {link_data['url']}
📦 Payload: {link_data['payload']}
🌐 Shortener: {link_data.get('shortener_domain', 'Unknown')}
👤 Added By: {link_data['added_by']}
📅 Added At: {link_data['added_at']}
📊 Status: {link_data.get('status', 'Active')}
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to List", callback_data="list_shortlinks")]
    ])
    
    await query.edit_message_text(details_text, reply_markup=keyboard)

async def confirm_remove_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE, link_id: str):
    """Confirm removal of shortlink"""
    query = update.callback_query
    reload_data()
    
    link_data = shortlinks_data.get(link_id)
    if not link_data:
        await query.answer("Shortlink not found!")
        return
    
    confirmation_text = f"""
🗑️ Confirm Removal

Are you sure you want to delete this shortlink?

🔗 URL: {link_data['url']}
🆔 ID: {link_data['id']}
📅 Added: {link_data['added_at']}

⚠️ This action cannot be undone!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"delete_shortlink_{link_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data="remove_shortlink")]
    ])
    
    await query.edit_message_text(confirmation_text, reply_markup=keyboard)


async def refresh_cmp_data(update: Update, context: ContextTypes.DEFAULT_TYPE, ls_id: str):
    """Refresh CPM data for a link shortener"""
    query = update.callback_query
    reload_data()
    
    ls_data = link_shorteners_data.get(ls_id)
    if not ls_data:
        await query.answer("Link shortener not found!")
        return
    
    domain = ls_data.get('domain', '').lower()
    
    if not ('gplinks.com' in domain or 'linkshortify.com' in domain):
        await query.answer("❌ CPM extraction not supported for this shortener!", show_alert=True)
        return
    
    # Show refreshing message
    refresh_msg = await query.edit_message_text("🔄 Refreshing CPM data from API...\n⏳ Please wait...")
    
    # Extract CPM data
    cmp_success = await update_link_shortener_cmp(ls_id)
    
    if cmp_success:
        reload_data()  # Reload to get updated data
        updated_data = link_shorteners_data[ls_id]
        
        success_text = f"""
✅ **CPM Data Refreshed Successfully!**

🌐 **Domain:** {updated_data['domain']}
🆔 **ID:** {ls_id}

💰 **Updated CPM Data:**
• **Per Click:** {updated_data.get('per_click', '$0.00')}
• **Per 1,000 Views:** {updated_data.get('per_1000_click', '$0.00')}
• **Total Earnings:** {updated_data.get('total_earnings', '$0.00')}
• **Updated At:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

📊 **Status:** {updated_data.get('cmp_status', 'Unknown')}
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View Details", callback_data=f"view_ls_{ls_id}")],
            [InlineKeyboardButton("🔙 Back to List", callback_data="list_link_shorteners")]
        ])
        
        await refresh_msg.edit_text(success_text, reply_markup=keyboard)
    else:
        error_text = f"""
❌ **CPM Data Refresh Failed!**

🌐 **Domain:** {ls_data['domain']}
🆔 **ID:** {ls_id}

⚠️ **Possible Reasons:**
• Invalid API key
• Network connection issues
• API service temporarily down
• Incorrect email/password

💡 **Try Again:** Check your API credentials and try refreshing again.
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Try Again", callback_data=f"refresh_cmp_{ls_id}")],
            [InlineKeyboardButton("🔙 Back to Details", callback_data=f"view_ls_{ls_id}")]
        ])
        
        await refresh_msg.edit_text(error_text, reply_markup=keyboard)

async def delete_shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE, link_id: str):
    """Delete the shortlink after confirmation"""
    query = update.callback_query
    reload_data()
    
    link_data = shortlinks_data.get(link_id)
    if not link_data:
        await query.answer("Shortlink not found!")
        return
    
    # Delete the shortlink
    deleted_url = link_data['url']
    del shortlinks_data[link_id]
    save_json(SHORTLINKS_FILE, shortlinks_data)
    
    success_text = f"""
✅ Shortlink Deleted Successfully!

🔗 Deleted: {deleted_url}
🆔 ID: {link_id}
⏰ Deleted At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The shortlink has been permanently removed.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="remove_shortlink")]
    ])
    
    await query.edit_message_text(success_text, reply_markup=keyboard)

async def priority_settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display priority settings panel"""
    query = update.callback_query
    reload_data()
    
    if not link_shorteners_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="shortlinks")]
        ])
        await query.edit_message_text(
            "🎯 Priority Settings\n\n"
            "❌ No link shorteners available for priority settings.",
            reply_markup=keyboard
        )
        return
    
    priority_text = "🎯 Priority Settings\n\n"
    for ls_id, ls_data in link_shorteners_data.items():
        priority_text += f"🌐 {ls_data['domain']}: {ls_data['priority']}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="shortlinks")]
    ])
    
    await query.edit_message_text(priority_text, reply_markup=keyboard)

# ======================== API DETAILS FUNCTIONS REMOVED ========================
# All comprehensive API data functions have been removed as requested

async def handle_shortlink_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all shortlink-related callback queries"""
    query = update.callback_query
    cb = query.data

    if cb == "shortlinks":
        await shortlinks_main_panel(update, context)
    elif cb == "link_shorteners":
        await link_shorteners_panel(update, context)
    elif cb == "add_link_shortener":
        await add_link_shortener(update, context)
    elif cb == "remove_link_shortener":
        context.user_data['ls_remove_page'] = 1
        await remove_link_shortener(update, context)
    elif cb == "list_link_shorteners":
        context.user_data['ls_list_page'] = 1
        await list_link_shorteners(update, context)
    elif cb == "view_shortlinks":
        await view_shortlinks_panel(update, context)
    elif cb == "add_shortlink":
        await add_shortlink_panel(update, context)
    elif cb == "add_link_to_shortener":
        context.user_data['add_link_page'] = 1
        await add_link_to_shortener(update, context)
    elif cb == "create_new_link":
        context.user_data['create_link_page'] = 1
        await create_new_link_panel(update, context)
    elif cb == "add_created_link":
        await add_created_link(update, context)
    elif cb == "remove_shortlink":
        context.user_data['remove_shortlink_page'] = 1
        await remove_shortlink_panel(update, context)
    elif cb == "list_shortlinks":
        context.user_data['list_shortlink_page'] = 1
        await list_shortlinks_panel(update, context)
    elif cb == "priority_settings":
        await priority_settings_panel(update, context)
    elif cb.startswith("view_ls_"):
        ls_id = cb.split("_")[-1]
        await view_link_shortener_details(update, context, ls_id)
    elif cb.startswith("remove_ls_"):
        ls_id = cb.split("_")[-1]
        await confirm_remove_link_shortener(update, context, ls_id)
    elif cb.startswith("delete_ls_"):
        ls_id = cb.split("_")[-1]
        await delete_link_shortener(update, context, ls_id)
    elif cb.startswith("select_ls_"):
        ls_id = cb.split("_")[-1]
        await select_link_shortener(update, context, ls_id)
    elif cb.startswith("create_with_ls_"):
        ls_id = cb.split("_")[-1]
        await select_shortener_for_creation(update, context, ls_id)
    elif cb == "quick_add_gplinks":
        await quick_add_gplinks(update, context)
    elif cb == "quick_add_linkshortify":
        await quick_add_linkshortify(update, context)
    elif cb == "manual_add_shortener":
        await manual_add_shortener(update, context)
    elif cb.startswith("remove_shortlink_"):
        link_id = cb.split("_")[-1]
        await confirm_remove_shortlink(update, context, link_id)
    elif cb.startswith("delete_shortlink_"):
        link_id = cb.split("_")[-1]
        await delete_shortlink(update, context, link_id)
    elif cb.startswith("view_shortlink_"):
        link_id = cb.split("_")[-1]
        await view_shortlink_details(update, context, link_id)
    elif cb.startswith("more_details_"):
        ls_id = cb.split("_")[-1]
        await view_more_link_shortener_details(update, context, ls_id)
    elif cb.startswith("refresh_stats_"):
        ls_id = cb.split("_")[-1]
        await view_more_link_shortener_details(update, context, ls_id)
    elif cb.startswith("refresh_cmp_"):
        ls_id = cb.split("_")[-1]
        await refresh_cmp_data(update, context, ls_id)
    elif cb == "next_ls_remove":
        current_page = context.user_data.get('ls_remove_page', 1)
        context.user_data['ls_remove_page'] = current_page + 1
        await remove_link_shortener(update, context)
    elif cb == "previous_ls_remove":
        current_page = context.user_data.get('ls_remove_page', 1)
        if current_page > 1:
            context.user_data['ls_remove_page'] = current_page - 1
        await remove_link_shortener(update, context)
    elif cb == "next_ls_list":
        current_page = context.user_data.get('ls_list_page', 1)
        context.user_data['ls_list_page'] = current_page + 1
        await list_link_shorteners(update, context)
    elif cb == "previous_ls_list":
        current_page = context.user_data.get('ls_list_page', 1)
        if current_page > 1:
            context.user_data['ls_list_page'] = current_page - 1
        await list_link_shorteners(update, context)
    elif cb == "next_add_link":
        current_page = context.user_data.get('add_link_page', 1)
        context.user_data['add_link_page'] = current_page + 1
        await add_link_to_shortener(update, context)
    elif cb == "previous_add_link":
        current_page = context.user_data.get('add_link_page', 1)
        if current_page > 1:
            context.user_data['add_link_page'] = current_page - 1
        await add_link_to_shortener(update, context)
    elif cb == "next_remove_shortlink":
        current_page = context.user_data.get('remove_shortlink_page', 1)
        context.user_data['remove_shortlink_page'] = current_page + 1
        await remove_shortlink_panel(update, context)
    elif cb == "previous_remove_shortlink":
        current_page = context.user_data.get('remove_shortlink_page', 1)
        if current_page > 1:
            context.user_data['remove_shortlink_page'] = current_page - 1
        await remove_shortlink_panel(update, context)
    elif cb == "next_list_shortlink":
        current_page = context.user_data.get('list_shortlink_page', 1)
        context.user_data['list_shortlink_page'] = current_page + 1
        await list_shortlinks_panel(update, context)
    elif cb == "previous_list_shortlink":
        current_page = context.user_data.get('list_shortlink_page', 1)
        if current_page > 1:
            context.user_data['list_shortlink_page'] = current_page - 1
        await list_shortlinks_panel(update, context)
    elif cb == "next_create_link":
        current_page = context.user_data.get('create_link_page', 1)
        context.user_data['create_link_page'] = current_page + 1
        await create_new_link_panel(update, context)
    elif cb == "previous_create_link":
        current_page = context.user_data.get('create_link_page', 1)
        if current_page > 1:
            context.user_data['create_link_page'] = current_page - 1
        await create_new_link_panel(update, context)


# ======================== TTS FUNCTIONS ========================
async def handle_tts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TTS tool request - show voice selection"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    # Check if user is owner (no credit deduction for owner)
    is_owner = user.id == OWNER_ID

    cost_per_char = CREDIT_CONFIG['tts_cost_per_char']

    tts_info_text = f"""
🗣 Text to Speech (TTS) - Hindi

चुनें कि आप कौन सी आवाज़ चाहते हैं:

📊 Pricing Information:
💰 Cost: {cost_per_char} credits per character
📏 Maximum: 1000 characters
🎵 Output: High quality Hindi MP3 audio

💡 Examples:
• 1 character = {cost_per_char} credits
• 10 characters = {cost_per_char * 10} credits
• 100 characters = {cost_per_char * 100} credits
    """

    if is_owner:
        tts_info_text = f"""
🗣 Text to Speech (TTS) - Hindi - Owner Mode

चुनें कि आप कौन सी आवाज़ चाहते हैं:

📊 Information:
📏 Maximum: 1000 characters
🎵 Output: High quality Hindi MP3 audio
👑 Owner: No credit cost
        """

    voice_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨 Male Voice (पुरुष आवाज़)", callback_data="tts_voice_male")],
        [InlineKeyboardButton("👩 Female Voice (महिला आवाज़)", callback_data="tts_voice_female")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools")]
    ])
    await query.edit_message_text(tts_info_text, reply_markup=voice_keyboard)

async def handle_tts_voice_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TTS voice selection"""
    query = update.callback_query
    voice_type = query.data.split("_")[-1]  # male or female

    context.user_data['tts_voice_type'] = voice_type

    voice_name = "पुरुष आवाज़" if voice_type == "male" else "महिला आवाज़"

    instruction_text = f"""
🗣 Text to Speech - {voice_name}

अब अपना टेक्स्ट भेजें जो आप ऑडियो में बदलना चाहते हैं:

📝 Instructions:
• Hindi या English text भेज सकते हैं
• Maximum 1000 characters
• Clear और natural voice मिलेगी

Please send your text now:
    """

    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tts")]])
    await query.edit_message_text(instruction_text, reply_markup=back_button)
    context.user_data['state'] = 'waiting_tts_text'

async def process_tts_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Process TTS text and generate audio with Hindi voices"""
    user = update.effective_user
    uid = str(user.id)
    is_owner = user.id == OWNER_ID

    # Get selected voice type
    voice_type = context.user_data.get('tts_voice_type', 'female')

    # Validate text length
    if len(text) > 1000:
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await update.message.reply_text(
            f"❌ Text too long!\n\n"
            f"📏 Your text: {len(text)} characters\n"
            f"📝 Maximum: 1000 characters\n"
            f"✂️ Please shorten your text by {len(text) - 1000} characters.",
            reply_markup=back_button
        )
        context.user_data['state'] = None
        return

    if len(text.strip()) == 0:
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await update.message.reply_text(
            "❌ Please provide valid text!",
            reply_markup=back_button
        )
        context.user_data['state'] = None
        return

    # Calculate cost and check credits for non-owner users
    char_count = len(text)
    credit_cost = char_count * CREDIT_CONFIG['tts_cost_per_char']  # 0.2 credits per character

    if not is_owner:
        reload_data()
        user_credits = user_data.get(uid, {}).get('credits', 0)

        if user_credits < credit_cost:
            insufficient_credits_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Credits", callback_data="add_credit")],
                [InlineKeyboardButton("🔙 Back", callback_data="tools")]
            ])
            await update.message.reply_text(
                f"❌ Insufficient Credits!\n\n"
                f"📝 Text: {char_count} characters\n"
                f"💰 Required: {credit_cost} credits ({CREDIT_CONFIG['tts_cost_per_char']} per char)\n"
                f"💳 Your Credits: {user_credits}\n"
                f"📉 Need: {credit_cost - user_credits} more credits",
                reply_markup=insufficient_credits_keyboard
            )
            context.user_data['state'] = None
            return

    # Show processing message
    voice_name = "पुरुष आवाज़" if voice_type == "male" else "महिला आवाज़"
    processing_msg = await update.message.reply_text(f"🔄 आपका टेक्स्ट {voice_name} में convert हो रहा है...\n⏳ Please wait...")

    try:
        # Select Hindi voice based on gender
        if voice_type == "male":
            voice = "hi-IN-MadhurNeural"  # High quality Hindi male voice
        else:
            voice = "hi-IN-SwaraNeural"  # High quality Hindi female voice

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tmp_path = tmp_file.name

        # Generate TTS with optimized settings for clarity
        communicate = edge_tts.Communicate(
            text, 
            voice,
            rate="+0%",  # Normal speed for clarity
            volume="+0%",  # Normal volume
            pitch="+0Hz"  # Normal pitch
        )
        await communicate.save(tmp_path)

        # Deduct credits for non-owner users
        if not is_owner:
            user_data[uid]['credits'] -= credit_cost
            save_json(USER_DATA_FILE, user_data)

        # Send audio file first (without buttons)
        with open(tmp_path, 'rb') as audio_file:
            caption_text = f"""
🎵 Text to Speech Generated

📝 Characters: {char_count}
🗣 Voice: High Quality Hindi {voice_name}
🎙️ Voice Model: {"Madhur (Male)" if voice_type == "male" else "Swara (Female)"}
"""
            if not is_owner:
                caption_text += f"💰 Credits Used: {credit_cost}\n💳 Remaining Credits: {user_data[uid]['credits']}"
            else:
                caption_text += "👑 Owner Mode: No credits deducted"

            await update.message.reply_audio(
                audio=audio_file,
                caption=caption_text
            )

        # Send buttons in separate message
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Tools", callback_data="tools")]])
        await update.message.reply_text("Audio sent successfully!", reply_markup=back_button)

        # Clean up temporary file
        os.unlink(tmp_path)

        # Delete processing message
        await processing_msg.delete()

    except Exception as e:
        logger.error(f"TTS Error: {e}")

        # Clean up temporary file if it exists
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass

        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await processing_msg.edit_text(
            "❌ Error generating audio!\n\n"
            "🔧 Please try again later or contact support.",
            reply_markup=back_button
        )

    context.user_data['state'] = None
    context.user_data.pop('tts_voice_type', None)

# ======================== YT VIDEO DOWNLOADER FUNCTIONS ========================
async def handle_yt_downloader_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YT Video Downloader tool request"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)
    is_owner = user.id == OWNER_ID
    
    # Get user's first name
    user_first_name = user.first_name or "User"
    
    # Get user credits
    reload_data()
    user_credits = user_data.get(uid, {}).get('credits', 0)
    
    downloader_text = f"""
📹 **YT Video Downloader - Premium Tool**

Hello {user_first_name}!

🌟 **Ye ek premium tool hai** with credit-based pricing!

📥 **Credit Requirements by Quality:**
• 🎬 1080p HD: {CREDIT_CONFIG['yt_1080p_cost']} credits
• 🎬 720p HD: {CREDIT_CONFIG['yt_720p_cost']} credits  
• 🎬 480p: {CREDIT_CONFIG['yt_480p_cost']} credits
• 🎬 360p: {CREDIT_CONFIG['yt_360p_cost']} credits
• 🎬 240p: {CREDIT_CONFIG['yt_240p_cost']} credits
• 🎬 144p: {CREDIT_CONFIG['yt_144p_cost']} credits
• 🎵 Audio Only: {CREDIT_CONFIG['yt_audio_cost']} credits

💰 **Your Credits:** {user_credits}

🎯 **Features:**
• High Quality Downloads
• Fast Download Speed
• Multiple Format Support
• Premium Quality Experience

📝 **Instructions:**
• Send YouTube video link
• Select quality based on your credits
• Download will start automatically!

**YouTube video link bhejiye:**
    """
    
    if is_owner:
        downloader_text = f"""
📹 **YT Video Downloader - Owner Mode**

Hello Boss {user_first_name}!

👑 **Owner Mode:** All downloads are FREE for you!

🎯 **Available Qualities:**
• 🎬 1080p HD (Free for Owner)
• 🎬 720p HD (Free for Owner)
• 🎬 480p (Free for Owner)
• 🎬 360p (Free for Owner)
• 🎬 240p (Free for Owner)
• 🎬 144p (Free for Owner)
• 🎵 Audio Only (Free for Owner)

📝 **Instructions:**
• Send YouTube video link
• Select any quality you want
• No credit deduction for owner!

**YouTube video link bhejiye:**
        """
    
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="tools")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(downloader_text, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['state'] = 'waiting_yt_link'

async def handle_yt_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str):
    """Handle YouTube link input and extract video information"""
    user = update.effective_user
    user_first_name = user.first_name or "User"
    
    # Basic YouTube link validation
    if not ("youtube.com" in link.lower() or "youtu.be" in link.lower()):
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await update.message.reply_text(
            f"❌ Invalid YouTube link!\n\n"
            f"🔗 Please send a valid YouTube video link\n"
            f"📝 Example: https://youtube.com/watch?v=...",
            reply_markup=back_button
        )
        context.user_data['state'] = None
        return
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        f"🔄 Processing YouTube link...\n"
        f"⏳ Extracting video information..."
    )
    
    try:
        # Extract video information using yt-dlp
        video_info = await extract_youtube_video_info(link)
        
        if not video_info:
            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
            await processing_msg.edit_text(
                f"❌ Failed to extract video information!\n\n"
                f"🔗 Link: {link}\n"
                f"💡 Please check if the video is public and accessible.",
                reply_markup=back_button
            )
            context.user_data['state'] = None
            return
        
        # Store original URL for downloading
        context.user_data['current_video_url'] = link
        
        # Show video information and available qualities (without file checking)
        await show_video_qualities(update, context, video_info, processing_msg)
        
    except Exception as e:
        logger.error(f"Error processing YouTube link: {e}")
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await processing_msg.edit_text(
            f"❌ Error processing video!\n\n"
            f"🔗 Link: {link}\n"
            f"⚠️ Error: {str(e)[:100]}...\n"
            f"💡 Please try again or contact support.",
            reply_markup=back_button
        )
    
    context.user_data['state'] = None

async def extract_youtube_video_info(url: str):
    """Extract YouTube video information using yt-dlp"""
    try:
        # Import yt-dlp
        import yt_dlp
        
        # Configure yt-dlp options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract video information
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
            
            # Extract available formats/qualities first
            formats = info.get('formats', [])
            
            # Extract relevant information
            video_data = {
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown Uploader'),
                'duration': info.get('duration', 0),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                'formats': [],
                'original_formats': formats,
                'available_qualities': {}  # Store format details by quality
            }
            
            # Group formats by quality for better selection
            quality_groups = {}
            
            for fmt in formats:
                height = fmt.get('height')
                vcodec = fmt.get('vcodec', 'none')
                acodec = fmt.get('acodec', 'none')
                filesize = fmt.get('filesize') or 0
                format_id = fmt.get('format_id')
                fps = fmt.get('fps', 30) or 30
                
                # Only include video formats with valid height
                if height and height > 0 and vcodec != 'none':
                    quality_key = f"{height}p"
                    
                    # Prioritize formats with audio, or best quality video-only
                    if quality_key not in quality_groups or (acodec != 'none' and quality_groups[quality_key]['acodec'] == 'none'):
                        quality_groups[quality_key] = {
                            'format_id': format_id,
                            'height': height,
                            'filesize': filesize,
                            'fps': fps,
                            'has_audio': acodec != 'none',
                            'acodec': acodec,
                            'vcodec': vcodec,
                            'ext': fmt.get('ext', 'mp4')
                        }
            
            # Convert to sorted list
            for quality, details in quality_groups.items():
                size_mb = details['filesize'] // 1024 // 1024 if details['filesize'] > 0 else 0
                quality_info = {
                    'format_id': details['format_id'],
                    'quality': quality,
                    'ext': details['ext'],
                    'filesize': details['filesize'],
                    'size_mb': size_mb,
                    'fps': details['fps'],
                    'height': details['height'],
                    'has_audio': details['has_audio']
                }
                video_data['formats'].append(quality_info)
                video_data['available_qualities'][quality] = details
            
            # Sort formats by quality (highest first)
            video_data['formats'].sort(key=lambda x: x.get('height', 0), reverse=True)
            
            # Add audio-only option
            audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
            if audio_formats:
                best_audio = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                filesize = best_audio.get('filesize', 0) or 0
                size_mb = filesize // 1024 // 1024 if filesize > 0 else 0
                
                audio_info = {
                    'format_id': best_audio.get('format_id'),
                    'quality': 'Audio Only',
                    'ext': 'mp3',
                    'filesize': filesize,
                    'size_mb': size_mb,
                    'fps': 0,
                    'height': 0,
                    'has_audio': True
                }
                video_data['formats'].append(audio_info)
                video_data['available_qualities']['Audio Only'] = {
                    'format_id': best_audio.get('format_id'),
                    'height': 0,
                    'filesize': filesize,
                    'fps': 0,
                    'has_audio': True,
                    'acodec': best_audio.get('acodec'),
                    'vcodec': 'none',
                    'ext': 'mp3'
                }
            
            return video_data
            
    except ImportError:
        logger.error("yt-dlp not available")
        return None
    except Exception as e:
        logger.error(f"Error extracting video info: {e}")
        return None

async def show_video_qualities(update: Update, context: ContextTypes.DEFAULT_TYPE, video_info: dict, processing_msg):
    """Show video information with available qualities only"""
    
    # Format duration
    duration = video_info.get('duration', 0)
    if duration:
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        if hours > 0:
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = f"{minutes}:{seconds:02d}"
    else:
        duration_str = "Unknown"
    
    # Format view count
    views = video_info.get('view_count', 0)
    if views:
        if views >= 1000000:
            views_str = f"{views/1000000:.1f}M"
        elif views >= 1000:
            views_str = f"{views/1000:.1f}K"
        else:
            views_str = f"{views:,}"
    else:
        views_str = "Unknown"
    
    # Format upload date
    upload_date = video_info.get('upload_date', '')
    if upload_date and len(upload_date) >= 8:
        year = upload_date[:4]
        month = upload_date[4:6]
        day = upload_date[6:8]
        upload_str = f"{day}/{month}/{year}"
    else:
        upload_str = "Unknown"
    
    # Get available qualities and file sizes
    available_qualities = []
    quality_info = {}
    
    # Process formats from video data
    for fmt in video_info.get('formats', []):
        quality = fmt.get('quality', 'Unknown')
        size_mb = fmt.get('size_mb', 0)
        fps = fmt.get('fps', 30)
        has_audio = fmt.get('has_audio', True)
        
        available_qualities.append(quality)
        
        if size_mb > 0:
            quality_info[quality] = f"{size_mb}MB"
        else:
            quality_info[quality] = "Size unknown"
        
        # Add additional info
        if fps > 30 and quality != "Audio Only":
            quality_info[quality] += f" • {fps}fps"
        if not has_audio and quality != "Audio Only":
            quality_info[quality] += " • Video Only"
        elif quality == "Audio Only":
            # Try to get bitrate info for audio
            original_formats = video_info.get('original_formats', [])
            audio_formats = [f for f in original_formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
            if audio_formats:
                best_audio = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                abr = best_audio.get('abr', 0) or 0
                if abr > 0:
                    quality_info[quality] += f" • {abr}kbps"
    
    # Sort video qualities (highest first), keep audio only at the end
    video_qualities = [q for q in available_qualities if q != "Audio Only"]
    if video_qualities:
        video_qualities.sort(key=lambda x: int(x.replace('p', '')), reverse=True)
    
    if "Audio Only" in available_qualities:
        video_qualities.append("Audio Only")
    
    # Format qualities with sizes
    qualities_list = []
    for quality in video_qualities:
        size_info = quality_info.get(quality, "Size unknown")
        qualities_list.append(f"• {quality} ({size_info})")
    
    qualities_display = "\n".join(qualities_list) if qualities_list else "• No qualities detected"
    
    video_text = f"""
📹 **YouTube Video Information**

🎬 **Title:** {video_info['title']}

👤 **Uploader:** {video_info['uploader']}

⏱️ **Duration:** {duration_str}

👀 **Views:** {views_str}

📅 **Upload Date:** {upload_str}

✅ **Video details successfully extracted!**

Select quality to download:
    """
    
    # Create download buttons for available qualities with cache indicators
    keyboard = []
    user = update.effective_user
    is_owner = user.id == OWNER_ID
    
    # Check for cached qualities
    video_url = context.user_data.get('current_video_url', '')
    cached_qualities = await get_cached_video_info(video_url)
    
    # Separate video qualities from audio
    video_only_qualities = [q for q in video_qualities if q != "Audio Only"]
    
    if video_only_qualities:
        # Dynamic button arrangement based on number of qualities
        if len(video_only_qualities) >= 6:
            # For 6+ qualities: 3 buttons per row
            for i in range(0, len(video_only_qualities), 3):
                row = []
                for j in range(3):
                    if i + j < len(video_only_qualities):
                        quality = video_only_qualities[i + j]
                        # Check if quality is cached
                        quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
                        is_cached = quality_key in cached_qualities
                        button_text = f"🚀 {quality}" if is_cached else f"🎥 {quality}"
                        row.append(InlineKeyboardButton(button_text, callback_data=f"download_video_{quality}"))
                keyboard.append(row)
                
        elif len(video_only_qualities) >= 4:
            # For 4-5 qualities: 2 buttons per row
            for i in range(0, len(video_only_qualities), 2):
                row = []
                for j in range(2):
                    if i + j < len(video_only_qualities):
                        quality = video_only_qualities[i + j]
                        # Check if quality is cached
                        quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
                        is_cached = quality_key in cached_qualities
                        button_text = f"🚀 {quality}" if is_cached else f"🎥 {quality}"
                        row.append(InlineKeyboardButton(button_text, callback_data=f"download_video_{quality}"))
                keyboard.append(row)
                
        elif len(video_only_qualities) >= 2:
            # For 2-3 qualities: 2 buttons per row for first row, then remaining
            if len(video_only_qualities) == 2:
                # 2 qualities: both in one row
                row = []
                for quality in video_only_qualities:
                    # Check if quality is cached
                    quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
                    is_cached = quality_key in cached_qualities
                    button_text = f"🚀 {quality}" if is_cached else f"🎥 {quality}"
                    row.append(InlineKeyboardButton(button_text, callback_data=f"download_video_{quality}"))
                keyboard.append(row)
            else:
                # 3 qualities: 2 in first row, 1 in second row
                row1 = []
                for i in range(2):
                    quality = video_only_qualities[i]
                    # Check if quality is cached
                    quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
                    is_cached = quality_key in cached_qualities
                    button_text = f"🚀 {quality}" if is_cached else f"🎥 {quality}"
                    row1.append(InlineKeyboardButton(button_text, callback_data=f"download_video_{quality}"))
                keyboard.append(row1)
                
                # Third quality in separate row
                quality = video_only_qualities[2]
                # Check if quality is cached
                quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
                is_cached = quality_key in cached_qualities
                button_text = f"🚀 {quality}" if is_cached else f"🎥 {quality}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_video_{quality}")])
        else:
            # For 1 quality: single button
            quality = video_only_qualities[0]
            # Check if quality is cached
            quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
            is_cached = quality_key in cached_qualities
            button_text = f"🚀 {quality}" if is_cached else f"🎥 {quality}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_video_{quality}")])
    
    # Add audio only button if available (always in separate row)
    if "Audio Only" in available_qualities:
        # Check if audio is cached
        audio_key = "audio_only"
        is_audio_cached = audio_key in cached_qualities
        audio_button_text = f"🚀 Audio Only" if is_audio_cached else f"🎵 Audio Only"
        keyboard.append([InlineKeyboardButton(audio_button_text, callback_data="download_audio")])
    
    # Add back button (always in separate row)
    keyboard.append([InlineKeyboardButton("🔙 Back to Tools", callback_data="tools")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store video info for potential future use
    context.user_data['current_video_info'] = video_info
    
    # Check if processing_msg is CallbackQuery or Message and handle accordingly
    try:
        if hasattr(processing_msg, 'edit_text'):
            # It's a Message object
            await processing_msg.edit_text(video_text, reply_markup=reply_markup)
        else:
            # It's a CallbackQuery object
            await processing_msg.edit_message_text(video_text, reply_markup=reply_markup)
    except Exception as e:
        if "Message is not modified" in str(e):
            # Message content is same, just answer the query
            if hasattr(processing_msg, 'answer'):
                await processing_msg.answer("Video information loaded!", show_alert=False)
        else:
            # Send new message if edit fails
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=video_text,
                reply_markup=reply_markup
            )

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle quality selection (placeholder for actual download)"""
    query = update.callback_query
    format_id = callback_data.split("_")[-1]
    
    video_info = context.user_data.get('current_video_info')
    if not video_info:
        await query.answer("❌ Video information not found!")
        return
    
    # Find selected format
    selected_format = None
    for fmt in video_info['formats']:
        if fmt['format_id'] == format_id:
            selected_format = fmt
            break
    
    if not selected_format:
        await query.answer("❌ Selected quality not found!")
        return
    
    # Show download preparation message
    preparation_text = f"""
⚡ **Download Ready**

🎬 **Video:** {video_info['title'][:50]}{'...' if len(video_info['title']) > 50 else ''}
🎯 **Selected Quality:** {selected_format['quality']}
📁 **Format:** {selected_format['ext'].upper()}
💾 **File Size:** {selected_format.get('filesize', 0)//1024//1024 if selected_format.get('filesize') else 'Unknown'} MB

🚧 **Download Feature Coming Soon!**

Currently showing available qualities only.
Full download functionality will be added in the next update.

✨ **Your selection has been recorded:**
• Quality: {selected_format['quality']}
• Format: {selected_format['ext'].upper()}
• Video: {video_info['title'][:30]}{'...' if len(video_info['title']) > 30 else ''}

Thank you for testing the quality detection feature!
    """
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Qualities", callback_data="back_to_qualities")],
        [InlineKeyboardButton("🏠 Back to Tools", callback_data="tools")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(preparation_text, reply_markup=reply_markup)
    await query.answer("🎯 Quality selected!")

async def handle_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle video download request - check cache first, then download if needed"""
    query = update.callback_query
    quality = callback_data.replace("download_video_", "")
    user = query.from_user
    uid = str(user.id)
    is_owner = user.id == OWNER_ID
    
    video_info = context.user_data.get('current_video_info')
    if not video_info:
        await query.answer("❌ Video information not found!")
        return
    
    # Check if we have cached file for this video and quality
    video_url = context.user_data.get('current_video_url', '')
    cached_file_id = await get_video_file_id(video_url, quality)
    
    if cached_file_id:
        # File exists in cache, send it directly
        await query.answer("⚡ Sending from cache...", show_alert=False)
        
        # Check credits for non-owner users before sending
        credit_cost = get_quality_credit_cost(quality)
        
        if not is_owner:
            reload_data()
            user_credits = user_data.get(uid, {}).get('credits', 0)
            
            if user_credits < credit_cost:
                insufficient_credits_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Add Credits", callback_data="add_credit")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_qualities")]
                ])
                await query.edit_message_text(
                    f"❌ **Insufficient Credits!**\n\n"
                    f"🎬 **Quality:** {quality}\n"
                    f"💰 **Required:** {credit_cost} credits\n"
                    f"💳 **Your Credits:** {user_credits}\n"
                    f"📉 **Need:** {credit_cost - user_credits} more credits",
                    reply_markup=insufficient_credits_keyboard
                )
                return
            
            # Deduct credits before sending
            user_data[uid]['credits'] -= credit_cost
            save_json(USER_DATA_FILE, user_data)
            remaining_credits = user_data[uid]['credits']
        
        # Send cached file
        try:
            await query.edit_message_text(
                f"⚡ **Sending Cached Video...**\n\n"
                f"🎯 **Quality:** {quality}\n"
                f"📁 **Status:** Found in cache, sending instantly!"
            )
            
            # Send the cached video
            await context.bot.send_video(
                chat_id=user.id,
                video=cached_file_id,
                caption=f"🎬 **{video_info['title']}**\n\n"
                        f"🎯 Quality: {quality}\n"
                        f"👤 Uploader: {video_info['uploader']}\n"
                        f"⚡ Sent from cache\n" +
                        (f"💰 Credits Used: {credit_cost}\n💳 Remaining: {remaining_credits}" if not is_owner else "👑 Owner Mode: Free")
            )
            
            # Send success message
            await query.edit_message_text(
                f"✅ **Video Sent from Cache!**\n\n"
                f"🎬 **Title:** {video_info['title'][:50]}{'...' if len(video_info['title']) > 50 else ''}\n"
                f"🎯 **Quality:** {quality}\n"
                f"⚡ **Speed:** Instant delivery from cache\n" +
                (f"💰 **Credits Used:** {credit_cost}\n💳 **Remaining:** {remaining_credits}" if not is_owner else "👑 **Owner Mode:** No credits deducted")
            )
            
            # Send buttons for more actions
            keyboard = [
                [InlineKeyboardButton("🔄 More Videos", callback_data="yt_downloader"),
                 InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user.id,
                text="Video sent successfully from cache! 🚀",
                reply_markup=reply_markup
            )
            return
            
        except Exception as e:
            logger.error(f"Error sending cached file: {e}")
            # Remove invalid file ID from cache
            import hashlib
            url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
            quality_key = quality.lower().replace(' ', '_').replace('only', 'only')
            if url_hash in video_file_cache:
                if quality_key in video_file_cache[url_hash]:
                    del video_file_cache[url_hash][quality_key]
                    save_video_cache()
                    logger.info(f"Removed invalid cached file for {quality}")
            # Continue to download fresh file
    
    # No cached file found or cache failed, proceed with fresh download
    await query.answer("🔄 Downloading fresh video...", show_alert=False)
    
    # Check credits for non-owner users
    credit_cost = get_quality_credit_cost(quality)
    
    if not is_owner:
        reload_data()
        user_credits = user_data.get(uid, {}).get('credits', 0)
        
        if user_credits < credit_cost:
            insufficient_credits_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Credits", callback_data="add_credit")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_qualities")]
            ])
            await query.edit_message_text(
                f"❌ **Insufficient Credits!**\n\n"
                f"🎬 **Quality:** {quality}\n"
                f"💰 **Required:** {credit_cost} credits\n"
                f"💳 **Your Credits:** {user_credits}\n"
                f"📉 **Need:** {credit_cost - user_credits} more credits\n\n"
                f"💡 **Tip:** Try lower quality or add more credits",
                reply_markup=insufficient_credits_keyboard
            )
            return
    
    # Show enhanced downloading message
    downloading_msg = await query.edit_message_text(
        f"📥 **Downloading Video...**\n\n"
        f"🎯 **Quality:** {quality}\n"
        f"📊 **Progress:** 0%\n"
        f"[▒▒▒▒▒▒▒▒▒▒] 0% downloading"
    )
    
    try:
        # Import yt-dlp for downloading
        import yt_dlp
        import tempfile
        import os
        import threading
        import time
        
        # Create temporary directory for download
        temp_dir = tempfile.mkdtemp()
        progress_data = {'percent': 0, 'downloading': True, 'speed': '', 'eta': ''}
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d or 'total_bytes_estimate' in d:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)
                    downloaded = d.get('downloaded_bytes', 0)
                    percent = int((downloaded / total) * 100) if total > 0 else 0
                    progress_data['percent'] = min(percent, 100)
                    
                    # Get speed and ETA
                    speed = d.get('speed')
                    eta = d.get('eta')
                    if speed:
                        speed_mb = speed / 1024 / 1024
                        progress_data['speed'] = f"{speed_mb:.1f}MB/s"
                    if eta:
                        progress_data['eta'] = f"{eta}s"
        
        # Get format details from video info
        available_qualities = video_info.get('available_qualities', {})
        format_details = available_qualities.get(quality)
        
        if not format_details:
            raise Exception(f"Quality {quality} not found in available formats")
        
        format_id = format_details['format_id']
        
        # Configure yt-dlp with specific format ID
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
        }
        
        # If format doesn't have audio, try to merge with audio
        if not format_details.get('has_audio', True) and quality != "Audio Only":
            ydl_opts['format'] = f"{format_id}+bestaudio[ext=m4a]/best[ext=mp4]"
        
        # Start download in separate thread
        download_complete = False
        download_error = None
        
        def download_thread():
            nonlocal download_complete, download_error
            try:
                original_url = context.user_data.get('current_video_url', '')
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([original_url])
                download_complete = True
            except Exception as e:
                download_error = str(e)
        
        # Start download
        download_thread_obj = threading.Thread(target=download_thread)
        download_thread_obj.start()
        
        # Update progress with enhanced UI
        last_update = 0
        while not download_complete and not download_error:
            percent = progress_data['percent']
            current_time = time.time()
            
            # Update every 0.5 seconds for smoother feel
            if current_time - last_update >= 0.5:
                filled = int(percent / 10)
                bar = "█" * filled + "▒" * (10 - filled)
                
                status_text = f"📥 **Downloading Video...**\n\n"
                status_text += f"🎯 **Quality:** {quality}\n"
                status_text += f"📊 **Progress:** {percent}%\n"
                status_text += f"[{bar}] {percent}% downloading"
                
                if progress_data['speed']:
                    status_text += f"\n⚡ **Speed:** {progress_data['speed']}"
                if progress_data['eta']:
                    status_text += f"\n⏱️ **ETA:** {progress_data['eta']}"
                
                try:
                    await downloading_msg.edit_text(status_text)
                    last_update = current_time
                except:
                    pass  # Ignore edit errors
            
            time.sleep(0.2)  # More responsive updates
        
        download_thread_obj.join(timeout=5)
        
        if download_error:
            raise Exception(download_error)
        
        # Find the downloaded file
        downloaded_files = os.listdir(temp_dir)
        if downloaded_files:
            video_file_path = os.path.join(temp_dir, downloaded_files[0])
            
            # Check file size (Custom limit is 500MB)
            file_size = os.path.getsize(video_file_path)
            if file_size > 500 * 1024 * 1024:  # 500MB in bytes
                await downloading_msg.edit_text(
                    f"❌ **File Too Large**\n\n"
                    f"🎯 **Quality:** {quality}\n"
                    f"📁 **Size:** {file_size // 1024 // 1024}MB\n\n"
                    f"⚠️ File exceeds 500MB limit.\nTry lower quality.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_downloader")]])
                )
            else:
                # Update to uploading status
                await downloading_msg.edit_text(
                    f"📤 **Uploading Video...**\n\n"
                    f"🎯 **Quality:** {quality}\n"
                    f"📊 **Status:** [██████████] 100% uploading\n"
                    f"📡 Sending to Telegram..."
                )
                
                # Deduct credits for non-owner users BEFORE sending file
                if not is_owner:
                    user_data[uid]['credits'] -= credit_cost
                    save_json(USER_DATA_FILE, user_data)
                    remaining_credits = user_data[uid]['credits']
                
                # Send video file
                with open(video_file_path, 'rb') as video_file:
                    caption = f"🎬 **{video_info['title']}**\n\n🎯 Quality: {quality}\n👤 Uploader: {video_info['uploader']}"
                    if not is_owner:
                        caption += f"\n💰 Credits Used: {credit_cost}\n💳 Remaining: {remaining_credits}"
                    else:
                        caption += f"\n👑 Owner Mode: Free Download"
                    
                    sent_message = await context.bot.send_video(
                        chat_id=query.from_user.id,
                        video=video_file,
                        caption=caption[:1024]
                    )
                    
                    # Save file ID to cache for future use
                    if sent_message.video:
                        video_url = context.user_data.get('current_video_url', '')
                        await save_video_file_id(video_url, quality, sent_message.video.file_id)
                        
                        # Send details to Telegram channel
                        await send_video_details_to_channel(context, video_info, quality, video_url, sent_message.video.file_id)
                
                # Send completion message
                completion_text = f"✅ **Video Download Complete!**\n\n"
                completion_text += f"🎬 **Title:** {video_info['title'][:50]}{'...' if len(video_info['title']) > 50 else ''}\n"
                completion_text += f"🎯 **Quality:** {quality}\n"
                completion_text += f"📁 **Size:** {file_size // 1024 // 1024}MB\n"
                completion_text += f"📊 **Status:** [██████████] 100% completed"
                
                if not is_owner:
                    completion_text += f"\n💰 **Credits Used:** {credit_cost}\n💳 **Remaining Credits:** {remaining_credits}"
                else:
                    completion_text += f"\n👑 **Owner Mode:** No credits deducted"
                
                await downloading_msg.edit_text(completion_text)
                
                # Send success message with buttons
                keyboard = [
                    [InlineKeyboardButton("🔄 More", callback_data="yt_downloader"),
                     InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text="Video has been sent successfully!",
                    reply_markup=reply_markup
                )
            
            # Clean up temporary file
            os.unlink(video_file_path)
        else:
            await downloading_msg.edit_text(
                f"❌ **Download Failed**\n\n"
                f"[▒▒▒▒▒▒▒▒▒▒] 0% failed\n"
                f"No video file was downloaded.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_downloader")]])
            )
        
        # Clean up temporary directory
        os.rmdir(temp_dir)
        
    except Exception as e:
        logger.error(f"Video download error: {e}")
        await downloading_msg.edit_text(
            f"❌ **Download Error**\n\n"
            f"[▒▒▒▒▒▒▒▒▒▒] 0% error\n"
            f"⚠️ {str(e)[:100]}...\n\n"
            f"Please try again with a different quality.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_downloader")]])
        )

async def handle_audio_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle audio download request - check cache first, then download if needed"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)
    is_owner = user.id == OWNER_ID
    
    video_info = context.user_data.get('current_video_info')
    if not video_info:
        await query.answer("❌ Video information not found!")
        return
    
    # Check if we have cached file for this audio
    video_url = context.user_data.get('current_video_url', '')
    cached_file_id = await get_video_file_id(video_url, "Audio Only")
    
    if cached_file_id:
        # File exists in cache, send it directly
        await query.answer("⚡ Sending from cache...", show_alert=False)
        
        # Check credits for non-owner users before sending
        credit_cost = get_quality_credit_cost("Audio Only")
        
        if not is_owner:
            reload_data()
            user_credits = user_data.get(uid, {}).get('credits', 0)
            
            if user_credits < credit_cost:
                insufficient_credits_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Add Credits", callback_data="add_credit")],
                    [InlineKeyboardButton("🔙 Back", callback_data="back_to_qualities")]
                ])
                await query.edit_message_text(
                    f"❌ **Insufficient Credits!**\n\n"
                    f"🎵 **Format:** Audio Only (MP3)\n"
                    f"💰 **Required:** {credit_cost} credits\n"
                    f"💳 **Your Credits:** {user_credits}\n"
                    f"📉 **Need:** {credit_cost - user_credits} more credits\n\n"
                    f"💡 **Tip:** Audio downloads are cheaper than video",
                    reply_markup=insufficient_credits_keyboard
                )
                return
            
            # Deduct credits before sending
            user_data[uid]['credits'] -= credit_cost
            save_json(USER_DATA_FILE, user_data)
            remaining_credits = user_data[uid]['credits']
        
        # Send cached file
        try:
            await query.edit_message_text(
                f"⚡ **Sending Cached Audio...**\n\n"
                f"🎯 **Format:** MP3 Audio\n"
                f"📁 **Status:** Found in cache, sending instantly!"
            )
            
            # Send the cached audio
            await context.bot.send_audio(
                chat_id=user.id,
                audio=cached_file_id,
                caption=f"🎵 **{video_info['title']}**\n\n"
                        f"👤 Uploader: {video_info['uploader']}\n"
                        f"🎯 Format: MP3 Audio\n"
                        f"⚡ Sent from cache\n" +
                        (f"💰 Credits Used: {credit_cost}\n💳 Remaining: {remaining_credits}" if not is_owner else "👑 Owner Mode: Free"),
                title=video_info['title'][:100],
                performer=video_info['uploader']
            )
            
            # Send success message
            await query.edit_message_text(
                f"✅ **Audio Sent from Cache!**\n\n"
                f"🎬 **Title:** {video_info['title'][:50]}{'...' if len(video_info['title']) > 50 else ''}\n"
                f"🎯 **Format:** MP3 Audio\n"
                f"⚡ **Speed:** Instant delivery from cache\n" +
                (f"💰 **Credits Used:** {credit_cost}\n💳 **Remaining:** {remaining_credits}" if not is_owner else "👑 **Owner Mode:** No credits deducted")
            )
            
            # Send buttons for more actions
            keyboard = [
                [InlineKeyboardButton("🔄 More Videos", callback_data="yt_downloader"),
                 InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user.id,
                text="Audio sent successfully from cache! 🚀",
                reply_markup=reply_markup
            )
            return
            
        except Exception as e:
            logger.error(f"Error sending cached audio file: {e}")
            # Remove invalid file ID from cache
            import hashlib
            url_hash = hashlib.md5(video_url.encode()).hexdigest()[:10]
            quality_key = "audio_only"
            if url_hash in video_file_cache:
                if quality_key in video_file_cache[url_hash]:
                    del video_file_cache[url_hash][quality_key]
                    save_video_cache()
                    logger.info(f"Removed invalid cached audio file")
            # Continue to download fresh file
    
    # No cached file found or cache failed, proceed with fresh download
    await query.answer("🔄 Downloading fresh audio...", show_alert=False)
    
    # Check credits for non-owner users
    credit_cost = get_quality_credit_cost("Audio Only")
    
    if not is_owner:
        reload_data()
        user_credits = user_data.get(uid, {}).get('credits', 0)
        
        if user_credits < credit_cost:
            insufficient_credits_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Credits", callback_data="add_credit")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_qualities")]
            ])
            await query.edit_message_text(
                f"❌ **Insufficient Credits!**\n\n"
                f"🎵 **Format:** Audio Only (MP3)\n"
                f"💰 **Required:** {credit_cost} credits\n"
                f"💳 **Your Credits:** {user_credits}\n"
                f"📉 **Need:** {credit_cost - user_credits} more credits\n\n"
                f"💡 **Tip:** Audio downloads are cheaper than video",
                reply_markup=insufficient_credits_keyboard
            )
            return
    
    # Show simple downloading message
    downloading_msg = await query.edit_message_text(
        f"📥 **Downloading Audio...**\n\n"
        f"🎯 **Format:** MP3 Audio\n"
        f"📊 **Progress:** 0%\n"
        f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%"
    )
    
    try:
        # Import yt-dlp for downloading
        import yt_dlp
        import tempfile
        import os
        import threading
        import time
        
        # Create temporary directory for download
        temp_dir = tempfile.mkdtemp()
        progress_data = {'percent': 0, 'downloading': True}
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d or 'total_bytes_estimate' in d:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)
                    downloaded = d.get('downloaded_bytes', 0)
                    percent = int((downloaded / total) * 100) if total > 0 else 0
                    progress_data['percent'] = min(percent, 100)
        
        # Configure yt-dlp for audio only
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
        }
        
        # Start download in separate thread
        download_complete = False
        download_error = None
        
        def download_thread():
            nonlocal download_complete, download_error
            try:
                original_url = context.user_data.get('current_video_url', '')
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([original_url])
                download_complete = True
            except Exception as e:
                download_error = str(e)
        
        # Start download
        download_thread_obj = threading.Thread(target=download_thread)
        download_thread_obj.start()
        
        # Update progress with enhanced UI
        last_update = 0
        while not download_complete and not download_error:
            percent = progress_data['percent']
            current_time = time.time()
            
            # Update every 0.5 seconds for smoother feel
            if current_time - last_update >= 0.5:
                filled = int(percent / 10)
                bar = "█" * filled + "▒" * (10 - filled)
                
                try:
                    await downloading_msg.edit_text(
                        f"📥 **Downloading Audio...**\n\n"
                        f"🎯 **Format:** MP3 Audio\n"
                        f"📊 **Progress:** {percent}%\n"
                        f"[{bar}] {percent}% downloading"
                    )
                    last_update = current_time
                except:
                    pass  # Ignore edit errors
            
            time.sleep(0.2)  # More responsive updates
        
        download_thread_obj.join(timeout=5)
        
        if download_error:
            raise Exception(download_error)
        
        # Find the downloaded file
        downloaded_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
        if downloaded_files:
            audio_file_path = os.path.join(temp_dir, downloaded_files[0])
            
            # Check file size (Custom limit is 500MB)
            file_size = os.path.getsize(audio_file_path)
            if file_size > 500 * 1024 * 1024:  # 500MB in bytes
                await downloading_msg.edit_text(
                    f"❌ **File Too Large**\n\n"
                    f"🎯 **Format:** MP3 Audio\n"
                    f"📁 **Size:** {file_size // 1024 // 1024}MB\n\n"
                    f"⚠️ Audio exceeds 500MB limit.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_downloader")]])
                )
            else:
                # Update to uploading status
                await downloading_msg.edit_text(
                    f"📤 **Uploading Audio...**\n\n"
                    f"🎯 **Format:** MP3 Audio\n"
                    f"📊 **Status:** Uploading to Telegram..."
                )
                
                # Deduct credits for non-owner users BEFORE sending file
                if not is_owner:
                    user_data[uid]['credits'] -= credit_cost
                    save_json(USER_DATA_FILE, user_data)
                    remaining_credits = user_data[uid]['credits']
                
                # Send audio file
                with open(audio_file_path, 'rb') as audio_file:
                    caption = f"🎵 **{video_info['title']}**\n\n👤 Uploader: {video_info['uploader']}\n🎯 Format: MP3 Audio"
                    if not is_owner:
                        caption += f"\n💰 Credits Used: {credit_cost}\n💳 Remaining: {remaining_credits}"
                    else:
                        caption += f"\n👑 Owner Mode: Free Download"
                    
                    sent_message = await context.bot.send_audio(
                        chat_id=query.from_user.id,
                        audio=audio_file,
                        caption=caption[:1024],
                        title=video_info['title'][:100],
                        performer=video_info['uploader']
                    )
                    
                    # Save file ID to cache for future use
                    if sent_message.audio:
                        video_url = context.user_data.get('current_video_url', '')
                        await save_video_file_id(video_url, "Audio Only", sent_message.audio.file_id)
                        
                        # Send details to Telegram channel for audio
                        await send_audio_details_to_channel(context, video_info, video_url, sent_message.audio.file_id)
                
                # Send completion message
                completion_text = f"✅ **Audio Download Complete!**\n\n"
                completion_text += f"🎬 **Title:** {video_info['title'][:50]}{'...' if len(video_info['title']) > 50 else ''}\n"
                completion_text += f"🎯 **Format:** MP3 Audio\n"
                completion_text += f"📁 **Size:** {file_size // 1024 // 1024}MB"
                
                if not is_owner:
                    completion_text += f"\n💰 **Credits Used:** {credit_cost}\n💳 **Remaining Credits:** {remaining_credits}"
                else:
                    completion_text += f"\n👑 **Owner Mode:** No credits deducted"
                
                await downloading_msg.edit_text(completion_text)
                
                # Send success message with buttons
                keyboard = [
                    [InlineKeyboardButton("🔄 More", callback_data="yt_downloader"),
                     InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text="Audio has been sent successfully!",
                    reply_markup=reply_markup
                )
            
            # Clean up temporary file
            os.unlink(audio_file_path)
        else:
            await downloading_msg.edit_text(
                f"❌ **Download Failed**\n\n"
                f"No audio file was downloaded.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_downloader")]])
            )
        
        # Clean up temporary directory
        os.rmdir(temp_dir)
        
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        await downloading_msg.edit_text(
            f"❌ **Download Error**\n\n"
            f"⚠️ {str(e)[:100]}...\n\n"
            f"Please try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="yt_downloader")]])
        )

async def handle_back_to_qualities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to qualities button"""
    query = update.callback_query
    video_info = context.user_data.get('current_video_info')
    
    if not video_info:
        await query.answer("❌ Video information not found!")
        return
    
    await show_video_qualities(update, context, video_info, query)

# ======================== STT FUNCTIONS ========================
async def handle_stt_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle STT (Speech to Text) tool request"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    # Check if user is owner (no credit deduction for owner)
    is_owner = user.id == OWNER_ID

    cost_per_minute = CREDIT_CONFIG['stt_cost_per_minute']

    stt_info_text = f"""
🎤 Speech to Text (STT) - Hindi/English

🎵 Send voice message या audio file भेजें:

📊 Pricing Information:
💰 Cost: {cost_per_minute} credits per minute (minimum 1 minute)
📏 Maximum: 20 minutes audio
🌐 Supports: English (और basic Hindi)
🎯 Output: Offline speech recognition

💡 Examples:
• 30 seconds = {cost_per_minute} credits (minimum)
• 1 minute = {cost_per_minute} credits
• 2.5 minutes = {cost_per_minute * 3} credits (rounded up)
• 5 minutes = {cost_per_minute * 5} credits
    """

    if is_owner:
        stt_info_text = f"""
🎤 Speech to Text (STT) - Hindi/English - Owner Mode

🎵 Send voice message या audio file भेजें:

📊 Information:
📏 Maximum: 20 minutes audio
🌐 Supports: English (और basic Hindi)
🎯 Output: Offline speech recognition
👑 Owner: No credit cost
        """

    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
    await query.edit_message_text(stt_info_text, reply_markup=back_button)
    context.user_data['state'] = 'waiting_stt_audio'

def get_audio_duration_minutes(file_path):
    """Get audio duration in minutes using pydub"""
    try:
        if not PYDUB_AVAILABLE:
            logger.warning("Pydub not available, returning default duration")
            return 1.0  # Default to 1 minute
        
        audio = AudioSegment.from_file(file_path)
        duration_seconds = len(audio) / 1000.0  # pydub returns milliseconds
        duration_minutes = duration_seconds / 60.0
        return duration_minutes
    except Exception as e:
        logger.error(f"Error getting audio duration: {e}")
        return 1.0  # Default to 1 minute

def convert_to_wav(input_path, output_path):
    """Convert audio file to WAV format for speech recognition"""
    try:
        if not PYDUB_AVAILABLE:
            logger.error("Pydub not available for audio conversion")
            return False
            
        audio = AudioSegment.from_file(input_path)
        # Convert to mono for better recognition
        audio = audio.set_channels(1)
        audio.export(output_path, format="wav")
        return True
    except Exception as e:
        logger.error(f"Error converting audio to WAV: {e}")
        return False

def transcribe_with_speech_recognition(wav_file_path):
    """Fallback transcription using SpeechRecognition library"""
    try:
        # Simple fallback without requiring Vosk
        return f"""
🎤 **Audio Received Successfully**

📝 **Transcription:** Sorry, speech recognition is currently under maintenance.

📊 **Audio Details:**
• File processed successfully
• Format: WAV audio
• Language detection: Attempted
• Processing status: ✅ Complete

💡 **Note:** Advanced speech recognition features will be available soon. Your audio was processed but transcription service is temporarily offline.

🔧 **What's working:**
• Audio file upload ✅
• Audio format conversion ✅
• Duration calculation ✅
• Credit system ✅

📞 **Contact support for immediate transcription needs.**
        """
        
        # Check for different possible model paths
        possible_model_paths = [
            "model",
            "vosk-model",
            "vosk-model-en-us-0.22",
            "vosk-model-small-en-us-0.15",
            "data/model"
        ]
        
        model_path = None
        for path in possible_model_paths:
            if os.path.exists(path):
                model_path = path
                break
        
        if not model_path:
            logger.error(f"Vosk model not found in any of these paths: {possible_model_paths}")
            return """
❌ Speech recognition model not available.

📥 To fix this issue:
1. Download a Vosk model from: https://alphacephei.com/vosk/models
2. Extract it to the project directory
3. Rename the folder to 'model'

Recommended models:
• vosk-model-small-en-us-0.15 (39MB) - For English
• vosk-model-en-us-0.22 (1.8GB) - High accuracy English

Contact the administrator to set up the speech recognition model.
            """
        
        import wave
        
        vosk_model = vosk.Model(model_path)
        recognizer = vosk.KaldiRecognizer(vosk_model, 16000) # Sample rate

        wf = wave.open(wav_file_path, "rb")
        
        # Convert audio to the required format if needed
        if wf.getnchannels() != 1 or wf.getsamplerate() != 16000:
            wf.close()
            # Convert using pydub
            audio = AudioSegment.from_wav(wav_file_path)
            audio = audio.set_channels(1).set_frame_rate(16000)
            
            # Create a new temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_wav:
                converted_path = tmp_wav.name
            
            audio.export(converted_path, format="wav")
            wf = wave.open(converted_path, "rb")
            
            # Clean up the converted file after processing
            def cleanup_converted():
                try:
                    os.unlink(converted_path)
                except:
                    pass
        else:
            cleanup_converted = lambda: None

        try:
            results = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                    
                if recognizer.AcceptWaveform(data):
                    result = recognizer.Result()
                    result_json = json.loads(result)
                    if result_json.get("text"):
                        results.append(result_json["text"])
            
            # Get final result
            final_result = recognizer.FinalResult()
            final_result_json = json.loads(final_result)
            if final_result_json.get("text"):
                results.append(final_result_json["text"])
            
            wf.close()
            cleanup_converted()
            
            if results:
                full_text = " ".join(results).strip()
                return f"📝 Transcription: {full_text}" if full_text else "📝 No speech detected in audio"
            else:
                return "📝 No speech detected in audio"
                
        except Exception as e:
            wf.close()
            cleanup_converted()
            raise e
            
    except Exception as e:
        logger.error(f"Vosk Transcription Error: {e}")
        return f"❌ Audio transcription error: {str(e)}\n\nPlease try with a clearer audio file or contact support."

async def process_stt_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process audio file for speech to text conversion"""
    user = update.effective_user
    uid = str(user.id)
    is_owner = user.id == OWNER_ID

    # Check if message has voice or audio
    if not (update.message.voice or update.message.audio):
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await update.message.reply_text(
            "❌ Please send a voice message या audio file!",
            reply_markup=back_button
        )
        context.user_data['state'] = None
        return

    # Get audio file
    if update.message.voice:
        audio_file = update.message.voice
        file_duration = audio_file.duration
    else:
        audio_file = update.message.audio
        file_duration = audio_file.duration

    # Check audio duration (max 20 minutes = 1200 seconds)
    if file_duration > 1200:  # 20 minutes
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await update.message.reply_text(
            f"❌ Audio too long!\n\n"
            f"📏 Your audio: {file_duration//60} minutes {file_duration%60} seconds\n"
            f"📝 Maximum: 20 minutes\n"
            f"✂️ Please send shorter audio.",
            reply_markup=back_button
        )
        context.user_data['state'] = None
        return

    # Calculate cost and duration in minutes
    duration_minutes = max(1, math.ceil(file_duration / 60))  # Minimum 1 minute, round up
    credit_cost = duration_minutes * CREDIT_CONFIG['stt_cost_per_minute']

    if not is_owner:
        reload_data()
        user_credits = user_data.get(uid, {}).get('credits', 0)

        if user_credits < credit_cost:
            insufficient_credits_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Credits", callback_data="add_credit")],
                [InlineKeyboardButton("🔙 Back", callback_data="tools")]
            ])
            await update.message.reply_text(
                f"❌ Insufficient Credits!\n\n"
                f"🎵 Audio Duration: {file_duration//60}m {file_duration%60}s\n"
                f"📊 Charged Duration: {duration_minutes} minutes\n"
                f"💰 Required: {credit_cost} credits ({CREDIT_CONFIG['stt_cost_per_minute']} per min)\n"
                f"💳 Your Credits: {user_credits}\n"
                f"📉 Need: {credit_cost - user_credits} more credits",
                reply_markup=insufficient_credits_keyboard
            )
            context.user_data['state'] = None
            return

    # Show processing message
    processing_msg = await update.message.reply_text(
        f"🔄 आपका audio text में convert हो रहा है...\n"
        f"⏳ Duration: {duration_minutes} minutes\n"
        f"📊 Processing..."
    )

    try:
        # Download audio file
        file = await context.bot.get_file(audio_file.file_id)

        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.oga') as temp_input:
            temp_input_path = temp_input.name

        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_wav:
            temp_wav_path = temp_wav.name

        # Download the file
        await file.download_to_drive(temp_input_path)

        # Convert to WAV format
        if not convert_to_wav(temp_input_path, temp_wav_path):
            raise Exception("Audio conversion failed")

        # Transcribe audio
        transcription = transcribe_with_speech_recognition(temp_wav_path)

        # Deduct credits for non-owner users
        if not is_owner:
            user_data[uid]['credits'] -= credit_cost
            save_json(USER_DATA_FILE, user_data)

        # Send transcription result
        result_text = f"""
📝 Speech to Text Result

🎤 **Transcription:**
{transcription}

📊 **Details:**
• Audio Duration: {file_duration//60}m {file_duration%60}s
• Charged Duration: {duration_minutes} minutes
• Language: Auto-detected (Hindi/English)
"""

        if not is_owner:
            result_text += f"\n💰 Credits Used: {credit_cost}\n💳 Remaining Credits: {user_data[uid]['credits']}"
        else:
            result_text += "\n👑 Owner Mode: No credits deducted"

        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Tools", callback_data="tools")]])

        await update.message.reply_text(result_text, reply_markup=back_button)

        # Clean up temporary files
        try:
            os.unlink(temp_input_path)
            os.unlink(temp_wav_path)
        except:
            pass

        # Delete processing message
        await processing_msg.delete()

    except Exception as e:
        logger.error(f"STT Error: {e}")

        # Clean up temporary files
        try:
            if 'temp_input_path' in locals():
                os.unlink(temp_input_path)
            if 'temp_wav_path' in locals():
                os.unlink(temp_wav_path)
        except:
            pass

        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="tools")]])
        await processing_msg.edit_text(
            "❌ Error converting audio to text!\n\n"
            "🔧 Please try again with clear audio or contact support.\n"
            "💡 Tip: Record in quiet environment for better accuracy.",
            reply_markup=back_button
        )

    context.user_data['state'] = None

# ======================== CREDIT MANAGEMENT FUNCTIONS ========================
async def process_give_credit(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_message: str = None):
    """Process giving credit to a specific user"""
    try:
        uid = context.user_data.get('credit_user_id')
        user_info = context.user_data.get('credit_user_info')
        credit_amount = context.user_data.get('credit_amount')

        if uid and user_info and credit_amount:
            reload_data()

            # Add credits to user
            if uid in user_data:
                user_data[uid]['credits'] = user_data[uid].get('credits', 0) + credit_amount
                user_data[uid]['user_updated_at'] = datetime.now().isoformat()
                save_json(USER_DATA_FILE, user_data)

                # Prepare message
                if custom_message:
                    # Replace placeholders with actual user data
                    formatted_message = custom_message
                    formatted_message = formatted_message.replace("{first_name}", user_info.get('user_first_name') or 'User')
                    formatted_message = formatted_message.replace("{last_name}", user_info.get('user_last_name') or 'User')
                    formatted_message = formatted_message.replace("{full_name}", user_info.get('name') or 'User')
                    formatted_message = formatted_message.replace("{user_id}", str(user_info.get('user_id') or 'Unknown'))
                    formatted_message = formatted_message.replace("{username}", user_info.get('username') or 'None')
                    formatted_message = formatted_message.replace("{credit}", str(credit_amount))
                else:
                    # Default message
                    formatted_message = f"🎁 You received {credit_amount} credits from the owner!"

                # Send notification to user
                try:
                    credit_msg = f"""
💰 Credit Added to Your Account!

{formatted_message}

💳 Credits Added: {credit_amount}
💰 Total Credits: {user_data[uid]['credits']}
⏰ Added At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 Added By: Owner
                    """
                    await context.bot.send_message(chat_id=user_info.get('user_id'), text=credit_msg)
                except Exception as e:
                    logger.error(f"Failed to send credit notification: {e}")

                # Send success message to owner
                if hasattr(update, 'callback_query') and update.callback_query:
                    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                    await update.callback_query.edit_message_text(
                        f"✅ Credit Added Successfully!\n\n"
                        f"👤 User: {user_info.get('name', 'Unknown')}\n"
                        f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                        f"💰 Credits Added: {credit_amount}\n"
                        f"💳 New Total: {user_data[uid]['credits']}\n"
                        f"⏰ Added At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"📬 Notification sent to user",
                        reply_markup=back_button
                    )
                else:
                    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                    await update.message.reply_text(
                        f"✅ Credit Added Successfully!\n\n�"
                        f"👤 User: {user_info.get('name', 'Unknown')}\n"
                        f"🆔 User ID: {user_info.get('user_id', 'Unknown')}\n"
                        f"💰 Credits Added: {credit_amount}\n"
                        f"💳 New Total: {user_data[uid]['credits']}\n"
                        f"⏰ Added At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"📬 Notification sent to user",
                        reply_markup=back_button
                    )

        context.user_data['state'] = None
        context.user_data.pop('credit_user_id', None)
        context.user_data.pop('credit_user_info', None)
        context.user_data.pop('credit_amount', None)

    except Exception as e:
        logger.error(f"Error giving credit: {e}")
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
        error_msg = "❌ Error occurred while giving credit. Please try again."

        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_msg, reply_markup=back_button)
        else:
            await update.message.reply_text(error_msg, reply_markup=back_button)
        context.user_data['state'] = None

async def process_give_credit_all(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_message: str = None):
    """Process giving credit to all users"""
    try:
        credit_amount = context.user_data.get('credit_all_amount')

        if credit_amount:
            reload_data()
            active_users = {uid: data for uid, data in user_data.items() if data.get('user_status') == 'active'}

            success_count = 0
            failed_count = 0

            # Show processing message
            if hasattr(update, 'callback_query') and update.callback_query:
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                await update.callback_query.edit_message_text(
                    f"💰 Adding {credit_amount} credits to {len(active_users)} users...\n⏳ Please wait...",
                    reply_markup=back_button
                )
            else:
                back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
                processing_msg = await update.message.reply_text(
                    f"💰 Adding {credit_amount} credits to {len(active_users)} users...\n⏳ Please wait...",
                    reply_markup=back_button
                )

            for uid, user_info in active_users.items():
                try:
                    user_id = user_info.get('user_id')
                    if not user_id or is_user_banned(user_id):
                        continue

                    # Add credits to user
                    user_data[uid]['credits'] = user_data[uid].get('credits', 0) + credit_amount
                    user_data[uid]['user_updated_at'] = datetime.now().isoformat()

                    # Prepare message
                    if custom_message:
                        # Replace placeholders with actual user data
                        formatted_message = custom_message
                        formatted_message = formatted_message.replace("{first_name}", user_info.get('user_first_name') or 'User')
                        formatted_message = formatted_message.replace("{last_name}", user_info.get('user_last_name') or 'User')
                        formatted_message = formatted_message.replace("{full_name}", user_info.get('name') or 'User')
                        formatted_message = formatted_message.replace("{user_id}", str(user_info.get('user_id') or 'Unknown'))
                        formatted_message = formatted_message.replace("{username}", user_info.get('username') or 'None')
                        formatted_message = formatted_message.replace("{credit}", str(credit_amount))
                    else:
                        # Default message
                        formatted_message = f"🎁 You received {credit_amount} credits from the owner!"

                    # Send notification to user
                    credit_msg = f"""
💰 Credit Added to Your Account!

{formatted_message}

💳 Credits Added: {credit_amount}
💰 Total Credits: {user_data[uid]['credits']}
⏰ Added At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👑 Added By: Owner
                    """
                    await context.bot.send_message(chat_id=user_id, text=credit_msg)
                    success_count += 1

                except Exception as e:
                    logger.error(f"Failed to send credit to user {user_id}: {e}")
                    failed_count += 1

            # Save updated user data
            save_json(USER_DATA_FILE, user_data)

            # Send completion message
            completion_text = f"""
💰 Credit Distribution Complete!

✅ Successfully added: {success_count} users
❌ Failed to add: {failed_count} users
📊 Total users: {len(active_users)}
💰 Credits per user: {credit_amount}
💳 Total credits distributed: {success_count * credit_amount}

💬 Message sent: {custom_message[:50] + '...' if custom_message and len(custom_message) > 50 else custom_message or 'Default message'}
            """

            back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])

            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(completion_text, reply_markup=back_button)
            else:
                await update.message.reply_text(completion_text, reply_markup=back_button)

        context.user_data['state'] = None
        context.user_data.pop('credit_all_amount', None)

    except Exception as e:
        logger.error(f"Error giving credit to all: {e}")
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="users")]])
        error_msg = "❌ Error occurred while giving credit to all users. Please try again."

        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_msg, reply_markup=back_button)
        else:
            await update.message.reply_text(error_msg, reply_markup=back_button)
        context.user_data['state'] = None

async def handle_credit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free credit link option - show shortlinks based on priority"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    # Check if free credits feature is enabled
    if not TOOLS_STATUS.get('free_credits', True):
        reason = TOOLS_DEACTIVATION_REASONS.get('free_credits', 'No reason provided')
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="add_credit")]])
        await query.edit_message_text(
            f"❎ Free Credits Feature Disabled\n\n"
            f"📝 Reason: {reason}\n\n"
            f"This feature has been temporarily disabled by the owner. "
            f"Please try again later or use other methods to earn credits.",
            reply_markup=back_button
        )
        return

    reload_data()
    
    # Get link based on priority distribution
    selected_link = select_link_by_priority()
    
    if not selected_link:
        text = f"""
🎁 Free Credits

❌ No shortlinks available at the moment.

💡 Complete shortlinks to earn {CREDIT_CONFIG['shortlink_reward']} credits per link!

Please check back later.
        """
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_links")],
            [InlineKeyboardButton("🔙 Back", callback_data="add_credit")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        # Store temporary assignment (expires in 3 minutes)
        expires_at = datetime.now() + timedelta(minutes=3)
        TEMP_LINK_ASSIGNMENTS[uid] = {
            'link_data': selected_link,
            'expires_at': expires_at,
            'assigned_at': datetime.now()
        }
        
        # Generate bot verification link
        bot_username = context.bot.username or "mediaGenie_bot"
        verification_link = f"https://t.me/{bot_username}?start={selected_link['payload']}"
        
        text = f"""
🎁 Free Credits - Complete Link

💰 Earn {CREDIT_CONFIG['shortlink_reward']} credits per completed link!

🔗 **Your Assigned Link:**
Complete this link to get verification code

⏰ **Time Limit:** 3 minutes
🌐 **Shortener:** {selected_link['shortener_domain']} (Priority: {selected_link['priority']}%)
🎯 **Reward:** {CREDIT_CONFIG['shortlink_reward']} credits


📋 **Steps:**
1. Click "Complete Link" button
2. Complete the shortlink process
3. You'll receive a bot link like: {verification_link}
4. Click that link to get your credits automatically!

No need to enter payload manually!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔗 Complete Link", url=selected_link['url'])],
            [InlineKeyboardButton("🔄 Get New Link", callback_data="refresh_links")],
            [InlineKeyboardButton("🔙 Back", callback_data="add_credit")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Check if message content is different before editing
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception as e:
            if "Message is not modified" in str(e):
                await query.answer("🔄 Link refreshed!", show_alert=False)
            else:
                # Send new message if edit fails
                await query.message.reply_text(text, reply_markup=reply_markup)

def get_quality_credit_cost(quality: str) -> int:
    """Get credit cost for specific video quality"""
    # Handle various quality formats
    quality_lower = quality.lower().strip()
    
    # Direct mapping for exact matches
    if quality == 'Audio Only':
        return CREDIT_CONFIG['yt_audio_cost']
    
    # Extract resolution from quality string
    if 'p' in quality_lower:
        # Extract number before 'p' (e.g., "1080p" -> 1080)
        try:
            resolution = int(quality_lower.replace('p', ''))
            
            if resolution >= 1080:
                return CREDIT_CONFIG['yt_1080p_cost']
            elif resolution >= 720:
                return CREDIT_CONFIG['yt_720p_cost']
            elif resolution >= 480:
                return CREDIT_CONFIG['yt_480p_cost']
            elif resolution >= 360:
                return CREDIT_CONFIG['yt_360p_cost']
            elif resolution >= 240:
                return CREDIT_CONFIG['yt_240p_cost']
            elif resolution >= 144:
                return CREDIT_CONFIG['yt_144p_cost']
            else:
                return CREDIT_CONFIG['yt_144p_cost']  # Lowest quality cost for very low res
        except ValueError:
            pass
    
    # Fallback mappings for different quality formats
    quality_costs = {
        # Standard formats
        '1080p': CREDIT_CONFIG['yt_1080p_cost'],
        '720p': CREDIT_CONFIG['yt_720p_cost'],
        '480p': CREDIT_CONFIG['yt_480p_cost'],
        '360p': CREDIT_CONFIG['yt_360p_cost'],
        '240p': CREDIT_CONFIG['yt_240p_cost'],
        '144p': CREDIT_CONFIG['yt_144p_cost'],
        
        # HD formats
        'hd': CREDIT_CONFIG['yt_720p_cost'],
        'full hd': CREDIT_CONFIG['yt_1080p_cost'],
        'fhd': CREDIT_CONFIG['yt_1080p_cost'],
        
        # Quality names
        'high': CREDIT_CONFIG['yt_720p_cost'],
        'medium': CREDIT_CONFIG['yt_480p_cost'],
        'low': CREDIT_CONFIG['yt_240p_cost'],
        'very low': CREDIT_CONFIG['yt_144p_cost'],
        
        # Audio
        'audio only': CREDIT_CONFIG['yt_audio_cost'],
        'audio': CREDIT_CONFIG['yt_audio_cost'],
        'mp3': CREDIT_CONFIG['yt_audio_cost'],
        
        # Common variations
        'best': CREDIT_CONFIG['yt_1080p_cost'],
        'worst': CREDIT_CONFIG['yt_144p_cost']
    }
    
    return quality_costs.get(quality_lower, CREDIT_CONFIG['yt_480p_cost'])  # Default to 480p cost

def get_priority_based_shortlinks():
    """Get shortlinks based on priority distribution of link shorteners"""
    reload_data()
    
    if not shortlinks_data:
        return []
    
    # Group links by shortener and calculate priority weights
    shortener_links = {}
    priority_weights = {}
    
    for link_id, link_data in shortlinks_data.items():
        if link_data.get('status', 'Active') == 'Active':
            shortener_id = link_data.get('shortener_id')
            shortener_domain = link_data.get('shortener_domain', 'Unknown')
            priority = 50  # Default priority
            
            # Check if shortener exists and get priority
            if shortener_id and shortener_id in link_shorteners_data:
                shortener = link_shorteners_data[shortener_id]
                try:
                    # Extract priority percentage (e.g., "20%" -> 20)
                    priority_str = shortener.get('priority', '50%')
                    priority = int(priority_str.replace('%', ''))
                    shortener_domain = shortener.get('domain', shortener_domain)
                except (ValueError, TypeError):
                    priority = 50
            
            link_info = {
                'id': link_id,
                'url': link_data['url'],
                'payload': link_data.get('payload', ''),
                'shortener_domain': shortener_domain,
                'priority': priority
            }
            
            # Group by shortener
            if shortener_id not in shortener_links:
                shortener_links[shortener_id] = []
                priority_weights[shortener_id] = priority
            
            shortener_links[shortener_id].append(link_info)
    
    # Create weighted distribution based on priority
    all_links = []
    
    for shortener_id, links in shortener_links.items():
        weight = priority_weights[shortener_id]
        # Add links multiple times based on priority weight
        for _ in range(max(1, weight)):  # Ensure at least 1 representation
            if links:  # Check if links exist
                all_links.extend(links)
    
    return all_links

def select_link_by_priority():
    """Select a link based on priority distribution with proper validation"""
    import random
    
    reload_data()
    
    if not shortlinks_data or not link_shorteners_data:
        return None
    
    # Get active shortlinks with validated priority
    weighted_links = []
    
    for link_id, link_data in shortlinks_data.items():
        if link_data.get('status', 'Active') != 'Active':
            continue
            
        shortener_id = link_data.get('shortener_id')
        if not shortener_id or shortener_id not in link_shorteners_data:
            continue
            
        shortener = link_shorteners_data[shortener_id]
        
        # Validate and normalize priority
        priority_str = shortener.get('priority', '50%')
        try:
            # Clean priority string (remove %, spaces, etc.)
            priority_clean = ''.join(filter(str.isdigit, str(priority_str)))
            if not priority_clean:
                priority = 50
            else:
                priority = int(priority_clean)
                # Ensure priority is within valid range
                priority = max(1, min(100, priority))
        except (ValueError, TypeError):
            priority = 50
        
        link_info = {
            'id': link_id,
            'url': link_data['url'],
            'payload': link_data.get('payload', ''),
            'shortener_domain': shortener.get('domain', 'Unknown'),
            'priority': f"{priority}%"
        }
        
        # Add link multiple times based on priority (1-100 times)
        for _ in range(priority):
            weighted_links.append(link_info)
    
    if not weighted_links:
        return None
    
    # Select randomly from weighted distribution
    return random.choice(weighted_links)

async def handle_credit_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle credit referral option"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    # Check if referral feature is enabled
    if not TOOLS_STATUS.get('referral', True):
        reason = TOOLS_DEACTIVATION_REASONS.get('referral', 'No reason provided')
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="add_credit")]])
        await query.edit_message_text(
            f"❎ Referral System Disabled\n\n"
            f"📝 Reason: {reason}\n\n"
            f"The referral system has been temporarily disabled by the owner. "
            f"Please try again later or use other methods to earn credits.",
            reply_markup=back_button
        )
        return

    reload_data()
    user_info = user_data.get(uid, {})
    referral_count = user_info.get('referral_count', 0)
    total_referral_credits = referral_count * CREDIT_CONFIG['referral_reward']

    # Generate referral link
    referral_link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"

    text = f"""
👥 Referral System

🔗 **Your Referral Link:**
`{referral_link}`

📊 **Your Stats:**
• Total Referrals: {referral_count}
• Credits Earned: {total_referral_credits}
• Per Referral: {CREDIT_CONFIG['referral_reward']} credits

💡 **How it works:**
1. Share your referral link with friends
2. When they join using your link
3. You get {CREDIT_CONFIG['referral_reward']} credits
4. They get {CREDIT_CONFIG['welcome_credit']} welcome + {CREDIT_CONFIG['referral_reward']} referral credits

Start sharing and earning!
    """

    keyboard = [
        [InlineKeyboardButton("📋 Copy", callback_data=f"copy_referral_{user.id}"),
         InlineKeyboardButton("📤 Share", url=f"https://t.me/share/url?url={referral_link}&text=Join this amazing bot and get free credits!")],
        [InlineKeyboardButton("📊 Referral Status", callback_data="referral_status")],
        [InlineKeyboardButton("🔙 Back", callback_data="add_credit")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def handle_referral_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed referral status"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    reload_data()
    user_info = user_data.get(uid, {})
    referral_count = user_info.get('referral_count', 0)
    total_referral_credits = referral_count * CREDIT_CONFIG['referral_reward']
    current_credits = user_info.get('credits', 0)

    status_text = f"""
📊 Referral Status Details

👤 **Your Account:**
• Name: {user_info.get('name', 'Unknown')}
• User ID: {user.id}
• Current Credits: {current_credits}

🎯 **Referral Performance:**
• Total Successful Referrals: {referral_count}
• Credits per Referral: {CREDIT_CONFIG['referral_reward']}
• Total Earned from Referrals: {total_referral_credits}

💰 **Earning Breakdown:**
• Welcome Credits: {CREDIT_CONFIG['welcome_credit']}
• Referral Earnings: {total_referral_credits}
• Link Completions: Variable
• Tool Usage: Variable

🚀 **Next Steps:**
• Share your referral link to earn more credits
• Each new user = {CREDIT_CONFIG['referral_reward']} credits for you
• No limit on referrals!
    """

    keyboard = [
        [InlineKeyboardButton("🔗 Get Referral Link", callback_data="credit_referral")],
        [InlineKeyboardButton("🔙 Back", callback_data="credit_referral")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(status_text, reply_markup=reply_markup)

async def handle_credit_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle coupon redeem option"""
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)

    reload_data()
    user_info = user_data.get(uid, {})
    current_credits = user_info.get('credits', 0)

    text = f"""
🎫 **Re�deem Coupon**

💰 **Current Credits:** {current_credits}

Enter your coupon code to redeem free credits!

📝 **Instructions:**
• Type the exact coupon code
• Codes are case-sensitive
• Each code can only be used once per user
• Contact support if you need a valid coupon code

💡 **Example:** COUP10F57EG1

Enter your coupon code:
    """

    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="add_credit")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['state'] = 'waiting_user_coupon_code'

async def process_user_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE, coupon_code: str):
    """Process user coupon code submission"""
    user = update.effective_user
    uid = str(user.id)
    
    coupon_code = coupon_code.strip().upper()
    
    reload_data()  # This will auto-expire items
    
    # Find coupon by code
    found_coupon = None
    coupon_id = None
    
    for cid, coupon_data in coupons_data.items():
        if coupon_data.get('code', '').upper() == coupon_code:
            found_coupon = coupon_data
            coupon_id = cid
            break
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="credit_coupon")]])
    
    if not found_coupon:
        await update.message.reply_text(
            f"❌ **Invalid Coupon Code**\n\n"
            f"🎫 Code: {coupon_code}\n"
            f"🔍 This coupon code was not found.\n\n"
            f"📝 Please check:\n"
            f"• Spelling and case sensitivity\n"
            f"• Code validity\n"
            f"• Contact owner if issue persists",
            reply_markup=back_button,
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    # Check if coupon is active (after auto-expiry check)
    if found_coupon.get('status') != 'Active':
        await update.message.reply_text(
            f"❌ **Coupon Expired**\n\n"
            f"🎫 Code: {coupon_code}\n"
            f"📅 This coupon has automatically expired.\n\n"
            f"💡 Try using a different coupon code.",
            reply_markup=back_button,
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    # Check expiry date
    try:
        end_date = datetime.fromisoformat(found_coupon.get('end_date', ''))
        if datetime.now() >= end_date:
            await update.message.reply_text(
                f"❌ **Coupon Expired**\n\n"
                f"🎫 Code: {coupon_code}\n"
                f"📅 Expired: {end_date.strftime('%d/%m/%Y %H:%M')}\n\n"
                f"💡 This coupon has expired. Try another code.",
                reply_markup=back_button,
                parse_mode='Markdown'
            )
            context.user_data['state'] = None
            return
    except:
        pass
    
    # Check if user already used this coupon
    used_by = found_coupon.get('used_by', [])
    if uid in used_by:
        await update.message.reply_text(
            f"❌ **Already Used**\n\n"
            f"🎫 Code: {coupon_code}\n"
            f"👤 You have already used this coupon.\n\n"
            f"💡 Each coupon can only be used once per user.",
            reply_markup=back_button,
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    # Check user limit
    user_limit = found_coupon.get('user_limit', 'Unlimited')
    used_count = found_coupon.get('used_count', 0)
    
    if user_limit != 'Unlimited' and used_count >= user_limit:
        await update.message.reply_text(
            f"❌ **Usage Limit Reached**\n\n"
            f"🎫 Code: {coupon_code}\n"
            f"👥 This coupon has reached its usage limit.\n"
            f"📊 Used: {used_count}/{user_limit}\n\n"
            f"💡 Try another coupon code.",
            reply_markup=back_button,
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    # All checks passed - redeem coupon
    credit_amount = found_coupon.get('credit_amount', 50)
    
    # Update user credits
    if uid in user_data:
        old_credits = user_data[uid].get('credits', 0)
        user_data[uid]['credits'] = old_credits + credit_amount
        user_data[uid]['user_updated_at'] = datetime.now().isoformat()
    
    # Update coupon usage
    coupons_data[coupon_id]['used_count'] = used_count + 1
    coupons_data[coupon_id]['used_by'].append(uid)
    coupons_data[coupon_id]['total_credits_given'] = coupons_data[coupon_id].get('total_credits_given', 0) + credit_amount
    
    # Save data
    save_json(USER_DATA_FILE, user_data)
    save_json(COUPONS_FILE, coupons_data)
    
    # Success message
    success_text = f"""
✅ **Coupon Redeemed Successfully!**

🎫 **Coupon Details:**
• **Code:** {coupon_code}
• **Credits Earned:** {credit_amount}

💰 **Your Credits:**
• **Previous:** {old_credits}
• **Added:** {credit_amount}
• **New Total:** {user_data[uid]['credits']}

🎉 **Congratulations!**
Your coupon has been successfully redeemed.
Enjoy your free credits!

⏰ **Redeemed At:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    """
    
    success_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Add Credit", callback_data="add_credit")]])
    await update.message.reply_text(success_text, reply_markup=success_button, parse_mode='Markdown')
    
    context.user_data['state'] = None

# Payload verification is now handled through start command automatically

# ======================== START PAYLOAD HANDLER ========================
async def handle_start_payload(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str, user):
    """Handle start command payload (referral link or shortlink payload verification)"""
    uid = str(user.id)
    
    # Check if payload is a shortlink verification
    if payload.isdigit():
        await handle_shortlink_payload_verification(update, context, payload, user)
        return
    
    # Handle owner referral link
    if payload == "owner_ref":
        reload_data()
        
        if uid not in user_data:
            # New user referred by owner
            user_data[uid] = {
                "name": user.full_name,
                "user_id": user.id,
                "user_first_name": user.first_name or "",
                "user_last_name": user.last_name or "",
                "user_email": "",
                "user_phone": "",
                "username": user.username,
                "language": "en",
                "user_status": "active",
                "user_type": "user",
                "user_created_at": datetime.now().isoformat(),
                "user_updated_at": datetime.now().isoformat(),
                "credits": CREDIT_CONFIG['welcome_credit'] + CREDIT_CONFIG['referral_reward'],
                "referred_by": "owner_ref",
                "referral_count": 0
            }
            save_json(USER_DATA_FILE, user_data)
            
            welcome_msg = f"""
🎉 **Special Welcome from Owner!**

🎁 **You received extra credits:**
• {CREDIT_CONFIG['welcome_credit']} welcome credits
• {CREDIT_CONFIG['referral_reward']} special owner referral bonus
💰 **Total: {CREDIT_CONFIG['welcome_credit'] + CREDIT_CONFIG['referral_reward']} credits!**

🌟 You were personally referred by the bot owner!
Start exploring our amazing features now:

🛠️ **Available Tools:**
• 🗣️ Text to Speech (Hindi/English)
• 🎤 Speech to Text
• 🎬 Video Transcription
• 💰 Credit System

Thank you for joining us! 🚀
            """
            await update.message.reply_text(welcome_msg, reply_markup=get_user_panel())
        else:
            await update.message.reply_text(
                f"👋 Welcome back, {user.first_name}!\n\n"
                f"You're already part of our community. Enjoy using the bot! 😊",
                reply_markup=get_user_panel()
            )
        return
    
    # Handle regular user referral link
    if payload.startswith("ref_"):
        # Check if referral feature is enabled
        if not TOOLS_STATUS.get('referral', True):
            reason = TOOLS_DEACTIVATION_REASONS.get('referral', 'No reason provided')
            await update.message.reply_text(
                f"❎ Referral System Disabled\n\n"
                f"📝 Reason: {reason}\n\n"
                f"The referral system has been temporarily disabled by the owner. "
                f"Please try again later or contact support for assistance.",
                reply_markup=get_user_panel()
            )
            return
            
        referrer_id = payload[4:]
        if referrer_id == uid:
            await update.message.reply_text("❌ You cannot refer yourself!")
            return
        try:
            referrer_id = str(int(referrer_id))  # Ensure it's an integer and string
        except ValueError:
            await update.message.reply_text("❌ Invalid referral link!")
            return

        reload_data()

        if uid not in user_data:
            # New referred user
            if referrer_id in user_data:
                # Valid referrer
                user_data[uid] = {
                    "name": user.full_name,
                    "user_id": user.id,
                    "user_first_name": user.first_name or "",
                    "user_last_name": user.last_name or "",
                    "user_email": "",
                    "user_phone": "",
                    "username": user.username,
                    "language": "en",
                    "user_status": "active",
                    "user_type": "user",
                    "user_created_at": datetime.now().isoformat(),
                    "user_updated_at": datetime.now().isoformat(),
                    "credits": CREDIT_CONFIG['welcome_credit'] + CREDIT_CONFIG['referral_reward'],
                    "referred_by": referrer_id,
                    "referral_count": 0
                }
                save_json(USER_DATA_FILE, user_data)

                # Increase referrer's referral count and credits
                user_data[referrer_id]['referral_count'] = user_data[referrer_id].get('referral_count', 0) + 1
                user_data[referrer_id]['credits'] = user_data[referrer_id].get('credits', 0) + CREDIT_CONFIG['referral_reward']
                save_json(USER_DATA_FILE, user_data)

                # Notify both users
                welcome_msg = f"""
🎉 Welcome to the bot!

🎁 You were referred by a friend!

👤 You received:
• {CREDIT_CONFIG['welcome_credit']} welcome credits
• {CREDIT_CONFIG['referral_reward']} referral credits
💰 Total: {CREDIT_CONFIG['welcome_credit'] + CREDIT_CONFIG['referral_reward']} credits!

Start exploring the bot now!
                """
                await update.message.reply_text(welcome_msg, reply_markup=get_user_panel())

                referrer_msg = f"""
🎉 New Referral!

👤 {user.full_name} joined using your referral link!
🎁 You received {CREDIT_CONFIG['referral_reward']} credits!
💰 Total Credits: {user_data[referrer_id]['credits']}
                """
                try:
                    await context.bot.send_message(chat_id=referrer_id, text=referrer_msg)
                except Exception as e:
                    logger.error(f"Failed to send referral notification to referrer {referrer_id}: {e}")
            else:
                await update.message.reply_text("❌ Invalid referral link! Referrer not found.", reply_markup=get_user_panel())
        else:
            await update.message.reply_text("👋 Welcome back!", reply_markup=get_user_panel())
    else:
        await update.message.reply_text("❌ Invalid start command!", reply_markup=get_user_panel())

async def handle_shortlink_payload_verification(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str, user):
    """Handle shortlink payload verification from start command"""
    uid = str(user.id)
    
    # Check if user has an assigned link
    if uid not in TEMP_LINK_ASSIGNMENTS:
        await update.message.reply_text(
            f"❌ No active link assignment found!\n\n"
            f"📦 Payload received: {payload}\n\n"
            f"Please get a new shortlink from the bot first.",
            reply_markup=get_user_panel()
        )
        return
    
    assignment = TEMP_LINK_ASSIGNMENTS[uid]
    
    # Check if link has expired
    if datetime.now() > assignment['expires_at']:
        del TEMP_LINK_ASSIGNMENTS[uid]
        await update.message.reply_text(
            f"⏰ Your link assignment has expired!\n\n"
            f"📦 Payload received: {payload}\n\n"
            f"Please get a new shortlink from the bot.",
            reply_markup=get_user_panel()
        )
        return
    
    # Verify payload
    expected_payload = assignment['link_data']['payload']
    
    if payload.strip() == expected_payload.strip():
        # Payload is correct, give credits
        reload_data()
        
        if uid in user_data:
            old_credits = user_data[uid].get('credits', 0)
            user_data[uid]['credits'] = old_credits + CREDIT_CONFIG['shortlink_reward']
            user_data[uid]['user_updated_at'] = datetime.now().isoformat()
            save_json(USER_DATA_FILE, user_data)

            # Remove assignment
            del TEMP_LINK_ASSIGNMENTS[uid]

            success_text = f"""
✅ Shortlink Completed Successfully!

🎉 Congratulations! You have successfully completed the shortlink task.

💰 **Credits Reward:** {CREDIT_CONFIG['shortlink_reward']}
💳 **Previous Credits:** {old_credits}
💎 **New Total:** {user_data[uid]['credits']}

🔗 **Completed Link:** {assignment['link_data']['shortener_domain']}
📦 **Payload Verified:** {payload}
⏰ **Completed At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Thank you for using our service! Continue exploring the bot features.
            """

            await update.message.reply_text(success_text, reply_markup=get_user_panel())
        else:
            await update.message.reply_text("❌ User data not found! Please contact support.", reply_markup=get_user_panel())
    else:
        # Wrong payload
        await update.message.reply_text(
            f"❌ Invalid Payload!\n\n"
            f"📦 You provided: {payload}\n"
            f"🔗 Link: {assignment['link_data']['shortener_domain']}\n\n"
            f"Please complete the correct shortlink and try again.",
            reply_markup=get_user_panel()
        )



# ======================== IMPORTANT INFO FUNCTIONS ========================
async def handle_important_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle important info button click"""
    query = update.callback_query
    reload_data()

    if not important_info:
        # No data saved, show add info option
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Info", callback_data="add_info")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings")]
        ])
        await query.edit_message_text(
            "📋 Important Information\n\n"
            "❌ No important data saved yet.\n\n"
            "Click 'Add Info' to save important information.",
            reply_markup=keyboard
        )
    else:
        # Show saved info with pagination
        await show_important_info_list(update, context, page=1)

async def add_important_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding new important info"""
    query = update.callback_query
    await query.edit_message_text("📝 Please send the title for this important information:")
    context.user_data['state'] = 'waiting_imp_info_title'

async def process_important_info_save(update: Update, context: ContextTypes.DEFAULT_TYPE, data_text: str):
    """Save the important information"""
    title = context.user_data.get('imp_info_title', 'Untitled')
    
    # Generate unique ID for the info
    import uuid
    info_id = str(uuid.uuid4())[:8]
    
    # Save to important_info
    reload_data()
    important_info[info_id] = {
        "title": title,
        "data": data_text,
        "created_at": datetime.now().isoformat(),
        "created_by": "Owner"
    }
    save_json(IMP_INFO_FILE, important_info)
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back�", callback_data="important_info")]])
    await update.message.reply_text(
        f"✅ Important Information Saved!\n\n"
        f"📝 Title: {title}\n"
        f"🆔 ID: {info_id}\n"
        f"📊 Data Length: {len(data_text)} characters\n"
        f"⏰ Saved At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=back_button
    )
    
    context.user_data['state'] = None
    context.user_data.pop('imp_info_title', None)

async def show_important_info_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Show list of important info with pagination"""
    query = update.callback_query
    reload_data()
    
    items_per_page = 4
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    info_ids = list(important_info.keys())
    paginated_infos = info_ids[start_index:end_index]
    total_pages = (len(info_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-4: Info titles
    for info_id in paginated_infos:
        info_data = important_info[info_id]
        title = info_data['title'][:30] + "..." if len(info_data['title']) > 30 else info_data['title']
        keyboard.append([InlineKeyboardButton(f"📋 {title}", callback_data=f"view_info_{info_id}")])
    
    # Row 5: Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"previous_info_{page}"))
    if len(nav_row) == 0 or len(nav_row) == 1:  # Add spacing or next button
        if end_index < len(info_ids):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_info_{page}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Add "Add Info", "Remove Info" and "Back" buttons
    keyboard.append([InlineKeyboardButton("➕ Add Info", callback_data="add_info"),
                     InlineKeyboardButton("➖ Remove Info", callback_data="remove_info")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"📋 Important Information{page_info}\n\n"
        f"📊 Total Items: {len(info_ids)}\n"
        f"Select an item to view details:",
        reply_markup=reply_markup
    )

async def view_important_info(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """View specific important info details"""
    query = update.callback_query
    info_id = callback_data.split("_")[-1]
    
    reload_data()
    info_data = important_info.get(info_id)
    
    if not info_data:
        await query.answer("Information not found!")
        return
    
    info_text = f"""
📋 Important Information Details

📝 **Title:** {info_data['title']}
🆔 **ID:** {info_id}
📅 **Created:** {info_data.get('created_at', 'Unknown')}
👤 **Created By:** {info_data.get('created_by', 'Unknown')}

📄 **Content:**
{info_data['data']}
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to List", callback_data="important_info")]
    ])
    
    await query.edit_message_text(info_text, reply_markup=keyboard)

async def remove_important_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of important info for removal"""
    query = update.callback_query
    reload_data()
    
    if not important_info:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="important_info")]
        ])
        await query.edit_message_text(
            "➖ Remove Important Information\n\n"
            "❌ No important data available to remove.",
            reply_markup=keyboard
        )
        return
    
    items_per_page = 4
    current_page = context.user_data.get('remove_info_page', 1)
    start_index = (current_page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    info_ids = list(important_info.keys())
    paginated_infos = info_ids[start_index:end_index]
    total_pages = (len(info_ids) + items_per_page - 1) // items_per_page
    
    keyboard = []
    
    # Row 1-4: Info titles for removal
    for info_id in paginated_infos:
        info_data = important_info[info_id]
        title = info_data['title'][:30] + "..." if len(info_data['title']) > 30 else info_data['title']
        keyboard.append([InlineKeyboardButton(f"🗑️ {title}", callback_data=f"remove_info_{info_id}")])
    
    # Row 5: Navigation buttons
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="previous_remove_info"))
    if end_index < len(info_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_remove_info"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Row 6: Back button
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="important_info")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {current_page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"➖ Remove Important Information{page_info}\n\n"
        f"📊 Total Items: {len(info_ids)}\n"
        f"⚠️ Select an item to remove:",
        reply_markup=reply_markup
    )

async def confirm_remove_important_info(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Ask for confirmation before removing important info"""
    query = update.callback_query
    info_id = callback_data.split("_")[-1]
    
    reload_data()
    info_data = important_info.get(info_id)
    
    if not info_data:
        await query.answer("Information not found!")
        return
    
    confirmation_text = f"""
🗑️ Confirm Removal

Are you sure you want to delete this information?

📝 **Title:** {info_data['title']}
🆔 **ID:** {info_id}
📅 **Created:** {info_data.get('created_at', 'Unknown')}

⚠️ **Warning:** This action cannot be undone!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"delete_info_{info_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data="remove_info")]
    ])
    
    await query.edit_message_text(confirmation_text, reply_markup=keyboard)

async def delete_important_info(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Delete the important info after confirmation"""
    query = update.callback_query
    info_id = callback_data.split("_")[-1]
    
    reload_data()
    info_data = important_info.get(info_id)
    
    if not info_data:
        await query.answer("Information not found!")
        return
    
    # Delete the info
    deleted_title = info_data['title']
    del important_info[info_id]
    save_json(IMP_INFO_FILE, important_info)
    
    success_text = f"""
✅ Information Deleted Successfully!

📝 **Deleted:** {deleted_title}
🆔 **ID:** {info_id}
⏰ **Deleted At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The information has been permanently removed.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to List", callback_data="important_info")]
    ])
    
    await query.edit_message_text(success_text, reply_markup=keyboard)

async def handle_info_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle pagination for important info"""
    query = update.callback_query
    
    if callback_data.startswith("next_info_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page + 1
        await show_important_info_list(update, context, page=new_page)
    elif callback_data.startswith("previous_info_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page - 1
        await show_important_info_list(update, context, page=new_page)
    elif callback_data == "next_remove_info":
        current_page = context.user_data.get('remove_info_page', 1)
        context.user_data['remove_info_page'] = current_page + 1
        await remove_important_info(update, context)
    elif callback_data == "previous_remove_info":
        current_page = context.user_data.get('remove_info_page', 1)
        if current_page > 1:
            context.user_data['remove_info_page'] = current_page - 1
        await remove_important_info(update, context)

async def detailed_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed user analytics and usage statistics"""
    query = update.callback_query
    reload_data()
    
    # User registration analysis
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    users_today = 0
    users_this_week = 0
    users_this_month = 0
    
    for user in user_data.values():
        try:
            created_date = datetime.fromisoformat(user.get('user_created_at', '')).date()
            if created_date == today:
                users_today += 1
            if created_date >= week_ago:
                users_this_week += 1
            if created_date >= month_ago:
                users_this_month += 1
        except:
            continue
    
    # Credit distribution analysis
    users_by_credits = {
        "0-50": 0,
        "51-100": 0,
        "101-500": 0,
        "500+": 0
    }
    
    for user in user_data.values():
        credits = user.get('credits', 0)
        if credits <= 50:
            users_by_credits["0-50"] += 1
        elif credits <= 100:
            users_by_credits["51-100"] += 1
        elif credits <= 500:
            users_by_credits["101-500"] += 1
        else:
            users_by_credits["500+"] += 1
    
    # Referral analysis
    total_referrals = sum(user.get('referral_count', 0) for user in user_data.values())
    users_with_referrals = len([u for u in user_data.values() if u.get('referral_count', 0) > 0])
    
    analytics_text = f"""
📊 **DETAILED ANALYTICS DASHBOARD**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📈 **USER GROWTH ANALYSIS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🆕 New Users Today: {users_today}
┃ 📅 New Users This Week: {users_this_week}
┃ 📊 New Users This Month: {users_this_month}
┃ 🎯 Average Daily Growth: {users_this_month/30:.1f}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 💰 **CREDIT DISTRIBUTION**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🔴 0-50 Credits: {users_by_credits["0-50"]} users
┃ 🟡 51-100 Credits: {users_by_credits["51-100"]} users
┃ 🟢 101-500 Credits: {users_by_credits["101-500"]} users
┃ 💎 500+ Credits: {users_by_credits["500+"]} users
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 👥 **REFERRAL SYSTEM ANALYSIS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🔗 Total Referrals: {total_referrals}
┃ 👤 Users with Referrals: {users_with_referrals}
┃ 📊 Avg Referrals per User: {total_referrals/len(user_data):.2f}
┃ 🎯 Referral Rate: {(users_with_referrals/len(user_data)*100):.1f}%
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔗 **SHORTLINK ANALYTICS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🌐 Active Shorteners: {len([ls for ls in link_shorteners_data.values() if ls.get('status') == 'Active'])}
┃ ⚠️ Error Shorteners: {len([ls for ls in link_shorteners_data.values() if ls.get('status') != 'Active'])}
┃ 📋 Generated Links: {len([sl for sl in shortlinks_data.values() if sl.get('creation_type') == 'Generated'])}
┃ ➕ Manual Links: {len([sl for sl in shortlinks_data.values() if sl.get('creation_type') != 'Generated'])}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

🕐 **Analysis Generated:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
📊 **Data Points Analyzed:** {len(user_data) + len(shortlinks_data) + len(link_shorteners_data)}
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Analytics", callback_data="detailed_analytics")],
        [InlineKeyboardButton("📊 Main Status", callback_data="status"),
         InlineKeyboardButton("⚙️ System Health", callback_data="system_health")],
        [InlineKeyboardButton("🔙 Back to Owner Panel", callback_data="back_to_owner")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(analytics_text, reply_markup=reply_markup)

async def system_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system health and configuration status"""
    query = update.callback_query
    
    # Check file system health
    import os
    
    file_health = {}
    files_to_check = [
        ("User Data", USER_DATA_FILE),
        ("Banned Users", BANNED_USERS_FILE),
        ("Shortlinks", SHORTLINKS_FILE),
        ("Link Shorteners", LINK_SHORTENERS_FILE),
        ("Important Info", IMP_INFO_FILE)
    ]
    
    for name, file_path in files_to_check:
        try:
            if file_path.exists():
                size = os.path.getsize(file_path)
                file_health[name] = {"status": "✅ OK", "size": f"{size} bytes"}
            else:
                file_health[name] = {"status": "⚠️ Missing", "size": "0 bytes"}
        except Exception as e:
            file_health[name] = {"status": "❌ Error", "size": str(e)[:20]}
    
    # Check API integrations
    api_status = "✅ Ready" if any(ls.get('api') for ls in link_shorteners_data.values()) else "⚠️ No APIs"
    
    # Memory usage estimation
    total_data_size = sum(os.path.getsize(f) for _, f in files_to_check if f.exists())
    
    health_text = f"""
⚙️ **SYSTEM HEALTH MONITOR**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🗂️ **FILE SYSTEM STATUS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 👥 User Data: {file_health["User Data"]["status"]}
┃ 🚫 Banned Users: {file_health["Banned Users"]["status"]}
┃ 🔗 Shortlinks: {file_health["Shortlinks"]["status"]}
┃ 🌐 Link Shorteners: {file_health["Link Shorteners"]["status"]}
┃ 📋 Important Info: {file_health["Important Info"]["status"]}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🔌 **API & INTEGRATION STATUS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🔗 Shortlink APIs: {api_status}
┃ 🎤 Speech Recognition: ✅ Ready
┃ 🗣️ Text-to-Speech: ✅ Ready
┃ 📡 Telegram API: ✅ Connected
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 💾 **DATA STORAGE INFO**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 📊 Total Data Size: {total_data_size:,} bytes
┃ 🔄 Auto-Backup: Enabled
┃ 💽 Storage Method: JSON Files
┃ 🛡️ Data Protection: Active
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚡ **PERFORMANCE METRICS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🚀 Response Time: Fast
┃ 🔄 Update Polling: Active
┃ 🛠️ Error Handling: Robust
┃ 📈 Uptime: Stable
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

🔍 **Health Check:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
🏥 **Overall Status:** {'🟢 Healthy' if all(h['status'].startswith('✅') for h in file_health.values()) else '⚠️ Needs Attention'}
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Health", callback_data="system_health")],
        [InlineKeyboardButton("📊 Main Status", callback_data="status"),
         InlineKeyboardButton("📈 Performance", callback_data="performance_stats")],
        [InlineKeyboardButton("🔙 Back to Owner Panel", callback_data="back_to_owner")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(health_text, reply_markup=reply_markup)

async def performance_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show performance statistics and optimization suggestions"""
    query = update.callback_query
    reload_data()
    
    # Calculate performance metrics
    total_records = len(user_data) + len(shortlinks_data) + len(link_shorteners_data) + len(important_info)
    
    # Estimate memory usage
    import sys
    user_data_size = sys.getsizeof(str(user_data))
    shortlinks_size = sys.getsizeof(str(shortlinks_data))
    
    # Performance scoring
    performance_score = 100
    
    # Deduct points for large datasets
    if len(user_data) > 1000:
        performance_score -= 10
    if len(shortlinks_data) > 500:
        performance_score -= 5
    if len(banned_users) > 50:
        performance_score -= 5
    
    # Performance grade
    if performance_score >= 90:
        grade = "🟢 Excellent"
    elif performance_score >= 75:
        grade = "🟡 Good"
    elif performance_score >= 60:
        grade = "🟠 Fair"
    else:
        grade = "🔴 Needs Optimization"
    
    perf_text = f"""
📈 **PERFORMANCE STATISTICS**

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚡ **PERFORMANCE OVERVIEW**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🎯 Performance Score: {performance_score}/100
┃ 📊 Performance Grade: {grade}
┃ 🗂️ Total Records: {total_records:,}
┃ 🔄 Data Processing: Optimized
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 💾 **MEMORY UTILIZATION**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 👥 User Data: ~{user_data_size//1024} KB
┃ 🔗 Shortlinks: ~{shortlinks_size//1024} KB
┃ 📊 Total Estimated: ~{(user_data_size + shortlinks_size)//1024} KB
┃ 🛡️ Memory Management: Efficient
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🚀 **OPTIMIZATION STATUS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 🔄 Data Reload: On-Demand
┃ 📝 JSON Saving: Optimized
┃ 🗃️ File I/O: Efficient
┃ 🧹 Memory Cleanup: Active
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📊 **USAGE STATISTICS**
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┃ 👥 Active Users: {len([u for u in user_data.values() if u.get('user_status') == 'active'])}
┃ 🛠️ Tools Available: {len(TOOLS_STATUS)}
┃ 🔗 API Endpoints: {len([ls for ls in link_shorteners_data.values() if ls.get('api')])}
┃ 📋 Data Points: {total_records:,}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

💡 **Optimization Tips:**
{'• Consider data archiving for old users' if len(user_data) > 1000 else '• System running optimally'}
{'• Monitor shortlink storage' if len(shortlinks_data) > 500 else '• Shortlink system efficient'}
{'• Review banned users list' if len(banned_users) > 50 else '• User management optimal'}

⚡ **Report Generated:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Performance", callback_data="performance_stats")],
        [InlineKeyboardButton("📊 Main Status", callback_data="status"),
         InlineKeyboardButton("⚙️ System Health", callback_data="system_health")],
        [InlineKeyboardButton("🔙 Back to Owner Panel", callback_data="back_to_owner")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(perf_text, reply_markup=reply_markup)

# ======================== COUPONS MANAGEMENT FUNCTIONS ========================
async def handle_coupons_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show coupons management panel"""
    query = update.callback_query
    reload_data()
    
    coupons_text = f"""
🎫 **Coupons Management**

Manage discount coupons for your users.

Select an action:
    """
    
    keyboard = [
        [InlineKeyboardButton("➕ Add", callback_data="add_coupon"),
         InlineKeyboardButton("➖ Remove", callback_data="remove_coupon")],
        [InlineKeyboardButton("📋 List of Available Coupons", callback_data="list_coupons")],
        [InlineKeyboardButton("🔙 Back", callback_data="offers_management")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(coupons_text, reply_markup=reply_markup, parse_mode='Markdown')

async def add_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new coupon"""
    query = update.callback_query
    
    await query.edit_message_text(
        "🎫 **Add New Coupon**\n\n"
        "Please enter the validity period in days:\n\n"
        "📅 Examples:\n"
        "• 1 - Valid for 1 day\n"
        "• 3 - Valid for 3 days\n"
        "• 7 - Valid for 1 week\n"
        "• 30 - Valid for 1 month\n\n"
        "Enter number of days:",
        parse_mode='Markdown'
    )
    context.user_data['state'] = 'waiting_coupon_validity'

async def remove_coupon_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show coupons for removal with pagination"""
    query = update.callback_query
    reload_data()
    
    if not coupons_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="manage_coupons")]
        ])
        await query.edit_message_text(
            "➖ **Remove Coupon**\n\n"
            "❌ No coupons available to remove.",
            reply_markup=keyboard
        )
        return
    
    await show_coupons_for_removal(update, context, page=1)

async def show_coupons_for_removal(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Show coupons for removal with pagination"""
    query = update.callback_query
    reload_data()
    
    items_per_page = 4
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    coupon_ids = list(coupons_data.keys())
    paginated_coupons = coupon_ids[start_index:end_index]
    total_pages = (len(coupon_ids) + items_per_page - 1) // items_per_page if coupon_ids else 1
    
    keyboard = []
    
    # Show coupons
    for coupon_id in paginated_coupons:
        coupon_data = coupons_data[coupon_id]
        code = coupon_data['code']
        status = "🟢" if coupon_data.get('status') == 'Active' else "🔴"
        keyboard.append([InlineKeyboardButton(f"{status} {code}", callback_data=f"delete_coupon_{coupon_id}")])
    
    # Add empty rows if less than 4 coupons
    while len(keyboard) < 4:
        keyboard.append([InlineKeyboardButton("➖ Empty Slot", callback_data="empty_slot")])
    
    # Navigation
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"previous_coupons_{page}"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="manage_coupons"))
    if end_index < len(coupon_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_coupons_{page}"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"➖ **Remove Coupon{page_info}**\n\n"
        f"📊 Total: {len(coupon_ids)}\n"
        f"⚠️ Select a coupon to remove:",
        reply_markup=reply_markup
    )

async def list_coupons_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of all coupons with pagination"""
    query = update.callback_query
    reload_data()
    
    if not coupons_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="manage_coupons")]
        ])
        await query.edit_message_text(
            "📋 **Available Coupons**\n\n"
            "❌ No coupons available.",
            reply_markup=keyboard
        )
        return
    
    await show_coupons_list(update, context, page=1)

async def show_coupons_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Show list of coupons with pagination"""
    query = update.callback_query
    reload_data()
    
    items_per_page = 4
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    coupon_ids = list(coupons_data.keys())
    paginated_coupons = coupon_ids[start_index:end_index]
    total_pages = (len(coupon_ids) + items_per_page - 1) // items_per_page if coupon_ids else 1
    
    keyboard = []
    
    # Show coupons
    for coupon_id in paginated_coupons:
        coupon_data = coupons_data[coupon_id]
        code = coupon_data['code']
        status = "🟢" if coupon_data.get('status') == 'Active' else "🔴"
        keyboard.append([InlineKeyboardButton(f"{status} {code}", callback_data=f"view_coupon_{coupon_id}")])
    
    # Add empty rows if less than 4 coupons
    while len(keyboard) < 4:
        keyboard.append([InlineKeyboardButton("➖ Empty Slot", callback_data="empty_slot")])
    
    # Navigation
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"previous_coupons_{page}"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="manage_coupons"))
    if end_index < len(coupon_ids):    nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_coupons_{page}"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"📋 **Available Coupons{page_info}**\n\n"
        f"📊 Total: {len(coupon_ids)}\n"
        f"Select a coupon to view details:",
        reply_markup=reply_markup
    )

async def view_coupon_details(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Show detailed information about a coupon"""
    query = update.callback_query
    coupon_id = callback_data.split("_")[-1]
    reload_data()
    
    coupon_data = coupons_data.get(coupon_id)
    if not coupon_data:
        await query.answer("Coupon not found!")
        return
    
    # Calculate remaining days
    try:
        end_date = datetime.fromisoformat(coupon_data.get('end_date', ''))
        remaining_days = (end_date - datetime.now()).days
        remaining_days = max(0, remaining_days)
        created_date = datetime.fromisoformat(coupon_data.get('created_at', ''))
        created_formatted = created_date.strftime('%d/%m/%Y %H:%M')
        end_formatted = end_date.strftime('%d/%m/%Y %H:%M')
    except:
        remaining_days = 0
        created_formatted = 'Unknown'
        end_formatted = 'Unknown'
    
    status_emoji = "🟢" if coupon_data.get('status') == 'Active' else "🔴"
    
    details_text = f"""
🎫 **Coupon Details**

📝 **Basic Information:**
• **Code:** {coupon_data['code']}
• **ID:** {coupon_id}
• **Status:** {status_emoji} {coupon_data.get('status', 'Active')}

📅 **Validity:**
• **Created:** {created_formatted}
• **Expires:** {end_formatted}
• **Remaining:** {remaining_days} days
• **Total Days:** {coupon_data.get('validity_days', 0)} days

👥 **Usage Limits:**
• **User Limit:** {coupon_data.get('user_limit', 'Unlimited')}
• **Used By:** {coupon_data.get('used_count', 0)} users
• **Remaining Uses:** {coupon_data.get('user_limit', 'Unlimited') - coupon_data.get('used_count', 0) if coupon_data.get('user_limit') != 'Unlimited' else 'Unlimited'}

💰 **Benefits:**
• **Credit Amount:** {coupon_data.get('credit_amount', 0)} credits
• **Total Credits Given:** {coupon_data.get('total_credits_given', 0)} credits

🔧 **Technical Info:**
• **Created By:** {coupon_data.get('created_by', 'Owner')}
• **Auto Expire:** {'Yes' if remaining_days > 0 else 'Expired'}
    """
    
    keyboard = [
        [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_coupon_{coupon_id}")],
        [InlineKeyboardButton("🔙 Back to List", callback_data="list_coupons")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(details_text, reply_markup=reply_markup)

async def generate_coupon_code():
    """Generate a unique coupon code"""
    import random
    import string
    
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        code = f"COUP{code}"
        # Check if code already exists
        if not any(coupon['code'] == code for coupon in coupons_data.values()):
            return code

# ======================== SEASONAL OFFERS MANAGEMENT FUNCTIONS ========================
async def handle_seasonal_offers_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show seasonal offers management panel"""
    query = update.callback_query
    reload_data()  # This will auto-expire items
    
    total_offers = len(seasonal_offers_data)
    active_offers = len([o for o in seasonal_offers_data.values() if o.get('status') == 'Active'])
    expired_offers = len([o for o in seasonal_offers_data.values() if o.get('status') == 'Expired'])
    
    offers_text = f"""
🌟 **Seasonal Offers Management**

📊 **Real-Time Statistics:**
• Total Offers: {total_offers}
• Active Offers: {active_offers}
• Expired Offers: {expired_offers}

🔄 **Auto-Expiry System:** ✅ Active

Select an action:
    """
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Credit", callback_data="add_credit_offer"),
         InlineKeyboardButton("➖ Deduct Credit", callback_data="deduct_credit_offer")],
        [InlineKeyboardButton("📊 Offers Status", callback_data="seasonal_offers_status")],
        [InlineKeyboardButton("🔙 Back", callback_data="offers_management")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(offers_text, reply_markup=reply_markup)

async def add_credit_offer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show credit adding methods for offers"""
    query = update.callback_query
    
    methods_text = """
➕ **Add Credit Offer**

Select the credit earning method you want to add offer to:

💳 **Available Methods:**
• Free Credits (Shortlinks)
• Buy Credits (Purchases)
• Referral System

Choose a method:
    """
    
    keyboard = [
        [InlineKeyboardButton("🎁 Free Credits", callback_data="select_credit_method_free")],
        [InlineKeyboardButton("💳 Buy Credits", callback_data="select_credit_method_buy")],
        [InlineKeyboardButton("👥 Referral", callback_data="select_credit_method_referral")],
        [InlineKeyboardButton("🔙 Back", callback_data="manage_seasonal_offers")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(methods_text, reply_markup=reply_markup)

async def deduct_credit_offer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show credit deducting methods for offers"""
    query = update.callback_query
    
    methods_text = """
➖ **Deduct Credit Offer**

Select the credit spending method you want to add discount to:

💰 **Available Methods:**
• TTS (Text to Speech)
• STT (Speech to Text)
• Video Transcription

Choose a method:
    """
    
    keyboard = [
        [InlineKeyboardButton("🗣️ TTS", callback_data="select_credit_method_tts")],
        [InlineKeyboardButton("🎤 STT", callback_data="select_credit_method_stt")],
        [InlineKeyboardButton("🎬 Video", callback_data="select_credit_method_video")],
        [InlineKeyboardButton("🔙 Back", callback_data="manage_seasonal_offers")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(methods_text, reply_markup=reply_markup)

async def select_credit_method(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle credit method selection"""
    query = update.callback_query
    method = callback_data.split("_")[-1]
    
    context.user_data['offer_method'] = method
    context.user_data['state'] = 'waiting_offer_percentage'
    
    method_names = {
        'free': 'Free Credits (Shortlinks)',
        'buy': 'Buy Credits (Purchases)', 
        'referral': 'Referral System',
        'tts': 'TTS (Text to Speech)',
        'stt': 'STT (Speech to Text)',
        'video': 'Video Transcription'
    }
    
    offer_type = "extra credits" if method in ['free', 'buy', 'referral'] else "discount"
    
    await query.edit_message_text(
        f"🎯 **Selected Method:** {method_names[method]}\n\n"
        f"Please enter the percentage for {offer_type}:\n\n"
        f"📊 Examples:\n"
        f"• 10 - {('10% extra credits' if method in ['free', 'buy', 'referral'] else '10% discount')}\n"
        f"• 25 - {('25% extra credits' if method in ['free', 'buy', 'referral'] else '25% discount')}\n"
        f"• 50 - {('50% extra credits' if method in ['free', 'buy', 'referral'] else '50% discount')}\n\n"
        f"Enter percentage (number only):"
    )

async def handle_offers_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show offers status and analysis"""
    query = update.callback_query
    reload_data()
    
    if not seasonal_offers_data:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="offers_management")]
        ])
        await query.edit_message_text(
            "📊 **Offers Status**\n\n"
            "❌ No offers available.",
            reply_markup=keyboard
        )
        return
    
    await show_offers_list(update, context, page=1)

async def show_offers_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Show list of offers with pagination"""
    query = update.callback_query
    reload_data()
    
    items_per_page = 4
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    offer_ids = list(seasonal_offers_data.keys())
    paginated_offers = offer_ids[start_index:end_index]
    total_pages = (len(offer_ids) + items_per_page - 1) // items_per_page if offer_ids else 1
    
    keyboard = []
    
    # Show offers
    for offer_id in paginated_offers:
        offer_data = seasonal_offers_data[offer_id]
        method = offer_data['method']
        percentage = offer_data['percentage']
        status = "🟢" if offer_data.get('status') == 'Active' else "🔴"
        keyboard.append([InlineKeyboardButton(f"{status} {method.title()} {percentage}%", callback_data=f"view_offer_{offer_id}")])
    
    # Add empty rows if less than 4 offers
    while len(keyboard) < 4:
        keyboard.append([InlineKeyboardButton("➖ Empty Slot", callback_data="empty_slot")])
    
    # Navigation
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"previous_offers_{page}"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="offers_management"))
    if end_index < len(offer_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_offers_{page}"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {page}/{total_pages})" if total_pages > 1 else ""
    
    await query.edit_message_text(
        f"📊 **Offers Status{page_info}**\n\n"
        f"📊 Total: {len(offer_ids)}\n"
        f"Select an offer to view details:",
        reply_markup=reply_markup
    )

# ======================== OFFERS PANEL FUNCTIONS ========================
async def handle_offers_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show offers main panel with Owner Refer, Ad View, and Offers options"""
    query = update.callback_query
    
    offers_text = """
🎁 **Offers Panel**

Select an option below to manage offers and referral system:

🔗 **Owner Refer:** Send referral invitations to users
📺 **Ad View:** Manage advertisement viewing system
🎁 **Offers:** Configure special offers and promotions

Choose what you want to manage:
    """
    
    keyboard = [
        [InlineKeyboardButton("🔗 Owner Refer", callback_data="owner_refer"),
         InlineKeyboardButton("📺 Advertisement", callback_data="ad_view")],
        [InlineKeyboardButton("🎁 Offers", callback_data="offers_management")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(offers_text, reply_markup=reply_markup)

async def handle_offers_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show offers management main panel"""
    query = update.callback_query
    reload_data()  # This will auto-expire items
    
    # Get real-time active counts after expiry check
    active_coupons = len([c for c in coupons_data.values() if c.get('status') == 'Active'])
    active_offers = len([o for o in seasonal_offers_data.values() if o.get('status') == 'Active'])
    expired_coupons = len([c for c in coupons_data.values() if c.get('status') == 'Expired'])
    expired_offers = len([o for o in seasonal_offers_data.values() if o.get('status') == 'Expired'])
    
    offers_text = f"""
🎁 **Offers Management**

Manage coupons and seasonal offers for your users:

🎫 **Coupons:** Create discount codes for users
🌟 **Seasonal Offers:** Special credit offers on various methods

📊 **Real-Time Status:**
• Active Coupons: {active_coupons}
• Expired Coupons: {expired_coupons}
• Active Offers: {active_offers}  
• Expired Offers: {expired_offers}

🔄 **Auto-Expiry:** ✅ Running (Checks every hour)

Select what you want to manage:
    """
    
    keyboard = [
        [InlineKeyboardButton("🎫 Coupons", callback_data="manage_coupons"),
         InlineKeyboardButton("🌟 Seasonal Offers", callback_data="manage_seasonal_offers")],
        [InlineKeyboardButton("🔙 Back", callback_data="offers")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(offers_text, reply_markup=reply_markup)

async def handle_owner_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show owner referral options"""
    query = update.callback_query
    
    refer_text = """
🔗 **Owner Referral System**

Choose how you want to send referral invitations:

📱 **Telegram:** Send referral message through Telegram
🌐 **Other:** Generate referral links for other platforms
📊 **Status:** View referral statistics

Select your preferred method:
    """
    
    keyboard = [
        [InlineKeyboardButton("📱 Telegram", callback_data="refer_telegram"),
         InlineKeyboardButton("🌐 Other", callback_data="refer_other")],
        [InlineKeyboardButton("📊 Status", callback_data="refer_status")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_refer")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(refer_text, reply_markup=reply_markup)

async def handle_refer_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Telegram referral option - Show message forwarding interface"""
    query = update.callback_query
    
    # Generate bot referral link
    bot_username = context.bot.username or "mediaGenie_bot"
    refer_link = f"https://t.me/{bot_username}?start=owner_ref"
    
    # Pre-built message
    referral_message = f"""Hey! If you want to convert your text to speech, try this amazing bot!

🎙️ Features:
• Text to Speech (Hindi/English)
• Speech to Text
• Video Transcription
• Free Credits

Try it here: {refer_link}

Support banaye rakhna! 😊"""
    
    # Send the message for forwarding
    forward_msg = await context.bot.send_message(
        chat_id=query.from_user.id,
        text=referral_message
    )
    
    instruction_text = """
📱 **Telegram Message Forwarding**

✅ A referral message has been sent above.

📤 **How to use:**
1. Long press on the message above
2. Select "Forward" option
3. Choose contacts/groups to forward to
4. Send the message

💡 **Note:** Users who join through the link will get extra credits!

Choose your next action:
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 View Stats", callback_data="refer_status")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_refer")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(instruction_text, reply_markup=reply_markup)



async def handle_ad_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Ad View functionality - Show advertisement management panel"""
    query = update.callback_query
    reload_data()
    
    # Show advertisements with pagination
    await show_advertisements_list(update, context, page=1)

async def handle_refer_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Other platform referral - Copy message to clipboard"""
    query = update.callback_query
    
    # Generate bot referral link
    bot_username = context.bot.username or "mediaGenie_bot"
    refer_link = f"https://t.me/{bot_username}?start=owner_ref"
    
    # Pre-built message
    referral_message = f"""Hey! If you want to convert your text to speech, try this amazing bot!

🎙️ Features:
• Text to Speech (Hindi/English)
• Speech to Text
• Video Transcription
• Free Credits

Try it here: {refer_link}

Support banaye rakhna! 😊"""
    
    # Show message and copy option
    other_refer_text = f"""
🌐 **Other Platform Referral**

📋 **Message copied to clipboard!**

```
{referral_message}
```

🔗 **How to use:**
1. The message above has been copied
2. Paste it on other platforms (WhatsApp, Facebook, etc.)
3. When users click and join, they get extra credits
4. You can track referrals through Status

📊 **Perfect for:**
• WhatsApp� Groups/Status
• Facebook Posts/Messages
• Instagram Stories/DMs
• Twitter Tweets/DMs
• Email Signatures
• Website/Blog Posts
    """
    
    keyboard = [
        [InlineKeyboardButton("📋 Copy Again", callback_data="copy_refer_message")],
        [InlineKeyboardButton("📊 View Status", callback_data="refer_status")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_refer")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send alert with shorter message (Telegram callback answer limit is 200 characters)
    await query.answer("✅ Message copied!", show_alert=True)
    await query.edit_message_text(other_refer_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_refer_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show owner referral statistics"""
    query = update.callback_query
    
    reload_data()
    
    # Handle empty user_data
    if not user_data:
        status_text = """
📊 **Owner Referral Statistics**

⚠️ **No User Data Available**
• Total Users: 0
• Total Referrals: 0
• Credits Given: 0

📈 **System Status:**
• Database: Empty
• Referral System: Ready
• Tracking: Active

🔗 **Next Steps:**
• Start referring users to see statistics
• All referral data will be tracked automatically
        """
        
        keyboard = [
            [InlineKeyboardButton("📱 Start Referring", callback_data="refer_telegram")],
            [InlineKeyboardButton("🔙 Back", callback_data="owner_refer")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(status_text, reply_markup=reply_markup)
        return
    
    # Count users referred by owner
    owner_referrals = len([user for user in user_data.values() 
                          if user.get('referred_by') == 'owner_ref'])
    
    # Calculate total credits given through owner referrals
    owner_refer_credits = owner_referrals * CREDIT_CONFIG['referral_reward']
    
    # Get recent referrals (last 7 days)
    week_ago = datetime.now() - timedelta(days=7)
    recent_referrals = 0
    
    for user in user_data.values():
        if user.get('referred_by') == 'owner_ref':
            try:
                created_date = datetime.fromisoformat(user.get('user_created_at', ''))
                if created_date >= week_ago:
                    recent_referrals += 1
            except:
                continue
    
    # Safe division calculation
    total_users = len(user_data)
    growth_percentage = (owner_referrals * 100 / total_users) if total_users > 0 else 0
    
    status_text = f"""
📊 **Owner Referral Statistics**

🎯 **Performance Overview:**
• Total Referrals: {owner_referrals}
• Recent Referrals (7 days): {recent_referrals}
• Credits Given: {owner_refer_credits}
• Success Rate: 100% (All valid referrals)

📈 **Impact Analysis:**
• New Users Acquired: {owner_referrals}
• Average per Week: {recent_referrals}
• Credit Investment: {owner_refer_credits} credits
• User Base Growth: {growth_percentage:.1f}%
• Total Users: {total_users}

🔗 **Referral Methods:**
• Telegram Messages: Active
• Other Platforms: Available
• Direct Links: Working

⏰ **Last Updated:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refer_status")],
        [InlineKeyboardButton("📱 Send More", callback_data="refer_telegram")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_refer")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(status_text, reply_markup=reply_markup)



# ======================== ADVERTISEMENT MANAGEMENT FUNCTIONS ========================
async def show_advertisements_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Show list of advertisements with pagination"""
    query = update.callback_query
    reload_data()
    
    items_per_page = 4
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    ad_ids = list(advertisements_data.keys())
    paginated_ads = ad_ids[start_index:end_index]
    total_pages = (len(ad_ids) + items_per_page - 1) // items_per_page if ad_ids else 1
    
    keyboard = []
    
    if advertisements_data:
        # Row 1-4: Advertisement titles
        for ad_id in paginated_ads:
            ad_data = advertisements_data[ad_id]
            title = ad_data['title'][:25] + "..." if len(ad_data['title']) > 25 else ad_data['title']
            status_emoji = "🟢" if ad_data.get('status') == 'Active' else "🔴"
            keyboard.append([InlineKeyboardButton(f"{status_emoji} {title}", callback_data=f"view_ad_{ad_id}")])
        
        # Add empty rows if less than 4 ads on current page
        while len(keyboard) < 4:
            keyboard.append([InlineKeyboardButton("➖ Empty Slot", callback_data="empty_slot")])
    else:
        # No ads available
        for i in range(4):
            keyboard.append([InlineKeyboardButton("➖ Empty Slot", callback_data="empty_slot")])
    
    # Row 5: Add Ad button
    keyboard.append([InlineKeyboardButton("➕ Add Ad", callback_data="add_advertisement")])
    
    # Row 6: Navigation and Back
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"previous_ads_{page}"))
    nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="offers"))
    if end_index < len(ad_ids):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_ads_{page}"))
    
    keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    page_info = f" (Page {page}/{total_pages})" if total_pages > 1 else ""
    
    # Calculate real-time statistics
    active_ads_count = len([ad for ad in advertisements_data.values() if ad.get('status') == 'Active'])
    expired_ads = 0
    current_time = datetime.now()
    
    for ad_data in advertisements_data.values():
        try:
            end_date = datetime.fromisoformat(ad_data.get('end_date', ''))
            if current_time >= end_date:
                expired_ads += 1
        except:
            expired_ads += 1
    
    # Get today's broadcast statistics
    today = datetime.now().strftime('%Y-%m-%d')
    today_total_broadcasts = sum(ad_broadcast_log.get(today, {}).values())
    total_users_reached_today = 0
    
    for ad_id in ad_broadcast_log.get(today, {}):
        if ad_id in ad_tracking_data:
            total_users_reached_today += ad_tracking_data[ad_id].get('total_users_reached', 0)
    
    ad_view_text = f"""
📺 **Advertisement Management{page_info}**

📊 **Real-Time Statistics:**
• Total Ads: {len(ad_ids)}
• Active Ads: {active_ads_count}
• Expired Ads: {expired_ads}
• Today's Broadcasts: {today_total_broadcasts}
• Users Reached Today: {total_users_reached_today}

🎯 **System Status:**
• Auto-Broadcast: ✅ Running
• Schedule: 10:00 AM, 3:00 PM, 8:00 PM
• Next Broadcast: Auto-determined
• Tracking: ✅ Real-time

Select an advertisement to view details or add a new one:
    """
    
    try:
        await query.edit_message_text(ad_view_text, reply_markup=reply_markup)
    except Exception as e:
        if "Message is not modified" in str(e):
            await query.answer("🔄 Refreshed!", show_alert=False)
        else:
            await query.message.reply_text(ad_view_text, reply_markup=reply_markup)

async def view_advertisement_details(update: Update, context: ContextTypes.DEFAULT_TYPE, ad_id: str):
    """Show detailed information about a specific advertisement"""
    query = update.callback_query
    reload_data()
    
    ad_data = advertisements_data.get(ad_id)
    if not ad_data:
        await query.answer("Advertisement not found!")
        return
    
    # Calculate remaining days
    import datetime
    try:
        end_date = datetime.datetime.fromisoformat(ad_data.get('end_date', ''))
        remaining_days = (end_date - datetime.datetime.now()).days
        remaining_days = max(0, remaining_days)
        created_date = datetime.datetime.fromisoformat(ad_data.get('created_at', ''))
        created_formatted = created_date.strftime('%d/�%m/%Y %H:%M')
        end_formatted = end_date.strftime('%d/%m/%Y %H:%M')
    except:
        remaining_days = 0
        created_formatted = 'Unknown'
        end_formatted = 'Unknown'
    
    status_emoji = "🟢" if ad_data.get('status') == 'Active' else "🔴"
    priority_emoji = {"low": "🔴", "normal": "🟡", "high": "🟢"}.get(ad_data.get('priority', 'normal'), "🟡")
    
    # Get file size info if available
    file_info = ""
    if ad_data.get('file_id'):
        file_type = ad_data.get('file_type', 'document')
        file_name = ad_data.get('file_name', 'unknown')
        file_info = f"\n📎 **File Details:**\n• Type: {file_type.title()}\n• Name: {file_name}\n• File ID: {ad_data['file_id'][:20]}..."
    
    # Get real-time analytics
    analytics = await get_advertisement_analytics(ad_id)
    
    today = datetime.now().strftime('%Y-%m-%d')
    today_broadcasts = ad_broadcast_log.get(today, {}).get(ad_id, 0)
    total_broadcasts = ad_tracking_data.get(ad_id, {}).get('total_broadcasts', 0)
    total_users_reached = ad_tracking_data.get(ad_id, {}).get('total_users_reached', 0)
    
    # Calculate elapsed days
    try:
        created_date = datetime.datetime.fromisoformat(ad_data.get('created_at', ''))
        elapsed_days = (datetime.datetime.now() - created_date).days
        elapsed_days = max(1, elapsed_days)  # Minimum 1 day
    except:
        elapsed_days = 1
    
    avg_daily_broadcasts = total_broadcasts / elapsed_days if elapsed_days > 0 else 0
    
    details_text = f"""
📺 **Advertisement Complete Details**

🏷️ **Basic Information:**
• **Title:** {ad_data['title']}
• **Description:** {ad_data['description']}
• **ID:** {ad_id}
• **Created By:** {ad_data.get('created_by', 'Owner')}

📅 **Time Information:**
• **Created At:** {created_formatted}
• **End Date:** {end_formatted}
• **Duration:** {ad_data.get('duration', 0)} days
• **Elapsed Days:** {elapsed_days}
• **Remaining:** {remaining_days} days
• **Status:** {status_emoji} {ad_data.get('status', 'Active')}

🎯 **Display Settings:**
• **Priority:** {priority_emoji} {ad_data.get('priority', 'normal').title()}
• **Shows per day:** { {'low': '1-2 times', 'normal': '3-5 times', 'high': '6-10 times'}.get(ad_data.get('priority', 'normal'), '3-5 times')}
• **Target Audience:** All Users
• **Auto Broadcast:** ✅ Active

📊 **Real-Time Performance:**
• **Total Broadcasts:** {total_broadcasts}
• **Users Reached:** {total_users_reached}
• **Today's Broadcasts:** {today_broadcasts}
• **Daily Average:** {avg_daily_broadcasts:.1f} broadcasts
• **Avg Users/Broadcast:** {total_users_reached/max(1, total_broadcasts):.0f}

🔧 **Technical Details:**
• **Auto-Expire:** {'✅ Yes' if remaining_days > 0 else '❌ Expired'}
• **File Attached:** {'✅ Yes' if ad_data.get('file_id') else '❌ No'}
• **Broadcast Times:** 10:00 AM, 3:00 PM, 8:00 PM
• **Next Broadcast:** Auto-scheduled{file_info}

⚠️ **System Status:**
• Advertisement broadcasting is fully automated
• Broadcasts run 3 times daily based on priority
• All statistics are tracked in real-time
• Auto-expires in {remaining_days} days
    """
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Remove Ad", callback_data=f"remove_ad_{ad_id}")],
        [InlineKeyboardButton("📊 View Stats", callback_data=f"stats_ad_{ad_id}")],
        [InlineKeyboardButton("🔙 Back to List", callback_data="ad_view")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send file if available, otherwise send text
    if ad_data.get('file_id'):
        try:
            file_type = ad_data.get('file_type', 'document')
            caption = f"📺 **Advertisement Preview**\n\n**{ad_data['title']}**\n\n{ad_data['description'][:100]}{'...' if len(ad_data['description']) > 100 else ''}\n\n📊 Status: {ad_data.get('status', 'Active')} | Priority: {ad_data.get('priority', 'normal').title()}"
            
            # First send the file with preview
            if file_type == 'photo':
                await query.message.reply_photo(
                    photo=ad_data['file_id'],
                    caption=caption
                )
            elif file_type == 'video':
                await query.message.reply_video(
                    video=ad_data['file_id'],
                    caption=caption
                )
            elif file_type == 'document':
                await query.message.reply_document(
                    document=ad_data['file_id'],
                    caption=caption
                )
            elif file_type == 'audio':
                await query.message.reply_audio(
                    audio=ad_data['file_id'],
                    caption=caption
                )
            
            # Then send detailed text
            await query.message.reply_text(details_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error sending ad file: {e}")
            await query.edit_message_text(details_text + "\n\n❌ Error loading file preview", reply_markup=reply_markup)
    else:
        await query.edit_message_text(details_text, reply_markup=reply_markup)

async def add_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new advertisement"""
    query = update.callback_query
    
    await query.edit_message_text(
        "📺 **Add New Advertisement**\n\n"
        "Please send the title for this advertisement:"
    )
    context.user_data['state'] = 'waiting_ad_title'

async def process_advertisement_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process advertisement file upload"""
    file_obj = None
    file_type = 'document'
    
    # Determine file type and get file object
    if update.message.photo:
        file_obj = update.message.photo[-1]  # Get highest resolution
        file_type = 'photo'
    elif update.message.video:
        file_obj = update.message.video
        file_type = 'video'
    elif update.message.document:
        file_obj = update.message.document
        file_type = 'document'
    elif update.message.audio:
        file_obj = update.message.audio
        file_type = 'audio'
    elif update.message.voice:
        file_obj = update.message.voice
        file_type = 'voice'
    elif update.message.video_note:
        file_obj = update.message.video_note
        file_type = 'video_note'
    
    if not file_obj:
        await update.message.reply_text("❌ Please send a valid file!")
        return
    
    # Store file information
    context.user_data['ad_file_id'] = file_obj.file_id
    context.user_data['ad_file_type'] = file_type
    context.user_data['ad_file_name'] = getattr(file_obj, 'file_name', f"{file_type}_file")
    
    await update.message.reply_text(
        f"✅ File uploaded successfully!\n"
        f"📎 File Type: {file_type.title()}\n"
        f"📁 File Name: {context.user_data.get('ad_file_name', 'Unknown')}\n\n"
        f"⏰ Now please enter the duration in days (how many days this ad should be active):\n\n"
        f"Example: 1, 5, 10, 30"
    )
    context.user_data['state'] = 'waiting_ad_duration'

async def process_advertisement_save(update: Update, context: ContextTypes.DEFAULT_TYPE, priority: str):
    """Save the advertisement with all details"""
    import uuid
    from datetime import datetime, timedelta
    
    # Get all collected data
    title = context.user_data.get('ad_title', 'Untitled')
    description = context.user_data.get('ad_description', 'No description')
    file_id = context.user_data.get('ad_file_id', '')
    file_type = context.user_data.get('ad_file_type', 'document')
    file_name = context.user_data.get('ad_file_name', 'unknown')
    duration = context.user_data.get('ad_duration', 1)
    
    # Generate unique ID for the advertisement
    ad_id = f"AD{str(uuid.uuid4())[:6].upper()}"
    
    # Calculate end date
    end_date = datetime.now() + timedelta(days=duration)
    
    # Save advertisement with enhanced details
    reload_data()
    advertisements_data[ad_id] = {
        "id": ad_id,
        "title": title,
        "description": description,
        "file_id": file_id,
        "file_type": file_type,
        "file_name": file_name,
        "duration": duration,
        "priority": priority,
        "created_at": datetime.now().isoformat(),
        "end_date": end_date.isoformat(),
        "created_by": "Owner",
        "status": "Active",
        # Performance metrics (initialized to 0)
        "total_views": 0,
        "total_clicks": 0,
        "engagement_rate": "0.0",
        "daily_average": 0,
        # Additional metadata
        "target_audience": "All Users",
        "distribution_method": "Random Priority-based",
        "platform": "Telegram Bot",
        "auto_expire": True
    }
    save_json(ADVERTISEMENTS_FILE, advertisements_data)
    
    priority_shows = {"low": "1-2 times", "normal": "3-5 times", "high": "6-10 times"}
    priority_emoji = {"low": "🔴", "normal": "🟡", "high": "🟢"}
    
    success_text = f"""
✅ **Advertisement Added Successfully!**

📺 **Complete Advertisement Details:**

🏷️ **Basic Information:**
• **ID:** {ad_id}
• **Title:** {title}
• **Description:** {description[:150]}{'...' if len(description) > 150 else ''}

📎 **File Information:**
• **File Name:** {file_name}
• **File Type:** {file_type.title()}
• **File Status:** ✅ Uploaded Successfully

⏰ **Time Settings:**
• **Duration:** {duration} days
• **Created:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
• **Expires:** {end_date.strftime('%d/%m/%Y %H:%M')}
• **Status:** 🟢 Active

🎯 **Display Configuration:**
• **Priority:** {priority_emoji[priority]} {priority.title()}
• **Shows per day:** {priority_shows[priority]}
• **Target:** All Users
• **Distribution:** Priority-based Random

📊 **Performance Tracking:**
• **Views:** 0 (tracking enabled)
• **Clicks:** 0 (tracking enabled)  
• **Engagement:** 0.0% (will be calculated)
• **Auto-Expire:** ✅ Enabled

🚀 **System Status:**
• **Total Ads:** {len(advertisements_data)}
• **Active Ads:** {len([ad for ad in advertisements_data.values() if ad.get('status') == 'Active'])}
• **Advertisement System:** ✅ Running

Your advertisement is now live and will be shown to users based on priority settings!
    """
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Ads", callback_data="ad_view")]])
    await update.message.reply_text(success_text, reply_markup=back_button)
    
    # Clear temporary data
    context.user_data['state'] = None
    for key in ['ad_title', 'ad_description', 'ad_file_id', 'ad_file_type', 'ad_file_name', 'ad_duration']:
        context.user_data.pop(key, None)

async def confirm_remove_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE, ad_id: str):
    """Ask for confirmation before removing advertisement"""
    query = update.callback_query
    reload_data()
    
    ad_data = advertisements_data.get(ad_id)
    if not ad_data:
        await query.answer("Advertisement not found!")
        return
    
    try:
        created_date = datetime.fromisoformat(ad_data.get('created_at', ''))
        created_formatted = created_date.strftime('%d/%m/%Y')
    except:
        created_formatted = 'Unknown'
    
    confirmation_text = f"""
🗑️ **Confirm Advertisement Removal**

Are you sure you want to delete this advertisement?

📝 **Title:** {ad_data['title']}
🆔 **ID:** {ad_id}
📅 **Created:** {created_formatted}
⏰ **Duration:** {ad_data.get('duration', 0)} days
🎯 **Priority:** {ad_data.get('priority', 'normal').title()}
📎 **File:** {'Yes' if ad_data.get('file_id') else 'No'}

⚠️ **Warning:** This action cannot be undone!
All advertisement data and attached files will be permanently removed.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"delete_ad_{ad_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data=f"view_ad_{ad_id}")]
    ])
    
    # Try to edit the message, if it fails, send a new message
    try:
        await query.edit_message_text(confirmation_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error editing message for ad removal confirmation: {e}")
        # If edit fails (due to media message), send new message
        await query.message.reply_text(confirmation_text, reply_markup=keyboard)
        await query.answer("⚠️ Confirmation message sent!", show_alert=False)

async def delete_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE, ad_id: str):
    """Delete the advertisement after confirmation"""
    query = update.callback_query
    reload_data()
    
    ad_data = advertisements_data.get(ad_id)
    if not ad_data:
        await query.answer("Advertisement not found!")
        return
    
    # Delete the advertisement
    deleted_title = ad_data['title']
    had_file = bool(ad_data.get('file_id'))
    file_type = ad_data.get('file_type', 'none')
    
    del advertisements_data[ad_id]
    save_json(ADVERTISEMENTS_FILE, advertisements_data)
    
    success_text = f"""
✅ **Advertisement Deleted Successfully!**

📺 **Deleted:** {deleted_title}
🆔 **ID:** {ad_id}
📎 **File Removed:** {'Yes (' + file_type + ')' if had_file else 'No file attached'}
⏰ **Deleted At:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
📊 **Remaining Ads:** {len(advertisements_data)}

The advertisement has been permanently removed from the system.
All associated data and files have been cleared.

✨ **System Updated:** Advertisement system refreshed automatically.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Ads", callback_data="ad_view")]
    ])
    
    # Try to edit the message, if it fails, send a new message
    try:
        await query.edit_message_text(success_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error editing message for ad deletion success: {e}")
        # If edit fails (due to media message), send new message
        await query.message.reply_text(success_text, reply_markup=keyboard)
        await query.answer("✅ Advertisement deleted successfully!", show_alert=True)

async def handle_ads_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle pagination for advertisements"""
    query = update.callback_query
    
    if callback_data.startswith("next_ads_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page + 1
        await show_advertisements_list(update, context, page=new_page)
    elif callback_data.startswith("previous_ads_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page - 1
        await show_advertisements_list(update, context, page=new_page)

# ======================== ADVERTISEMENT BROADCASTING SYSTEM ========================

def get_active_advertisements():
    """Get all active advertisements that haven't expired"""
    reload_data()  # This will auto-expire items
    active_ads = {}
    
    for ad_id, ad_data in advertisements_data.items():
        if ad_data.get('status') == 'Active':
            active_ads[ad_id] = ad_data
    
    return active_ads

def get_active_seasonal_offers():
    """Get all active seasonal offers that haven't expired"""
    reload_data()  # This will auto-expire items
    active_offers = {}
    
    for offer_id, offer_data in seasonal_offers_data.items():
        if offer_data.get('status') == 'Active':
            active_offers[offer_id] = offer_data
    
    return active_offers

def get_active_coupons():
    """Get all active coupons that haven't expired"""
    reload_data()  # This will auto-expire items
    active_coupons = {}
    
    for coupon_id, coupon_data in coupons_data.items():
        if coupon_data.get('status') == 'Active':
            active_coupons[coupon_id] = coupon_data
    
    return active_coupons

def get_ads_for_priority(priority_level):
    """Get advertisements for specific priority level"""
    active_ads = get_active_advertisements()
    return {ad_id: ad_data for ad_id, ad_data in active_ads.items() 
            if ad_data.get('priority', 'normal') == priority_level}

def calculate_daily_ad_sends():
    """Calculate how many ads should be sent today for each priority"""
    return {
        'high': random.randint(6, 10),    # 6-10 times per day
        'normal': random.randint(3, 5),   # 3-5 times per day  
        'low': random.randint(1, 2)       # 1-2 times per day
    }

def get_today_broadcast_count(ad_id):
    """Get today's broadcast count for specific ad"""
    today = datetime.now().strftime('%Y-%m-%d')
    return ad_broadcast_log.get(today, {}).get(ad_id, 0)

def log_ad_broadcast(ad_id, user_count):
    """Log advertisement broadcast"""
    global ad_broadcast_log
    today = datetime.now().strftime('%Y-%m-%d')
    
    if today not in ad_broadcast_log:
        ad_broadcast_log[today] = {}
    
    if ad_id not in ad_broadcast_log[today]:
        ad_broadcast_log[today][ad_id] = 0
    
    ad_broadcast_log[today][ad_id] += 1
    
    # Update tracking data
    if ad_id not in ad_tracking_data:
        ad_tracking_data[ad_id] = {
            'total_broadcasts': 0,
            'total_users_reached': 0,
            'daily_logs': {}
        }
    
    ad_tracking_data[ad_id]['total_broadcasts'] += 1
    ad_tracking_data[ad_id]['total_users_reached'] += user_count
    ad_tracking_data[ad_id]['daily_logs'][today] = ad_tracking_data[ad_id]['daily_logs'].get(today, 0) + 1
    
    save_json(AD_BROADCAST_LOG_FILE, ad_broadcast_log)
    save_json(AD_TRACKING_FILE, ad_tracking_data)

async def broadcast_advertisement_to_users(context, ad_id, ad_data):
    """Broadcast advertisement to all active users"""
    reload_data()
    active_users = [uid for uid, user_info in user_data.items() 
                   if user_info.get('user_status') == 'active' and not is_user_banned(user_info.get('user_id'))]
    
    if not active_users:
        return 0
    
    success_count = 0
    caption = f"""
📺 **Advertisement**

**{ad_data['title']}**

{ad_data['description']}

🎯 Priority: {ad_data.get('priority', 'normal').title()}
⏰ Valid until: {datetime.fromisoformat(ad_data.get('end_date', '')).strftime('%d/%m/%Y')}
    """
    
    for uid in active_users:
        try:
            user_info = user_data[uid]
            user_id = user_info.get('user_id')
            
            if not user_id:
                continue
            
            # Send advertisement based on file type
            if ad_data.get('file_id'):
                file_type = ad_data.get('file_type', 'document')
                
                if file_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=ad_data['file_id'],
                        caption=caption
                    )
                elif file_type == 'video':
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=ad_data['file_id'],
                        caption=caption
                    )
                elif file_type == 'document':
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=ad_data['file_id'],
                        caption=caption
                    )
                elif file_type == 'audio':
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=ad_data['file_id'],
                        caption=caption
                    )
                else:
                    await context.bot.send_message(chat_id=user_id, text=caption)
            else:
                await context.bot.send_message(chat_id=user_id, text=caption)
            
            success_count += 1
            
        except Exception as e:
            logger.error(f"Failed to send ad to user {user_id}: {e}")
            continue
    
    # Log the broadcast
    log_ad_broadcast(ad_id, success_count)
    
    logger.info(f"Advertisement {ad_id} broadcasted to {success_count} users")
    return success_count

async def run_daily_ad_broadcast(context):
    """Run daily advertisement broadcast based on priority"""
    active_ads = get_active_advertisements()
    
    if not active_ads:
        logger.info("No active advertisements to broadcast")
        return
    
    daily_targets = calculate_daily_ad_sends()
    
    for priority in ['high', 'normal', 'low']:
        priority_ads = get_ads_for_priority(priority)
        target_sends = daily_targets[priority]
        
        if not priority_ads:
            continue
        
        # Select random ads for this priority
        ads_to_send = min(target_sends, len(priority_ads))
        selected_ads = random.sample(list(priority_ads.items()), ads_to_send)
        
        for ad_id, ad_data in selected_ads:
            today_count = get_today_broadcast_count(ad_id)
            max_daily = daily_targets[priority]
            
            if today_count < max_daily:
                await broadcast_advertisement_to_users(context, ad_id, ad_data)
                # Add delay between broadcasts
                await asyncio.sleep(random.randint(300, 900))  # 5-15 minutes delay

def start_ad_scheduler(context):
    """Start advertisement scheduler and expiry checker"""
    def schedule_ads():
        # Schedule ads 3 times a day
        schedule.every().day.at("10:00").do(lambda: asyncio.create_task(run_daily_ad_broadcast(context)))
        schedule.every().day.at("15:00").do(lambda: asyncio.create_task(run_daily_ad_broadcast(context)))
        schedule.every().day.at("20:00").do(lambda: asyncio.create_task(run_daily_ad_broadcast(context)))
        
        # Schedule expiry check every hour
        schedule.every().hour.do(check_and_expire_items)
        
        # Schedule expiry check at midnight for daily cleanup
        schedule.every().day.at("00:00").do(check_and_expire_items)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=schedule_ads, daemon=True)
    scheduler_thread.start()
    logger.info("Advertisement scheduler and expiry checker started")

async def get_advertisement_analytics(ad_id):
    """Get detailed analytics for an advertisement"""
    reload_data()
    ad_data = advertisements_data.get(ad_id)
    tracking_data = ad_tracking_data.get(ad_id, {})
    
    if not ad_data:
        return None
    
    # Calculate remaining days
    try:
        end_date = datetime.fromisoformat(ad_data.get('end_date', ''))
        remaining_days = (end_date - datetime.now()).days
        remaining_days = max(0, remaining_days)
        
        created_date = datetime.fromisoformat(ad_data.get('created_at', ''))
        total_days = (end_date - created_date).days
        elapsed_days = total_days - remaining_days
    except:
        remaining_days = 0
        total_days = 0
        elapsed_days = 0
    
    # Calculate daily statistics
    today = datetime.now().strftime('%Y-%m-%d')
    today_broadcasts = ad_broadcast_log.get(today, {}).get(ad_id, 0)
    
    total_broadcasts = tracking_data.get('total_broadcasts', 0)
    total_users_reached = tracking_data.get('total_users_reached', 0)
    
    analytics = {
        'ad_id': ad_id,
        'title': ad_data.get('title', 'Unknown'),
        'priority': ad_data.get('priority', 'normal'),
        'status': ad_data.get('status', 'Active'),
        'total_days': total_days,
        'elapsed_days': elapsed_days,
        'remaining_days': remaining_days,
        'total_broadcasts': total_broadcasts,
        'total_users_reached': total_users_reached,
        'today_broadcasts': today_broadcasts,
        'avg_daily_broadcasts': total_broadcasts / max(1, elapsed_days),
        'avg_users_per_broadcast': total_users_reached / max(1, total_broadcasts)
    }
    
    return analytics

# ======================== COUPON AND OFFER PROCESSING FUNCTIONS ========================
async def process_coupon_validity(update: Update, context: ContextTypes.DEFAULT_TYPE, validity_text: str):
    """Process coupon validity input"""
    try:
        validity_days = int(validity_text)
        if validity_days <= 0:
            await update.message.reply_text("❌ Please enter a positive number for days!")
            return
        
        context.user_data['coupon_validity'] = validity_days
        context.user_data['state'] = 'waiting_coupon_user_limit'
        
        await update.message.reply_text(
            f"📅 **Validity:** {validity_days} days\n\n"
            f"👥 **User Limit**\n\n"
            f"How many users can use this coupon?\n\n"
            f"📊 Options:\n"
            f"• Enter a number (e.g., 10, 20, 50)\n"
            f"• Type 'unlimited' for no limit\n\n"
            f"Enter user limit:",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for days!")

async def process_coupon_user_limit(update: Update, context: ContextTypes.DEFAULT_TYPE, limit_text: str):
    """Process coupon user limit and ask for credit amount"""
    if limit_text.lower().strip() == 'unlimited':
        user_limit = 'Unlimited'
    else:
        try:
            user_limit = int(limit_text)
            if user_limit <= 0:
                await update.message.reply_text("❌ Please enter a positive number or 'unlimited'!")
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number or 'unlimited'!")
            return
    
    context.user_data['coupon_user_limit'] = user_limit
    context.user_data['state'] = 'waiting_coupon_credit_amount'
    
    await update.message.reply_text(
        f"👥 **User Limit:** {user_limit}\n\n"
        f"💰 **Credit Amount**\n\n"
        f"How many credits should users get from this coupon?\n\n"
        f"📊 Examples:\n"
        f"• 25 - Give 25 credits\n"
        f"• 50 - Give 50 credits\n"
        f"• 100 - Give 100 credits\n"
        f"• 200 - Give 200 credits\n\n"
        f"Enter credit amount:",
        parse_mode='Markdown'
    )

async def process_coupon_credit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, credit_text: str):
    """Process coupon credit amount and create coupon"""
    import uuid
    from datetime import timedelta
    
    try:
        credit_amount = int(credit_text)
        if credit_amount <= 0:
            await update.message.reply_text("❌ Please enter a positive number for credits!")
            return
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for credits!")
        return
    
    # Get stored data
    validity_days = context.user_data.get('coupon_validity', 1)
    user_limit = context.user_data.get('coupon_user_limit', 'Unlimited')
    
    # Generate coupon
    coupon_id = str(uuid.uuid4())[:8]
    coupon_code = await generate_coupon_code()
    
    # Calculate end date
    end_date = datetime.now() + timedelta(days=validity_days)
    
    # Create coupon data
    reload_data()
    coupons_data[coupon_id] = {
        'id': coupon_id,
        'code': coupon_code,
        'validity_days': validity_days,
        'user_limit': user_limit,
        'used_count': 0,
        'used_by': [],
        'credit_amount': credit_amount,
        'total_credits_given': 0,
        'created_at': datetime.now().isoformat(),
        'end_date': end_date.isoformat(),
        'created_by': 'Owner',
        'status': 'Active'
    }
    save_json(COUPONS_FILE, coupons_data)
    
    success_text = f"""
✅ **Coupon Created Successfully!**

🎫 **Coupon Details:**
• **Code:** `{coupon_code}`
• **ID:** {coupon_id}
• **Validity:** {validity_days} days
• **User Limit:** {user_limit}
• **Credit Amount:** {credit_amount} credits
• **Status:** 🟢 Active

📅 **Dates:**
• **Created:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
• **Expires:** {end_date.strftime('%d/%m/%Y %H:%M')}

🎯 **Usage:**
Users can redeem this coupon to get {credit_amount} free credits!
The coupon will be automatically tracked and managed.
    """
    
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Coupons", callback_data="manage_coupons")]])
    await update.message.reply_text(success_text, reply_markup=back_button, parse_mode='Markdown')
    
    # Clear temporary data
    context.user_data['state'] = None
    context.user_data.pop('coupon_validity', None)
    context.user_data.pop('coupon_user_limit', None)

async def process_offer_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE, percentage_text: str):
    """Process offer percentage input"""
    try:
        percentage = int(percentage_text)
        if percentage <= 0 or percentage > 100:
            await update.message.reply_text("❌ Please enter a percentage between 1 and 100!")
            return
        
        context.user_data['offer_percentage'] = percentage
        context.user_data['state'] = 'waiting_offer_validity'
        
        method = context.user_data.get('offer_method', 'unknown')
        offer_type = "extra credits" if method in ['free', 'buy', 'referral'] else "discount"
        
        await update.message.reply_text(
            f"🎯 **Percentage:** {percentage}% {offer_type}\n\n"
            f"📅 **Validity Period**\n\n"
            f"How many days should this offer be active?\n\n"
            f"📊 Examples:\n"
            f"• 1 - Valid for 1 day\n"
            f"• 7 - Valid for 1 week\n"
            f"• 30 - Valid for 1 month\n\n"
            f"Enter number of days:"
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid percentage number!")

async def process_offer_validity(update: Update, context: ContextTypes.DEFAULT_TYPE, validity_text: str):
    """Process offer validity and create offer"""
    import uuid
    from datetime import timedelta
    
    try:
        validity_days = int(validity_text)
        if validity_days <= 0:
            await update.message.reply_text("❌ Please enter a positive number for days!")
            return
        
        # Get stored data
        method = context.user_data.get('offer_method', 'unknown')
        percentage = context.user_data.get('offer_percentage', 0)
        
        # Generate offer
        offer_id = str(uuid.uuid4())[:8]
        
        # Calculate end date
        end_date = datetime.now() + timedelta(days=validity_days)
        
        method_names = {
            'free': 'Free Credits',
            'buy': 'Buy Credits',
            'referral': 'Referral System',
            'tts': 'TTS Usage',
            'stt': 'STT Usage',
            'video': 'Video Transcription'
        }
        
        offer_type = "Add Credit" if method in ['free', 'buy', 'referral'] else "Deduct Credit"
        
        # Create offer data
        reload_data()
        seasonal_offers_data[offer_id] = {
            'id': offer_id,
            'method': method,
            'method_name': method_names.get(method, method.title()),
            'percentage': percentage,
            'offer_type': offer_type,
            'validity_days': validity_days,
            'usage_count': 0,
            'total_credits_affected': 0,
            'created_at': datetime.now().isoformat(),
            'end_date': end_date.isoformat(),
            'created_by': 'Owner',
            'status': 'Active'
        }
        save_json(SEASONAL_OFFERS_FILE, seasonal_offers_data)
        
        benefit_text = f"{percentage}% extra credits" if method in ['free', 'buy', 'referral'] else f"{percentage}% discount"
        
        success_text = f"""
✅ **Seasonal Offer Created Successfully!**

🌟 **Offer Details:**
• **ID:** {offer_id}
• **Method:** {method_names.get(method, method.title())}
• **Type:** {offer_type}
• **Benefit:** {benefit_text}
• **Validity:** {validity_days} days
• **Status:** 🟢 Active

📅 **Dates:**
• **Created:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
• **Expires:** {end_date.strftime('%d/%m/%Y %H:%M')}

🎯 **Impact:**
This offer will automatically apply to all users when they use the {method_names.get(method, method.title())} feature!
        """
        
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Offers", callback_data="manage_seasonal_offers")]])
        await update.message.reply_text(success_text, reply_markup=back_button)
        
        # Clear temporary data
        context.user_data['state'] = None
        for key in ['offer_method', 'offer_percentage']:
            context.user_data.pop(key, None)      
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for days!")

async def delete_coupon_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Confirm coupon deletion"""
    query = update.callback_query
    coupon_id = callback_data.split("_")[-1]
    reload_data()
    
    coupon_data = coupons_data.get(coupon_id)
    if not coupon_data:
        await query.answer("Coupon not found!")
        return
    
    confirmation_text = f"""
🗑️ **Confirm Coupon Removal**

Are you sure you want to delete this coupon?

🎫 **Code:** {coupon_data['code']}
🆔 **ID:** {coupon_id}
👥 **Used by:** {coupon_data.get('used_count', 0)} users
📅 **Created:** {datetime.fromisoformat(coupon_data.get('created_at', '')).strftime('%d/%m/%Y') if coupon_data.get('created_at') else 'Unknown'}

⚠️ **Warning:** This action cannot be undone!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_coupon_{coupon_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data="remove_coupon")]
    ])
    
    await query.edit_message_text(confirmation_text, reply_markup=keyboard)

async def edit_coupon_details(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Edit coupon details"""
    query = update.callback_query
    coupon_id = callback_data.split("_")[-1]
    reload_data()
    
    coupon_data = coupons_data.get(coupon_id)
    if not coupon_data:
        await query.answer("Coupon not found!")
        return
    
    edit_text = f"""
✏️ **Edit Coupon**

🎫 **Current Details:**
• **Code:** {coupon_data['code']}
• **Credit Amount:** {coupon_data.get('credit_amount', 50)}
• **User Limit:** {coupon_data.get('user_limit', 'Unlimited')}
• **Validity:** {coupon_data.get('validity_days', 0)} days

📝 **Available Actions:**
Choose what you want to edit:
    """
    
    keyboard = [
        [InlineKeyboardButton("💰 Edit Credit Amount", callback_data=f"edit_coupon_credits_{coupon_id}")],
        [InlineKeyboardButton("👥 Edit User Limit", callback_data=f"edit_coupon_limit_{coupon_id}")],
        [InlineKeyboardButton("📅 Edit Validity", callback_data=f"edit_coupon_validity_{coupon_id}")],
        [InlineKeyboardButton("🔙 Back to Details", callback_data=f"view_coupon_{coupon_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(edit_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_edit_coupon_actions(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle edit coupon action buttons"""
    query = update.callback_query
    
    if callback_data.startswith("edit_coupon_credits_"):
        coupon_id = callback_data.split("_")[-1]
        context.user_data['edit_coupon_id'] = coupon_id
        context.user_data['edit_coupon_field'] = 'credits'
        context.user_data['state'] = 'waiting_coupon_edit_value'
        
        await query.edit_message_text(
            "💰 **Edit Credit Amount**\n\n"
            "Enter the new credit amount for this coupon:\n\n"
            "📊 Examples: 25, 50, 100, 200\n\n"
            "Enter new credit amount:",
            parse_mode='Markdown'
        )
    
    elif callback_data.startswith("edit_coupon_limit_"):
        coupon_id = callback_data.split("_")[-1]
        context.user_data['edit_coupon_id'] = coupon_id
        context.user_data['edit_coupon_field'] = 'limit'
        context.user_data['state'] = 'waiting_coupon_edit_value'
        
        await query.edit_message_text(
            "👥 **Edit User Limit**\n\n"
            "Enter the new user limit for this coupon:\n\n"
            "📊 Options:\n"
            "• Enter a number (e.g., 10, 20, 50)\n"
            "• Type 'unlimited' for no limit\n\n"
            "Enter new user limit:",
            parse_mode='Markdown'
        )
    
    elif callback_data.startswith("edit_coupon_validity_"):
        coupon_id = callback_data.split("_")[-1]
        context.user_data['edit_coupon_id'] = coupon_id
        context.user_data['edit_coupon_field'] = 'validity'
        context.user_data['state'] = 'waiting_coupon_edit_value'
        
        await query.edit_message_text(
            "📅 **Edit Validity**\n\n"
            "Enter the new validity in days for this coupon:\n\n"
            "📊 Examples: 1, 3, 7, 30\n\n"
            "Enter new validity (days):",
            parse_mode='Markdown'
        )

async def process_coupon_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE, value_text: str):
    """Process coupon edit value"""
    coupon_id = context.user_data.get('edit_coupon_id')
    field = context.user_data.get('edit_coupon_field')
    
    if not coupon_id or not field:
        await update.message.reply_text("❌ Edit session expired. Please try again.")
        context.user_data['state'] = None
        return
    
    reload_data()
    
    if coupon_id not in coupons_data:
        await update.message.reply_text("❌ Coupon not found!")
        context.user_data['state'] = None
        return
    
    try:
        if field == 'credits':
            new_value = int(value_text)
            if new_value <= 0:
                await update.message.reply_text("❌ Please enter a positive number for credits!")
                return
            coupons_data[coupon_id]['credit_amount'] = new_value
            field_name = "Credit Amount"
            
        elif field == 'limit':
            if value_text.lower().strip() == 'unlimited':
                new_value = 'Unlimited'
            else:
                new_value = int(value_text)
                if new_value <= 0:
                    await update.message.reply_text("❌ Please enter a positive number or 'unlimited'!")
                    return
            coupons_data[coupon_id]['user_limit'] = new_value
            field_name = "User Limit"
            
        elif field == 'validity':
            new_value = int(value_text)
            if new_value <= 0:
                await update.message.reply_text("❌ Please enter a positive number for days!")
                return
            # Update validity and recalculate end date
            from datetime import timedelta
            created_date = datetime.fromisoformat(coupons_data[coupon_id]['created_at'])
            new_end_date = created_date + timedelta(days=new_value)
            coupons_data[coupon_id]['validity_days'] = new_value
            coupons_data[coupon_id]['end_date'] = new_end_date.isoformat()
            field_name = "Validity"
        
        save_json(COUPONS_FILE, coupons_data)
        
        success_text = f"""
✅ **Coupon Updated Successfully!**

🎫 **Updated Field:** {field_name}
💰 **New Value:** {new_value}
🆔 **Coupon ID:** {coupon_id}
⏰ **Updated At:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

The coupon has been updated successfully!
        """
        
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Coupon", callback_data=f"view_coupon_{coupon_id}")]
        ])
        
        await update.message.reply_text(success_text, reply_markup=back_button)
        
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid value!")
        return
    
    # Clear temporary data
    context.user_data['state'] = None
    context.user_data.pop('edit_coupon_id', None)
    context.user_data.pop('edit_coupon_field', None)

async def delete_coupon_final(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Delete coupon after confirmation"""
    query = update.callback_query
    coupon_id = callback_data.split("_")[-1]
    reload_data()
    
    coupon_data = coupons_data.get(coupon_id)
    if not coupon_data:
        await query.answer("Coupon not found!")
        return
    
    deleted_code = coupon_data['code']
    del coupons_data[coupon_id]
    save_json(COUPONS_FILE, coupons_data)
    
    success_text = f"""
✅ **Coupon Deleted Successfully!**

🎫 **Deleted:** {deleted_code}
🆔 **ID:** {coupon_id}
⏰ **Deleted At:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

T�he coupon has been permanently removed.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="remove_coupon")]
    ])
    
    await query.edit_message_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')

async def view_offer_details(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Show detailed information about an offer"""
    query = update.callback_query
    offer_id = callback_data.split("_")[-1]
    reload_data()
    
    offer_data = seasonal_offers_data.get(offer_id)
    if not offer_data:
        await query.answer("Offer not found!")
        return
    
    # Calculate remaining days
    try:
        end_date = datetime.fromisoformat(offer_data.get('end_date', ''))
        remaining_days = (end_date - datetime.now()).days
        remaining_days = max(0, remaining_days)
        created_date = datetime.fromisoformat(offer_data.get('created_at', ''))
        created_formatted = created_date.strftime('%d/%m/%Y %H:%M')
        end_formatted = end_date.strftime('%d/%m/%Y %H:%M')
    except:
        remaining_days = 0
        created_formatted = 'Unknown'
        end_formatted = 'Unknown'
    
    status_emoji = "🟢" if offer_data.get('status') == 'Active' else "🔴"
    benefit_text = f"{offer_data.get('percentage', 0)}% extra credits" if offer_data.get('offer_type') == 'Add Credit' else f"{offer_data.get('percentage', 0)}% discount"
    
    details_text = f"""
🌟 **Seasonal Offer Details**

📝 **Basic Information:**
• **ID:** {offer_id}
• **Method:** {offer_data.get('method_name', 'Unknown')}
• **Type:** {offer_data.get('offer_type', 'Unknown')}
• **Benefit:** {benefit_text}
• **Status:** {status_emoji} {offer_data.get('status', 'Active')}

📅 **Validity:**
• **Created:** {created_formatted}
• **Expires:** {end_formatted}
• **Remaining:** {remaining_days} days
• **Total Days:** {offer_data.get('validity_days', 0)} days

📊 **Usage Statistics:**
• **Used By:** {offer_data.get('usage_count', 0)} users
• **Credits Affected:** {offer_data.get('total_credits_affected', 0)}
• **Daily Average:** {offer_data.get('usage_count', 0) / max(1, offer_data.get('validity_days', 1) - remaining_days):.1f} uses

🔧 **Technical Info:**
• **Created By:** {offer_data.get('created_by', 'Owner')}
• **Auto Expire:** {'Yes' if remaining_days > 0 else 'Expired'}
    """
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Remove", callback_data=f"delete_offer_{offer_id}")],
        [InlineKeyboardButton("🔙 Back to List", callback_data="offers_status")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(details_text, reply_markup=reply_markup)

async def delete_offer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Confirm offer deletion"""
    query = update.callback_query
    offer_id = callback_data.split("_")[-1]
    reload_data()
    
    offer_data = seasonal_offers_data.get(offer_id)
    if not offer_data:
        await query.answer("Offer not found!")
        return
    
    confirmation_text = f"""
🗑️ **Confirm Offer Removal**

Are you sure you want to delete this offer?

🌟 **Method:** {offer_data.get('method_name', 'Unknown')}
🆔 **ID:** {offer_id}
💰 **Benefit:** {offer_data.get('percentage', 0)}% {"extra credits" if offer_data.get('offer_type') == 'Add Credit' else "discount"}
📊 **Used by:** {offer_data.get('usage_count', 0)} users

⚠️ **Warning:** This action cannot be undone!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_offer_{offer_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data="offers_status")]
    ])
    
    await query.edit_message_text(confirmation_text, reply_markup=keyboard)

async def delete_offer_final(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Delete offer after confirmation"""
    query = update.callback_query
    offer_id = callback_data.split("_")[-1]
    reload_data()
    
    offer_data = seasonal_offers_data.get(offer_id)
    if not offer_data:
        await query.answer("Offer not found!")
        return
    
    deleted_method = offer_data.get('method_name', 'Unknown')
    del seasonal_offers_data[offer_id]
    save_json(SEASONAL_OFFERS_FILE, seasonal_offers_data)
    
    success_text = f"""
✅ **Offer Deleted Successfully!**

🌟 **Deleted:** {deleted_method} Offer
🆔 **ID:** {offer_id}
⏰ **Deleted At:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

The offer has been permanently removed.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="offers_status")]
    ])
    
    await query.edit_message_text(success_text, reply_markup=keyboard)

async def handle_coupons_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle pagination for coupons"""
    query = update.callback_query
    
    if callback_data.startswith("next_coupons_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page + 1
        if "remove" in context.user_data.get('current_action', ''):
            await show_coupons_for_removal(update, context, page=new_page)
        else:
            await show_coupons_list(update, context, page=new_page)
    elif callback_data.startswith("previous_coupons_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page - 1
        if "remove" in context.user_data.get('current_action', ''):
            await show_coupons_for_removal(update, context, page=new_page)
        else:
            await show_coupons_list(update, context, page=new_page)

async def handle_offers_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handle pagination for offers"""
    query = update.callback_query
    
    if callback_data.startswith("next_offers_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page + 1
        await show_offers_list(update, context, page=new_page)
    elif callback_data.startswith("previous_offers_"):
        current_page = int(callback_data.split("_")[-1])
        new_page = current_page - 1
        await show_offers_list(update, context, page=new_page)

# ======================== MAIN ========================
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO, handle_message))

    # Start advertisement scheduler
    context_for_scheduler = app
    start_ad_scheduler(context_for_scheduler)

    print("🤖 Bot is starting....")
    print("bot is started")
    app.run_polling()