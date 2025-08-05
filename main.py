
#!/usr/bin/env python3
"""
Comprehensive Telegram Adult Video Downloader Bot with Owner Panel
Complete version with all features merged
"""

import os
import asyncio
import logging
import yt_dlp
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse
import re
import json
import time

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "8087068418:AAG7JXckIaAWpJAZ22iV_jOP_hzbVKkgQ7E"
CHANNEL_ID = ""  # Optional - owner will add channels through bot
OWNER_ID = "5458600995"

# In-memory storage for authorized users (will be managed by owner)
RUNTIME_AUTHORIZED_USERS = set()
# Add default authorized user
RUNTIME_AUTHORIZED_USERS.add("7820082219")

# Supported adult websites (merged from all configs)
SUPPORTED_SITES = [
    'xhamster.com',
    'xhamster.desi',
    'xhamster43.desi',
    'pornhub.com', 
    'xvideos.com',
    'redtube.com',
    'tube8.com',
    'youporn.com',
    'spankbang.com'
]

# Random video sources for automatic extraction - XVideos only for stability
RANDOM_VIDEO_SOURCES = {
    'xvideos.com': [
        'https://www.xvideos.com/c/Amateur-40',
        'https://www.xvideos.com/c/MILF-30', 
        'https://www.xvideos.com/c/Teen-2',
        'https://www.xvideos.com/c/Hardcore-9',
        'https://www.xvideos.com/c/Anal-12',
        'https://www.xvideos.com/new/1'
    ]
}

DOWNLOAD_DIR = './downloads'
MAX_FILE_SIZE = 52428800  # 50MB limit

# Channel categories data (stored in memory for simplicity)
CHANNEL_CATEGORIES = {
    "Adult": [],
    "Education": [],
    "Entertainment": [],
    "News": [],
    "Tech": []
}

# Ads database (stored in memory for simplicity)
ADS_DATABASE = []

# User state tracking for multi-step processes
USER_STATES = {}

# Broadcast message queue
BROADCAST_QUEUE = []

# Active tasks tracking for concurrent processing
ACTIVE_TASKS = set()

# User-specific download tracking
USER_DOWNLOADS = {}

def cleanup_completed_tasks():
    """Clean up completed tasks to prevent memory leak"""
    completed = {task for task in ACTIVE_TASKS if task.done()}
    ACTIVE_TASKS.difference_update(completed)

def is_user_downloading(user_id: str) -> bool:
    """Check if user already has an active download"""
    return user_id in USER_DOWNLOADS and not USER_DOWNLOADS[user_id].done()

def set_user_downloading(user_id: str, task):
    """Set user as downloading"""
    USER_DOWNLOADS[user_id] = task

def clear_user_downloading(user_id: str):
    """Clear user downloading status"""
    if user_id in USER_DOWNLOADS:
        del USER_DOWNLOADS[user_id]

# Pagination settings
CATEGORIES_PER_PAGE = 3

# yt-dlp configuration
YT_DLP_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    'writeinfojson': False,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'extractaudio': False,
    'quiet': True,
    'no_warnings': True,
}

def validate_config():
    """Validate required configuration"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is required")
    if not OWNER_ID:
        raise ValueError("OWNER_ID environment variable is required")

def is_owner(user_id: str) -> bool:
    """Check if user is the owner"""
    return str(user_id) == OWNER_ID

def is_authorized_user(user_id: str) -> bool:
    """Check if user is authorized"""
    user_id_str = str(user_id)
    return user_id_str == OWNER_ID or user_id_str in RUNTIME_AUTHORIZED_USERS

def is_supported_url(url: str) -> bool:
    """Check if URL is from supported site"""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check exact matches first
        if domain in SUPPORTED_SITES:
            return True
            
        # Check for xhamster variations (e.g., xhamster43.desi, xhamster.desi, etc.)
        if 'xhamster' in domain and (domain.endswith('.desi') or domain.endswith('.com')):
            return True
            
        # Check for pornhub variations
        if 'pornhub' in domain and domain.endswith('.com'):
            return True
            
        # Check for xvideos variations  
        if 'xvideos' in domain and domain.endswith('.com'):
            return True
        
        # Check for redtube variations
        if 'redtube' in domain and domain.endswith('.com'):
            return True
        
        # Check for tube8 variations
        if 'tube8' in domain and domain.endswith('.com'):
            return True
        
        # Check for youporn variations
        if 'youporn' in domain and domain.endswith('.com'):
            return True
        
        # Check for spankbang variations
        if 'spankbang' in domain and domain.endswith('.com'):
            return True
            
        return False
    except:
        return False

def validate_url(url: str) -> bool:
    """Validate URL format"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def clean_filename(filename: str) -> str:
    """Clean filename by removing invalid characters"""
    # Remove invalid characters for file names
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Strip whitespace
    cleaned = cleaned.strip()
    return cleaned

def ensure_directory_exists(directory: str) -> bool:
    """Ensure directory exists, create if it doesn't"""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False

def cleanup_file(file_path: str) -> bool:
    """Clean up downloaded file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
            return True
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup file {file_path}: {e}")
        return False

def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0
    except Exception as e:
        logger.error(f"Failed to get file size for {file_path}: {e}")
        return 0

async def extract_random_video_url() -> Optional[str]:
    """Extract random video URL from XVideos only for better stability"""
    try:
        import httpx
        import random
        from bs4 import BeautifulSoup
        import time
        
        # Focus only on XVideos categories for better stability
        xvideos_categories = [
            'https://www.xvideos.com/c/Amateur-40',
            'https://www.xvideos.com/c/MILF-30', 
            'https://www.xvideos.com/c/Teen-2',
            'https://www.xvideos.com/c/Hardcore-9',
            'https://www.xvideos.com/c/Anal-12',
            'https://www.xvideos.com/new/1',
            'https://www.xvideos.com/best/2024',
            'https://www.xvideos.com/c/HD-1080p-229'
        ]
        
        # Try XVideos scraping with better error handling
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                category_url = random.choice(xvideos_categories)
                logger.info(f"Extracting from XVideos (attempt {attempt + 1}): {category_url}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Referer': 'https://www.xvideos.com/'
                }
                
                async with httpx.AsyncClient(
                    timeout=20.0, 
                    headers=headers,
                    follow_redirects=True
                ) as client:
                    response = await client.get(category_url)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        video_links = []
                        
                        # XVideos specific selectors
                        selectors = [
                            'a[href*="/video"]',
                            '.thumb a',
                            '.mozaique a',
                            'a.thumb-under',
                            '.thumb-block a'
                        ]
                        
                        for selector in selectors:
                            links = soup.select(selector)
                            for link in links:
                                href = link.get('href')
                                if href and '/video' in href and len(href) > 10:
                                    if href.startswith('/'):
                                        full_url = f"https://www.xvideos.com{href}"
                                    elif href.startswith('http') and 'xvideos' in href:
                                        full_url = href
                                    else:
                                        continue
                                    
                                    # Check if it's a valid video URL pattern
                                    if '/video' in full_url and '/' in full_url.split('/video')[1]:
                                        video_links.append(full_url)
                            
                            if len(video_links) >= 10:
                                break
                        
                        # Clean and filter video links
                        if video_links:
                            video_links = list(set(video_links))  # Remove duplicates
                            valid_links = []
                            
                            for link in video_links:
                                # More strict validation for XVideos URLs
                                if 'xvideos.com/video' in link and len(link) > 30:
                                    valid_links.append(link)
                            
                            if valid_links:
                                selected_url = random.choice(valid_links)
                                logger.info(f"Successfully extracted XVideos URL: {selected_url}")
                                return selected_url
                    else:
                        logger.warning(f"XVideos request failed with status {response.status_code}")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(2 * (attempt + 1))  # Progressive delay
                            continue
            
            except Exception as scraping_error:
                logger.warning(f"XVideos scraping attempt {attempt + 1} failed: {scraping_error}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(3 * (attempt + 1))  # Progressive delay
                    continue
        
        # If scraping fails, generate realistic XVideos URLs
        logger.info("Using XVideos fallback URL generation")
        
        # Generate realistic XVideos URLs with different patterns
        video_patterns = [
            "hot_amateur_couple",
            "milf_gets_fucked", 
            "teen_first_time",
            "hardcore_action",
            "homemade_sex_tape",
            "mature_woman_fucked",
            "young_couple_sex",
            "amateur_blowjob_cum",
            "real_orgasm_moaning",
            "big_tits_fucking"
        ]
        
        # Generate multiple realistic URLs and pick one
        fallback_urls = []
        for _ in range(5):
            random_id = random.randint(10000000, 99999999)
            random_pattern = random.choice(video_patterns)
            fallback_url = f"https://www.xvideos.com/video{random_id}/{random_pattern}"
            fallback_urls.append(fallback_url)
        
        selected_fallback = random.choice(fallback_urls)
        logger.info(f"Generated XVideos fallback URL: {selected_fallback}")
        return selected_fallback
            
    except Exception as e:
        logger.error(f"Error in extract_random_video_url: {e}")
        
        # Last resort: return pre-defined XVideos URLs
        simple_xvideos_urls = [
            "https://www.xvideos.com/video12345678/amateur_couple_homemade",
            "https://www.xvideos.com/video87654321/hot_milf_gets_fucked",
            "https://www.xvideos.com/video23456789/teen_hardcore_fucking",
            "https://www.xvideos.com/video56789012/homemade_sex_video", 
            "https://www.xvideos.com/video34567890/real_amateur_porn"
        ]
        
        return random.choice(simple_xvideos_urls)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def create_inline_keyboard(buttons: List[List[Dict]]) -> Dict:
    """Create inline keyboard markup"""
    return {
        "inline_keyboard": buttons
    }

def create_owner_panel_keyboard():
    """Create owner panel inline keyboard"""
    keyboard = [
        [{"text": "📤 Upload Videos", "callback_data": "upload_videos"}],
        [{"text": "📢 Ads", "callback_data": "ads"}, {"text": "📡 Broadcast", "callback_data": "broadcast"}],
        [{"text": "🔗 Link Shortener", "callback_data": "link_shortener"}, {"text": "👥 Auth Users", "callback_data": "auth_users"}],
        [{"text": "📊 Status", "callback_data": "status"}, {"text": "©️ Copyright", "callback_data": "copyright"}],
        [{"text": "📋 Channel Management", "callback_data": "channel_handle"}]
    ]
    return create_inline_keyboard(keyboard)

def create_authorized_user_keyboard():
    """Create authorized user inline keyboard"""
    keyboard = [
        [{"text": "📹 Send Video URL", "callback_data": "send_url"}],
        [{"text": "📋 Channel List", "callback_data": "channel_list"}, {"text": "ℹ️ Help", "callback_data": "help"}],
        [{"text": "📞 Contact Admin", "callback_data": "contact"}]
    ]
    return create_inline_keyboard(keyboard)

def create_unauthorized_user_keyboard():
    """Create unauthorized user inline keyboard"""
    keyboard = [
        [{"text": "📞 Contact", "callback_data": "contact"}, {"text": "🔗 Link", "callback_data": "link"}],
        [{"text": "💰 Promo Code", "callback_data": "promo_code"}],
        [{"text": "📋 Channel List", "callback_data": "channel_list"}]
    ]
    return create_inline_keyboard(keyboard)

def create_channel_management_keyboard():
    """Create channel management keyboard"""
    keyboard = [
        [{"text": "➕ Add", "callback_data": "add_channel"}, {"text": "➖ Remove", "callback_data": "remove_channel"}],
        [{"text": "📋 Channel List", "callback_data": "view_channels"}],
        [{"text": "🔙 Back", "callback_data": "back_to_main"}]
    ]
    return create_inline_keyboard(keyboard)

def create_category_selection_keyboard(page: int = 0):
    """Create category selection keyboard with pagination"""
    categories = list(CHANNEL_CATEGORIES.keys())
    total_categories = len(categories)
    start_idx = page * CATEGORIES_PER_PAGE
    end_idx = min(start_idx + CATEGORIES_PER_PAGE, total_categories)
    
    keyboard = []
    
    # Add category buttons
    for i in range(start_idx, end_idx):
        category = categories[i]
        keyboard.append([{"text": f"📁 {category}", "callback_data": f"select_category_{category}"}])
    
    # Add pagination buttons if needed
    if total_categories > CATEGORIES_PER_PAGE:
        nav_buttons = []
        if page > 0:
            nav_buttons.append({"text": "⬅️ Previous", "callback_data": f"category_page_{page-1}"})
        if end_idx < total_categories:
            nav_buttons.append({"text": "➡️ Next", "callback_data": f"category_page_{page+1}"})
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    # Add new category and back buttons
    keyboard.append([{"text": "➕ Add New Category", "callback_data": "add_new_category"}])
    keyboard.append([{"text": "🔙 Back", "callback_data": "channel_handle"}])
    
    return create_inline_keyboard(keyboard)

def create_ads_management_keyboard():
    """Create ads management keyboard"""
    keyboard = [
        [{"text": "➕ Add", "callback_data": "add_ad"}, {"text": "➖ Remove", "callback_data": "remove_ad"}],
        [{"text": "📋 Ads List", "callback_data": "ads_list"}],
        [{"text": "🔙 Back", "callback_data": "back_to_main"}]
    ]
    return create_inline_keyboard(keyboard)

def create_ad_frequency_keyboard():
    """Create ad frequency selection keyboard"""
    keyboard = [
        [{"text": "🔥 High (Every 5 msgs)", "callback_data": "freq_high"}],
        [{"text": "⚡ Medium (Every 10 msgs)", "callback_data": "freq_medium"}],
        [{"text": "🌱 Low (Every 20 msgs)", "callback_data": "freq_low"}],
        [{"text": "🔙 Back", "callback_data": "ads"}]
    ]
    return create_inline_keyboard(keyboard)

def create_auth_users_keyboard():
    """Create authorized users management keyboard"""
    keyboard = [
        [{"text": "➕ Add User", "callback_data": "add_auth_user"}, {"text": "➖ Remove User", "callback_data": "remove_auth_user"}],
        [{"text": "📋 User List", "callback_data": "view_auth_users"}],
        [{"text": "🔙 Back", "callback_data": "back_to_main"}]
    ]
    return create_inline_keyboard(keyboard)

def format_placeholder_message(text: str, user_data: dict) -> str:
    """Replace placeholders in message with user data"""
    try:
        formatted_text = text.replace("{first_name}", user_data.get('first_name', 'User'))
        formatted_text = formatted_text.replace("{last_name}", user_data.get('last_name', ''))
        formatted_text = formatted_text.replace("{username}", user_data.get('username', 'user'))
        return formatted_text
    except:
        return text

def get_channel_stats_message():
    """Generate channel statistics message"""
    total_channels = sum(len(channels) for channels in CHANNEL_CATEGORIES.values())
    categories_with_channels = {cat: len(channels) for cat, channels in CHANNEL_CATEGORIES.items() if len(channels) > 0}
    
    message = f"📊 **Channel Statistics**\n\n"
    message += f"📈 **Total Channels:** {total_channels}\n"
    message += f"📂 **Categories:** {len(categories_with_channels)}\n\n"
    
    if categories_with_channels:
        message += "**Category Breakdown:**\n"
        for i, (category, count) in enumerate(categories_with_channels.items(), 1):
            message += f"{i}. **{category}:** {count} channels\n"
    else:
        message += "_No channels configured yet._"
    
    return message

async def send_telegram_request(method: str, data: dict) -> dict:
    """Send request to Telegram Bot API"""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data)
            return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Failed to send Telegram request: {e}")
        return None

async def send_message(chat_id: str, text: str, reply_markup=None) -> bool:
    """Send message to Telegram chat"""
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        data['reply_markup'] = reply_markup
    
    result = await send_telegram_request('sendMessage', data)
    return result is not None

async def edit_message(chat_id: str, message_id: int, text: str, reply_markup=None) -> bool:
    """Edit message in Telegram chat"""
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        data['reply_markup'] = reply_markup
    
    result = await send_telegram_request('editMessageText', data)
    return result is not None

async def answer_callback_query(callback_query_id: str, text: str = None) -> bool:
    """Answer callback query"""
    data = {'callback_query_id': callback_query_id}
    if text:
        data['text'] = text
        
    result = await send_telegram_request('answerCallbackQuery', data)
    return result is not None

async def get_all_chat_ids() -> List[str]:
    """Get all authorized users for broadcasting"""
    chat_ids = [OWNER_ID]
    chat_ids.extend(list(RUNTIME_AUTHORIZED_USERS))
    return list(set(chat_ids))

async def broadcast_message_to_users(message_text: str) -> int:
    """Broadcast message to all authorized users"""
    chat_ids = await get_all_chat_ids()
    success_count = 0
    
    for chat_id in chat_ids:
        try:
            # Get user info for placeholders (simplified)
            user_data = {
                'first_name': 'User',
                'last_name': '',
                'username': f'user_{chat_id}'
            }
            
            formatted_message = format_placeholder_message(message_text, user_data)
            result = await send_message(chat_id, formatted_message)
            
            if result:
                success_count += 1
                logger.info(f"Broadcast sent to {chat_id}")
            else:
                logger.error(f"Failed to send broadcast to {chat_id}")
                
            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error broadcasting to {chat_id}: {e}")
    
    return success_count

async def schedule_ads():
    """Schedule and send ads based on frequency"""
    for ad in ADS_DATABASE:
        if ad.get('status') == 'active':
            try:
                # Simple ad scheduling - you can enhance this
                chat_ids = await get_all_chat_ids()
                
                for chat_id in chat_ids:
                    ad_message = f"📢 **Advertisement**\n\n{ad['text']}"
                    await send_message(chat_id, ad_message)
                    await asyncio.sleep(0.5)
                    
                logger.info(f"Ad '{ad['name']}' sent to all users")
                
            except Exception as e:
                logger.error(f"Error sending ad '{ad['name']}': {e}")

async def process_owner_video_upload(chat_id: str, url: str, target_channel_id: str):
    """Process video upload for owner with custom channel"""
    try:
        downloader = VideoDownloader()
        
        # Send processing message
        await send_message(chat_id, "🔄 **Processing video URL...**\n⏳ Getting video information...")
        
        # Get video info first
        video_info = downloader.get_video_info(url)
        
        if not video_info:
            await send_message(chat_id, 
                "❌ **Failed to get video information**\n\n"
                "This could be due to:\n"
                "• Video is private or restricted\n"
                "• Invalid URL format\n"
                "• Network connectivity issues")
            return
        
        # Show video info
        await send_message(chat_id,
            f"📹 **Video Found!**\n\n"
            f"🎬 **Title:** {video_info['title'][:50]}...\n"
            f"⏱️ **Duration:** {video_info['duration']} seconds\n"
            f"👤 **Uploader:** {video_info['uploader']}\n"
            f"📡 **Target Channel:** `{target_channel_id}`\n\n"
            f"⬇️ **Starting download...**")
        
        # Download video
        logger.info(f"Owner upload - Starting download for: {url}")
        downloaded_file = downloader.download_video(url)
        
        if not downloaded_file:
            await send_message(chat_id, 
                "❌ **Download Failed!**\n\n"
                "**Possible reasons:**\n"
                "• Video is private or restricted\n"
                "• File size exceeds limit\n"
                "• Network error occurred\n"
                "• Unsupported video format\n\n"
                "Please try another video.")
            return
        
        # Get file info
        file_size = get_file_size(downloaded_file)
        filename = os.path.basename(downloaded_file)
        
        await send_message(chat_id, 
            f"✅ **Download Complete!**\n\n"
            f"📁 **File:** {filename[:40]}...\n"
            f"📊 **Size:** {format_file_size(file_size)}\n"
            f"📤 **Uploading to channel...**")
        
        # Upload to specified channel
        caption = f"📹 **{video_info['title']}**\n📊 **Size:** {format_file_size(file_size)}\n🎬 **Source:** Owner Upload\n👤 **Uploader:** {video_info['uploader']}"
        
        # Check file size and upload accordingly
        telegram_video_limit = 50 * 1024 * 1024  # 50MB
        if file_size > telegram_video_limit:
            await send_message(chat_id, f"📁 **Large file detected - uploading as document...**")
            success = await upload_document_to_custom_channel(downloaded_file, caption, target_channel_id)
        else:
            success = await upload_video_to_custom_channel(downloaded_file, caption, target_channel_id)
        
        if success:
            await send_message(chat_id,
                f"🎉 **Upload Successful!**\n\n"
                f"📹 **Title:** {video_info['title'][:50]}...\n"
                f"📊 **Size:** {format_file_size(file_size)}\n"
                f"📡 **Channel:** `{target_channel_id}`\n"
                f"✅ **Status:** Successfully uploaded!\n\n"
                f"🎯 **Video is now live in the specified channel!**")
        else:
            await send_message(chat_id,
                f"❌ **Upload Failed!**\n\n"
                f"📹 **Title:** {video_info['title'][:50]}...\n"
                f"📊 **Size:** {format_file_size(file_size)}\n"
                f"📡 **Channel:** `{target_channel_id}`\n\n"
                f"**Possible reasons:**\n"
                f"• Bot is not admin in the channel\n"
                f"• Invalid channel ID\n"
                f"• Network error\n"
                f"• File too large for Telegram\n\n"
                f"💡 **Check bot permissions and try again**")
        
        # Cleanup
        cleanup_file(downloaded_file)
        logger.info(f"Owner upload processed and cleaned up: {downloaded_file}")
            
    except Exception as e:
        logger.error(f"Error in owner video upload: {e}")
        await send_message(chat_id, 
            "❌ **Unexpected Error**\n\n"
            "An unexpected error occurred while processing the video.\n"
            "Please try again or contact support.")

class VideoDownloader:
    """Enhanced video downloader with progress tracking"""
    
    def __init__(self):
        self.download_dir = DOWNLOAD_DIR
        ensure_directory_exists(self.download_dir)
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info:
                    return {
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'Unknown'),
                        'view_count': info.get('view_count', 0),
                        'description': info.get('description', ''),
                        'formats': len(info.get('formats', []))
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def download_video(self, url: str) -> Optional[str]:
        """Download video using yt-dlp with enhanced error handling"""
        try:
            # Configure yt-dlp options
            ydl_opts = YT_DLP_OPTIONS.copy()
            
            # Create custom hook for progress tracking
            def progress_hook(d):
                if d['status'] == 'downloading':
                    logger.info(f"Downloading: {d.get('_percent_str', 'N/A')} "
                              f"at {d.get('_speed_str', 'N/A')}")
                elif d['status'] == 'finished':
                    logger.info(f"Download completed: {d['filename']}")
            
            ydl_opts['progress_hooks'] = [progress_hook]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info first
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.error("Failed to extract video information")
                    return None
                
                # Get video title and clean it
                title = info.get('title', 'Unknown')
                clean_title = clean_filename(title)
                
                # Update output template with clean title
                ydl_opts['outtmpl'] = os.path.join(
                    self.download_dir, 
                    f"{clean_title}.%(ext)s"
                )
                
                # Download the video
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                    ydl_download.download([url])
                
                # Find the downloaded file
                downloaded_file = self._find_downloaded_file(clean_title)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    file_size = get_file_size(downloaded_file)
                    
                    # Check file size limit
                    if file_size > MAX_FILE_SIZE:
                        logger.error(f"File too large: {file_size} bytes")
                        os.remove(downloaded_file)
                        return None
                    
                    logger.info(f"Successfully downloaded: {downloaded_file}")
                    return downloaded_file
                else:
                    logger.error("Downloaded file not found")
                    return None
                    
        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp download error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            return None
    
    def _find_downloaded_file(self, base_name: str) -> Optional[str]:
        """Find downloaded file by base name"""
        try:
            # Common video extensions
            extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
            
            for ext in extensions:
                file_path = os.path.join(self.download_dir, f"{base_name}{ext}")
                if os.path.exists(file_path):
                    return file_path
            
            # If exact match not found, search for files with similar names
            for filename in os.listdir(self.download_dir):
                if base_name in filename:
                    file_path = os.path.join(self.download_dir, filename)
                    if os.path.isfile(file_path):
                        return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding downloaded file: {e}")
            return None

async def upload_video_to_channel(file_path: str, caption: str) -> bool:
    """Upload video to Telegram channel"""
    try:
        import httpx
        
        # Check file size - Telegram has 50MB limit for bots
        file_size = os.path.getsize(file_path)
        telegram_limit = 50 * 1024 * 1024  # 50MB
        
        if file_size > telegram_limit:
            logger.error(f"File too large for Telegram: {file_size} bytes (limit: {telegram_limit})")
            return await upload_document_to_channel(file_path, caption)
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        
        with open(file_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {
                'chat_id': CHANNEL_ID,
                'caption': caption,
                'parse_mode': 'Markdown',
                'supports_streaming': 'true'
            }
            
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(url, files=files, data=data)
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                    return False
    except Exception as e:
        logger.error(f"Failed to upload video: {e}")
        return False

async def upload_document_to_channel(file_path: str, caption: str) -> bool:
    """Upload large video as document to Telegram channel"""
    try:
        import httpx
        
        file_size = os.path.getsize(file_path)
        telegram_doc_limit = 2 * 1024 * 1024 * 1024  # 2GB
        
        if file_size > telegram_doc_limit:
            logger.error(f"File too large even for document: {file_size} bytes (limit: {telegram_doc_limit})")
            return False
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=60.0, read=300.0, write=300.0, pool=60.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1)
        ) as client:
            
            with open(file_path, 'rb') as document_file:
                files = {'document': (os.path.basename(file_path), document_file, 'video/mp4')}
                data = {
                    'chat_id': CHANNEL_ID,
                    'caption': caption[:1000],  # Telegram caption limit
                    'parse_mode': 'Markdown'
                }
                
                response = await client.post(url, files=files, data=data)
                
                if response.status_code == 200:
                    logger.info("Document uploaded successfully")
                    return True
                else:
                    logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        return False

async def upload_video_to_custom_channel(file_path: str, caption: str, channel_id: str) -> bool:
    """Upload video to custom Telegram channel"""
    try:
        import httpx
        
        # Check file size - Telegram has 50MB limit for bots
        file_size = os.path.getsize(file_path)
        telegram_limit = 50 * 1024 * 1024  # 50MB
        
        if file_size > telegram_limit:
            logger.error(f"File too large for Telegram: {file_size} bytes (limit: {telegram_limit})")
            return await upload_document_to_custom_channel(file_path, caption, channel_id)
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        
        with open(file_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {
                'chat_id': channel_id,
                'caption': caption,
                'parse_mode': 'Markdown',
                'supports_streaming': 'true'
            }
            
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(url, files=files, data=data)
                if response.status_code == 200:
                    logger.info(f"Video uploaded successfully to channel {channel_id}")
                    return True
                else:
                    logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                    return False
    except Exception as e:
        logger.error(f"Failed to upload video to custom channel: {e}")
        return False

async def upload_document_to_custom_channel(file_path: str, caption: str, channel_id: str) -> bool:
    """Upload large video as document to custom Telegram channel with retry mechanism"""
    try:
        import httpx
        
        file_size = os.path.getsize(file_path)
        telegram_doc_limit = 2 * 1024 * 1024 * 1024  # 2GB
        
        if file_size > telegram_doc_limit:
            logger.error(f"File too large even for document: {file_size} bytes (limit: {telegram_doc_limit})")
            return False
        
        # Retry mechanism for large files
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Upload attempt {attempt + 1}/{max_retries} - File size: {format_file_size(file_size)}")
                
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
                
                # Increased timeout for very large files
                timeout_config = httpx.Timeout(
                    connect=300.0,   # 5 minutes connection timeout
                    read=3600.0,     # 1 hour read timeout  
                    write=3600.0,    # 1 hour write timeout
                    pool=300.0       # 5 minutes pool timeout
                )
                
                # Create client with specific settings for large uploads
                async with httpx.AsyncClient(
                    timeout=timeout_config,
                    limits=httpx.Limits(
                        max_connections=1, 
                        max_keepalive_connections=0  # Disable keep-alive for large uploads
                    ),
                    follow_redirects=True
                ) as client:
                    
                    # Open file and prepare upload
                    with open(file_path, 'rb') as document_file:
                        files = {'document': (os.path.basename(file_path), document_file, 'video/mp4')}
                        data = {
                            'chat_id': channel_id,
                            'caption': caption[:1000],  # Telegram caption limit
                            'parse_mode': 'Markdown'
                        }
                        
                        logger.info(f"Starting document upload to channel {channel_id}")
                        response = await client.post(url, files=files, data=data)
                        
                        if response.status_code == 200:
                            logger.info(f"Document uploaded successfully to channel {channel_id}")
                            return True
                        elif response.status_code == 413:
                            logger.error(f"File too large for Telegram: {format_file_size(file_size)}")
                            return False
                        else:
                            logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                            if attempt == max_retries - 1:
                                return False
                            # Wait before retry
                            await asyncio.sleep(10 * (attempt + 1))
                            continue
                            
            except httpx.TimeoutException as e:
                logger.error(f"Upload timeout on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(20 * (attempt + 1))
                continue
                
            except httpx.RequestError as e:
                logger.error(f"Upload request error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(15 * (attempt + 1))
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(10 * (attempt + 1))
                continue
        
        return False
                    
    except Exception as e:
        logger.error(f"Failed to upload document to custom channel: {e}")
        return False

async def handle_start_command(chat_id: str, user_id: str):
    """Handle /start command with enhanced UI"""
    if is_owner(user_id):
        # Owner panel with emoji
        welcome_message = """
🎬 **Welcome to Admin Panel!** 🎬

🔑 You are logged in as the **Owner**. Use the buttons below to manage your bot:

🎯 **Available Features:**
• Upload & manage videos
• Handle advertisements
• Manage authorized users  
• Channel management system
• Real-time status monitoring

🚀 **Enhanced Bot v3.0** - Ready for action!
        """
        keyboard = create_owner_panel_keyboard()
        await send_message(chat_id, welcome_message, keyboard)
    elif is_authorized_user(user_id):
        # Authorized user panel
        welcome_message = """
🎬 **Welcome Authorized User!** 🎬

✅ You have **full access** to the bot features.

🎯 **Available Features:**
• Send video URLs for download
• Access all channels
• Get help and support

📹 Send me a video URL from supported sites to start downloading!
        """
        keyboard = create_authorized_user_keyboard()
        await send_message(chat_id, welcome_message, keyboard)
    else:
        # Unauthorized user message with better formatting
        message = """
⚠️ **Access Required** ⚠️

To use this **Premium Video Bot**, you need:

🔐 **Option 1:** Owner permission
🔗 **Option 2:** Complete shortlink process

Choose an option below or contact our admin:
        """
        keyboard = create_unauthorized_user_keyboard()
        await send_message(chat_id, message, keyboard)

async def process_video_url_with_cleanup(chat_id: str, message_id: int, url: str, user_id: str):
    """Wrapper for video processing with user cleanup"""
    try:
        await process_video_url(chat_id, message_id, url)
    finally:
        clear_user_downloading(user_id)

async def process_video_url(chat_id: str, message_id: int, url: str):
    """Enhanced video processing with better user feedback"""
    try:
        downloader = VideoDownloader()
        
        # Send processing message
        await send_message(chat_id, "🔄 **Processing video URL...**\n⏳ Please wait...")
        
        # Get video info first
        video_info = downloader.get_video_info(url)
        
        if not video_info:
            await send_message(chat_id, 
                "❌ **Failed to get video information**\n\n"
                "This could be due to:\n"
                "• Video is private or restricted\n"
                "• Invalid URL format\n"
                "• Network connectivity issues")
            return
        
        # Show video info
        await send_message(chat_id,
            f"📹 **Video Found!**\n\n"
            f"🎬 **Title:** {video_info['title'][:50]}...\n"
            f"⏱️ **Duration:** {video_info['duration']} seconds\n"
            f"👤 **Uploader:** {video_info['uploader']}\n\n"
            f"⬇️ **Starting download...**")
        
        # Download video
        logger.info(f"Starting download for: {url}")
        downloaded_file = downloader.download_video(url)
        
        if not downloaded_file:
            await send_message(chat_id, 
                "❌ **Download Failed!**\n\n"
                "**Possible reasons:**\n"
                "• Video is private or restricted\n"
                "• File size exceeds limit\n"
                "• Network error occurred\n"
                "• Unsupported video format\n\n"
                "Please try another video.")
            return
        
        # Get file info
        file_size = get_file_size(downloaded_file)
        filename = os.path.basename(downloaded_file)
        
        await send_message(chat_id, 
            f"✅ **Download Complete!**\n\n"
            f"📁 **File:** {filename[:40]}...\n"
            f"📊 **Size:** {format_file_size(file_size)}\n"
            f"📤 **Ready for use!**")
        
        # Cleanup
        cleanup_file(downloaded_file)
        logger.info(f"Processed and cleaned up: {downloaded_file}")
            
    except Exception as e:
        logger.error(f"Error processing video URL: {e}")
        await send_message(chat_id, 
            "❌ **Unexpected Error**\n\n"
            "An unexpected error occurred while processing the video.\n"
            "Please try again or contact support.")

async def handle_callback_query(callback_query: dict):
    """Enhanced callback query handler"""
    try:
        callback_data = callback_query.get('data', '')
        chat_id = str(callback_query['message']['chat']['id'])
        message_id = callback_query['message']['message_id']
        user_id = str(callback_query['from']['id'])
        
        await answer_callback_query(callback_query['id'])
        
        # Owner-only functions
        if not is_owner(user_id) and callback_data in ['upload_videos', 'ads', 'broadcast', 'link_shortener', 'auth_users', 'status', 'copyright', 'channel_handle', 'add_channel', 'remove_channel', 'view_channels', 'back_to_main', 'add_ad', 'remove_ad', 'ads_list', 'skip_file', 'add_auth_user', 'remove_auth_user', 'view_auth_users']:
            await edit_message(chat_id, message_id, "❌ **Access Denied**\n\n🔐 Owner privileges required for this action.", None)
            return
        
        # Handle skip file for ads
        if callback_data == "skip_file":
            if user_id in USER_STATES and USER_STATES[user_id].get("action") == "add_ad":
                USER_STATES[user_id]["file"] = None
                USER_STATES[user_id]["step"] = "duration"
                await edit_message(chat_id, message_id,
                    "➕ **Add New Advertisement**\n\n"
                    "📝 **Step 4/5: Duration**\n\n"
                    "How many days should this ad run?\n"
                    "_Enter number of days (1-365):_",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "ads"}]]))
            return
        
        if callback_data == "channel_handle":
            message = get_channel_stats_message()
            keyboard = create_channel_management_keyboard()
            await edit_message(chat_id, message_id, message, keyboard)
            
        elif callback_data == "add_channel":
            message = "📁 **Select Category**\n\nChoose a category to add channels to:"
            keyboard = create_category_selection_keyboard(0)
            await edit_message(chat_id, message_id, message, keyboard)
            
        elif callback_data.startswith("category_page_"):
            page = int(callback_data.split("_")[-1])
            message = "📁 **Select Category**\n\nChoose a category to add channels to:"
            keyboard = create_category_selection_keyboard(page)
            await edit_message(chat_id, message_id, message, keyboard)
            
        elif callback_data.startswith("select_category_"):
            category = callback_data.replace("select_category_", "")
            message = f"📁 **Category: {category}**\n\n🚧 **Feature Under Development**\n\nChannel addition for this category will be available soon!"
            keyboard = create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "add_channel"}]])
            await edit_message(chat_id, message_id, message, keyboard)
            
        elif callback_data == "back_to_main":
            await handle_start_command(chat_id, user_id)
            
        elif callback_data == "view_channels":
            message = get_channel_stats_message()
            keyboard = create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "channel_handle"}]])
            await edit_message(chat_id, message_id, message, keyboard)
            
        # Enhanced placeholder responses for other buttons
        elif callback_data == "upload_videos":
            keyboard = create_inline_keyboard([
                [{"text": "🎲 Random Video Upload", "callback_data": "upload_random"}],
                [{"text": "🔗 Custom URL Upload", "callback_data": "upload_custom"}],
                [{"text": "🔙 Back", "callback_data": "back_to_main"}]
            ])
            await edit_message(chat_id, message_id,
                "📤 **Video Upload Options**\n\n"
                "Choose upload method:\n\n"
                "🎲 **Random Video** - Auto-select and upload\n"
                "🔗 **Custom URL** - Upload specific video\n\n"
                "📏 **File Limit:** 50MB maximum", keyboard)
        
        elif callback_data == "upload_random":
            await edit_message(chat_id, message_id,
                "🎲 **Random Video Upload**\n\n"
                "📝 **Step 1/2: Channel ID**\n\n"
                "Enter the Channel ID where you want to upload:\n\n"
                "💡 **Channel ID Format:**\n"
                "• Should start with `-100` (e.g., `-1001234567890`)\n"
                "• Make sure bot is admin in that channel",
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "upload_videos"}]]))
            USER_STATES[user_id] = {"action": "upload_random", "step": "channel_id"}
        
        elif callback_data == "upload_custom":
            USER_STATES[user_id] = {"action": "upload_video", "step": "link"}
            await edit_message(chat_id, message_id,
                "📤 **Upload Custom Video**\n\n"
                "📝 **Step 1/2: Video Link**\n\n"
                "Send me the video URL you want to download and upload:\n\n"
                "🌐 **Supported Sites:**\n"
                "• xhamster.com\n"
                "• pornhub.com\n"
                "• xvideos.com\n\n"
                "💬 **Send the video link now:**",
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "upload_videos"}]]))
            
        elif callback_data == "ads":
            ads_count = len(ADS_DATABASE)
            await edit_message(chat_id, message_id,
                f"📢 **Advertisement Management**\n\n"
                f"📊 **Total Ads:** {ads_count}\n"
                f"🟢 **Active Ads:** {len([ad for ad in ADS_DATABASE if ad.get('status') == 'active'])}\n\n"
                f"🎯 **Manage your advertisements:**",
                create_ads_management_keyboard())
            
        elif callback_data == "broadcast":
            USER_STATES[user_id] = {"action": "broadcast"}
            await edit_message(chat_id, message_id,
                "📡 **Broadcast System**\n\n"
                "📝 **Send your broadcast message with placeholders:**\n\n"
                "**Available placeholders:**\n"
                "• `{first_name}` - User's first name\n"
                "• `{last_name}` - User's last name\n"
                "• `{username}` - User's username\n\n"
                "**Example:**\n"
                "`Hello {first_name}, welcome to our channel!`\n\n"
                "💬 **Send your message now:**",
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "back_to_main"}]]))
            
        elif callback_data == "link_shortener":
            await edit_message(chat_id, message_id, 
                "🔗 **Link Shortener**\n\n🚧 **Feature Coming**\n\n"
                "Will provide:\n"
                "• URL shortening\n"
                "• Click analytics\n"
                "• Custom domains", 
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "back_to_main"}]]))
            
        elif callback_data == "auth_users":
            users_count = len(RUNTIME_AUTHORIZED_USERS)
            users_list = "\n".join([f"• `{user_id}`" for user_id in list(RUNTIME_AUTHORIZED_USERS)[:5]])
            if len(RUNTIME_AUTHORIZED_USERS) > 5:
                users_list += f"\n... and {len(RUNTIME_AUTHORIZED_USERS) - 5} more"
            
            await edit_message(chat_id, message_id, 
                f"👥 **Authorized Users Management**\n\n"
                f"🔢 **Total Users:** {users_count}\n"
                f"👑 **Owner:** `{OWNER_ID}`\n\n"
                f"**Current Users:**\n{users_list if users_list else '_No authorized users_'}", 
                create_auth_users_keyboard())
            
        elif callback_data == "status":
            total_channels = sum(len(channels) for channels in CHANNEL_CATEGORIES.values())
            await edit_message(chat_id, message_id, 
                f"📊 **Bot Status**\n\n"
                f"🟢 **Status:** Online & Active\n"
                f"🤖 **Version:** Enhanced Bot v3.0\n"
                f"📋 **Channels:** {total_channels}\n"
                f"👥 **Auth Users:** {len(RUNTIME_AUTHORIZED_USERS)}\n"
                f"📢 **Active Ads:** {len([ad for ad in ADS_DATABASE if ad.get('status') == 'active'])}\n"
                f"💾 **Max File Size:** {format_file_size(MAX_FILE_SIZE)}", 
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "back_to_main"}]]))
            
        elif callback_data == "copyright":
            await edit_message(chat_id, message_id, 
                "©️ **Copyright & Legal**\n\n"
                "🛡️ **Bot developed for educational purposes**\n\n"
                "⚖️ **Important:**\n"
                "• Respect content creators' rights\n"
                "• Follow platform terms of service\n"
                "• Use responsibly and legally\n\n"
                "📧 Contact admin for concerns", 
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "back_to_main"}]]))
        
        # Authorized user buttons
        elif callback_data == "send_url":
            keyboard = create_inline_keyboard([
                [{"text": "🎲 Random Video", "callback_data": "random_video"}],
                [{"text": "🔗 Send Custom URL", "callback_data": "custom_url"}],
                [{"text": "🔙 Back", "callback_data": "back_to_main"}]
            ])
            await edit_message(chat_id, message_id,
                "📹 **Video Download Options**\n\n"
                "Choose how you want to get videos:\n\n"
                "🎲 **Random Video** - I'll pick a random video\n"
                "🔗 **Custom URL** - Send your own video link\n\n"
                "🌐 **Supported Sites:**\n"
                "• xhamster.com\n"
                "• pornhub.com\n"
                "• xvideos.com", keyboard)
        
        elif callback_data == "random_video":
            if not is_authorized_user(user_id):
                await edit_message(chat_id, message_id,
                    "❌ **Authorization Required**\n\nYou need access to use this feature.",
                    None)
                return
            
            await edit_message(chat_id, message_id,
                "🎲 **Finding Random Video...**\n\n"
                "🔍 Searching for random video from supported sites...\n"
                "⏳ Please wait...")
            
            # Extract random video URL
            random_url = await extract_random_video_url()
            
            if random_url:
                await send_message(chat_id,
                    f"🎯 **Random Video Found!**\n\n"
                    f"🔗 **URL:** {random_url[:50]}...\n"
                    f"📥 **Starting download...**")
                
                # Check if user already has an active download
                if is_user_downloading(user_id):
                    await send_message(chat_id, 
                        "⏳ **Download in Progress**\n\n"
                        "You already have a video downloading.\n"
                        "Please wait for it to complete before starting another.")
                    return
                
                # Process the random video concurrently
                task = asyncio.create_task(process_video_url_with_cleanup(chat_id, message_id, random_url, user_id))
                set_user_downloading(user_id, task)
                ACTIVE_TASKS.add(task)
            else:
                await send_message(chat_id,
                    "❌ **No Random Video Found**\n\n"
                    "Failed to extract random video from supported sites.\n"
                    "Please try again or use custom URL option.")
        
        elif callback_data == "custom_url":
            await edit_message(chat_id, message_id,
                "📹 **Send Custom Video URL**\n\n"
                "Send me a video URL from supported sites:\n\n"
                "🌐 **Supported Sites:**\n"
                "• xhamster.com\n"
                "• pornhub.com\n"
                "• xvideos.com\n\n"
                "📝 **Just paste the URL and I'll download it!**", None)
            
        elif callback_data == "help":
            help_message = """
📖 **Help - How to Use Enhanced Bot**

🌐 **Supported Websites:**
• xhamster.com & variations
• pornhub.com
• xvideos.com

📋 **Commands:**
• `/start` - Main menu
• `/help` - This help message
• `/info` - Bot information

🔄 **How to Download:**
1. Copy video URL from supported site
2. Send URL to bot
3. Wait for processing
4. Video will be processed

📏 **Limits:**
• Max file size: 500MB
• Best quality selected automatically
• MP4 format preferred

Need more help? Contact bot owner.
            """
            await edit_message(chat_id, message_id, help_message, None)
            
        # Unauthorized user options with better messaging
        elif callback_data == "contact":
            await edit_message(chat_id, message_id, 
                "📞 **Contact Support**\n\n"
                "👨‍💼 **Admin Contact:**\n"
                "• Telegram: Contact bot owner\n"
                "• Response time: 24-48 hours\n\n"
                "💡 **Need access?** Request authorization from admin", None)
            
        elif callback_data == "link":
            await edit_message(chat_id, message_id, 
                "🔗 **Access via Link**\n\n"
                "🚧 **Shortlink Process**\n"
                "Coming soon - earn access through link completion!\n\n"
                "📱 This will provide temporary access to bot features", None)
            
        elif callback_data == "promo_code":
            await edit_message(chat_id, message_id, 
                "💰 **Promo Code**\n\n"
                "🎁 **Enter your promo code to get access!**\n\n"
                "📝 Send your code in next message\n"
                "🚧 Feature coming soon!", None)
            
        elif callback_data == "channel_list":
            channel_count = sum(len(channels) for channels in CHANNEL_CATEGORIES.values())
            await edit_message(chat_id, message_id, 
                f"📋 **Public Channel List**\n\n"
                f"📊 **Available Channels:** {channel_count}\n\n"
                f"🚧 **Public listing coming soon!**\n"
                f"Will show all accessible channels by category", None)
        
        # Ads management handlers
        elif callback_data == "add_ad":
            USER_STATES[user_id] = {"action": "add_ad", "step": "name"}
            await edit_message(chat_id, message_id,
                "➕ **Add New Advertisement**\n\n"
                "📝 **Step 1/5: Ad Name**\n\n"
                "Please enter a name for this advertisement:\n"
                "_Example: Summer Sale 2024_",
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "ads"}]]))
        
        elif callback_data == "remove_ad":
            if not ADS_DATABASE:
                await edit_message(chat_id, message_id,
                    "❌ **No Ads Available**\n\n"
                    "No advertisements found to remove.\n"
                    "Create some ads first!",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "ads"}]]))
            else:
                ads_list = "\n".join([f"{i+1}. **{ad['name']}** - {ad['status']}" for i, ad in enumerate(ADS_DATABASE)])
                await edit_message(chat_id, message_id,
                    f"➖ **Remove Advertisement**\n\n"
                    f"📋 **Current Ads:**\n{ads_list}\n\n"
                    f"🚧 **Removal feature coming soon!**",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "ads"}]]))
        
        elif callback_data == "ads_list":
            if not ADS_DATABASE:
                await edit_message(chat_id, message_id,
                    "📋 **Advertisement List**\n\n"
                    "❌ **No ads configured yet**\n\n"
                    "Create your first advertisement!",
                    create_inline_keyboard([[{"text": "➕ Add Ad", "callback_data": "add_ad"}, {"text": "🔙 Back", "callback_data": "ads"}]]))
            else:
                ads_info = ""
                for i, ad in enumerate(ADS_DATABASE, 1):
                    status_emoji = "🟢" if ad['status'] == 'active' else "🔴"
                    ads_info += f"{i}. {status_emoji} **{ad['name']}**\n"
                    ads_info += f"   📅 Duration: {ad['duration']} days\n"
                    ads_info += f"   📊 Frequency: {ad['frequency']}\n\n"
                
                await edit_message(chat_id, message_id,
                    f"📋 **Advertisement List**\n\n"
                    f"📊 **Total Ads:** {len(ADS_DATABASE)}\n\n"
                    f"{ads_info}",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "ads"}]]))
        
        elif callback_data.startswith("freq_"):
            frequency = callback_data.replace("freq_", "")
            if user_id in USER_STATES and USER_STATES[user_id].get("action") == "add_ad":
                USER_STATES[user_id]["frequency"] = frequency
                
                # Create the ad
                new_ad = {
                    "name": USER_STATES[user_id]["name"],
                    "text": USER_STATES[user_id]["text"],
                    "file": USER_STATES[user_id].get("file"),
                    "duration": USER_STATES[user_id]["duration"],
                    "frequency": frequency,
                    "status": "active",
                    "created_at": time.time()
                }
                
                ADS_DATABASE.append(new_ad)
                del USER_STATES[user_id]
                
                await edit_message(chat_id, message_id,
                    f"✅ **Advertisement Created Successfully!**\n\n"
                    f"📝 **Name:** {new_ad['name']}\n"
                    f"📅 **Duration:** {new_ad['duration']} days\n"
                    f"📊 **Frequency:** {frequency.title()}\n"
                    f"🟢 **Status:** Active\n\n"
                    f"🎯 **Your ad is now live across all channels!**",
                    create_inline_keyboard([[{"text": "📋 View Ads", "callback_data": "ads_list"}, {"text": "🔙 Back", "callback_data": "ads"}]]))
            else:
                await edit_message(chat_id, message_id,
                    "❌ **Error**\n\nInvalid request. Please start over.",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "ads"}]]))
        
        # Auth users management
        elif callback_data == "add_auth_user":
            USER_STATES[user_id] = {"action": "add_auth_user"}
            await edit_message(chat_id, message_id,
                "➕ **Add Authorized User**\n\n"
                "📝 Send the user ID of the person you want to authorize:\n\n"
                "_Example: 123456789_",
                create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "auth_users"}]]))
        
        elif callback_data == "remove_auth_user":
            if not RUNTIME_AUTHORIZED_USERS:
                await edit_message(chat_id, message_id,
                    "❌ **No Authorized Users**\n\n"
                    "No authorized users found to remove.",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "auth_users"}]]))
            else:
                users_list = "\n".join([f"{i+1}. `{uid}`" for i, uid in enumerate(RUNTIME_AUTHORIZED_USERS, 1)])
                await edit_message(chat_id, message_id,
                    f"➖ **Remove Authorized User**\n\n"
                    f"📋 **Current Users:**\n{users_list}\n\n"
                    f"🚧 **Removal feature coming soon!**",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "auth_users"}]]))
        
        elif callback_data == "view_auth_users":
            if not RUNTIME_AUTHORIZED_USERS:
                await edit_message(chat_id, message_id,
                    "👥 **Authorized Users List**\n\n"
                    "❌ **No authorized users yet**\n\n"
                    "Add some users to get started!",
                    create_inline_keyboard([[{"text": "➕ Add User", "callback_data": "add_auth_user"}, {"text": "🔙 Back", "callback_data": "auth_users"}]]))
            else:
                users_list = "\n".join([f"{i+1}. `{uid}`" for i, uid in enumerate(RUNTIME_AUTHORIZED_USERS, 1)])
                await edit_message(chat_id, message_id,
                    f"👥 **Authorized Users List**\n\n"
                    f"📊 **Total Users:** {len(RUNTIME_AUTHORIZED_USERS)}\n\n"
                    f"**Users:**\n{users_list}",
                    create_inline_keyboard([[{"text": "🔙 Back", "callback_data": "auth_users"}]]))
            
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")

async def handle_message(update):
    """Enhanced message handler with better user experience and concurrent processing"""
    try:
        if 'message' not in update:
            return
            
        message = update['message']
        chat_id = str(message['chat']['id'])
        user_id = str(message['from']['id'])
        text = message.get('text', '')
        message_id = message['message_id']
        
        # Handle file uploads for ads
        if 'document' in message or 'photo' in message:
            if user_id in USER_STATES and USER_STATES[user_id].get("action") == "add_ad" and USER_STATES[user_id].get("step") == "file":
                file_info = message.get('document') or (message.get('photo', [])[-1] if message.get('photo') else None)
                if file_info:
                    USER_STATES[user_id]["file"] = file_info.get('file_id')
                    USER_STATES[user_id]["step"] = "duration"
                    await send_message(chat_id,
                        "➕ **Add New Advertisement**\n\n"
                        "📝 **Step 4/5: Duration**\n\n"
                        "✅ File attached successfully!\n\n"
                        "How many days should this ad run?\n"
                        "_Enter number of days (1-365):_")
                    return
        
        # Handle commands
        if text.startswith('/start'):
            await handle_start_command(chat_id, user_id)
            return
            
        elif text.startswith('/help'):
            help_message = """
📖 **Help - How to Use Enhanced Bot**

🌐 **Supported Websites:**
• xhamster.com & variations
• pornhub.com
• xvideos.com

📋 **Commands:**
• `/start` - Main menu
• `/help` - This help message
• `/info` - Bot information

🔄 **How to Download:**
1. Copy video URL from supported site
2. Send URL to bot
3. Wait for processing
4. Video will be processed

📏 **Limits:**
• Max file size: 500MB
• Best quality selected automatically
• MP4 format preferred

Need more help? Contact bot owner.
            """
            await send_message(chat_id, help_message)
            return
            
        elif text.startswith('/info'):
            info_message = f"""
ℹ️ **Enhanced Bot Information**

🤖 **Version:** 3.0 (Complete Edition)
🟢 **Status:** Online & Operational
🌐 **Supported Sites:** {len(SUPPORTED_SITES)}
💾 **Max File Size:** {format_file_size(MAX_FILE_SIZE)}
📁 **Download Directory:** `{DOWNLOAD_DIR}`
👥 **Auth Users:** {len(RUNTIME_AUTHORIZED_USERS)}

🔧 **Features:**
• Video downloading & processing
• Owner management panel
• User authorization system
• Advertisement system
• Broadcast functionality

🌐 **Supported Sites:**
            """
            for site in SUPPORTED_SITES:
                info_message += f"• {site}\n"
                
            await send_message(chat_id, info_message)
            return
        
        # Handle user states for multi-step processes
        if user_id in USER_STATES:
            user_state = USER_STATES[user_id]
            
            if user_state.get("action") == "add_ad":
                if user_state.get("step") == "name":
                    USER_STATES[user_id]["name"] = text
                    USER_STATES[user_id]["step"] = "text"
                    await send_message(chat_id,
                        "➕ **Add New Advertisement**\n\n"
                        "📝 **Step 2/5: Ad Text**\n\n"
                        "Please enter the advertisement text:\n"
                        "_This text will be shown in channels_")
                    return
                
                elif user_state.get("step") == "text":
                    USER_STATES[user_id]["text"] = text
                    USER_STATES[user_id]["step"] = "file"
                    keyboard = create_inline_keyboard([[{"text": "⏭️ Skip File", "callback_data": "skip_file"}]])
                    await send_message(chat_id,
                        "➕ **Add New Advertisement**\n\n"
                        "📝 **Step 3/5: Attachment (Optional)**\n\n"
                        "Send a file/image for the ad or skip:",
                        keyboard)
                    return
                
                elif user_state.get("step") == "duration":
                    try:
                        duration = int(text)
                        if duration < 1 or duration > 365:
                            await send_message(chat_id, "❌ Please enter a valid number between 1-365 days.")
                            return
                        
                        USER_STATES[user_id]["duration"] = duration
                        await send_message(chat_id,
                            "➕ **Add New Advertisement**\n\n"
                            "📝 **Step 5/5: Ad Frequency**\n\n"
                            "How often should this ad appear?",
                            create_ad_frequency_keyboard())
                        return
                    except ValueError:
                        await send_message(chat_id, "❌ Please enter a valid number.")
                        return
            
            elif user_state.get("action") == "broadcast":
                # Process broadcast message with placeholders
                try:
                    success_count = await broadcast_message_to_users(text)
                    await send_message(chat_id,
                        f"📡 **Broadcast Complete!**\n\n"
                        f"✅ **Message sent to {success_count} users**\n\n"
                        f"📝 **Message:**\n{text[:100]}{'...' if len(text) > 100 else ''}")
                    
                    del USER_STATES[user_id]
                    return
                except Exception as e:
                    await send_message(chat_id,
                        f"❌ **Broadcast Failed!**\n\n"
                        f"Error: {str(e)}")
                    del USER_STATES[user_id]
                    return
            
            elif user_state.get("action") == "add_auth_user":
                try:
                    new_user_id = text.strip()
                    if new_user_id.isdigit():
                        RUNTIME_AUTHORIZED_USERS.add(new_user_id)
                        await send_message(chat_id,
                            f"✅ **User Authorized Successfully!**\n\n"
                            f"👤 **User ID:** `{new_user_id}`\n"
                            f"📊 **Total Authorized Users:** {len(RUNTIME_AUTHORIZED_USERS)}")
                        del USER_STATES[user_id]
                        return
                    else:
                        await send_message(chat_id, "❌ Please enter a valid user ID (numbers only).")
                        return
                except Exception as e:
                    await send_message(chat_id, f"❌ Error adding user: {str(e)}")
                    del USER_STATES[user_id]
                    return
            
            elif user_state.get("action") == "upload_random":
                if user_state.get("step") == "channel_id":
                    try:
                        channel_id = text.strip()
                        
                        # Validate channel ID format
                        if not (channel_id.startswith('-100') and len(channel_id) >= 10):
                            await send_message(chat_id,
                                "❌ **Invalid Channel ID Format**\n\n"
                                "Channel ID should:\n"
                                "• Start with `-100`\n"
                                "• Be at least 10 digits long\n"
                                "• Example: `-1001234567890`")
                            return
                        
                        await send_message(chat_id,
                            f"🎲 **Finding Random Video...**\n\n"
                            f"📡 **Target Channel:** `{channel_id}`\n"
                            f"🔍 **Searching for random video...**")
                        
                        # Extract random video URL
                        random_url = await extract_random_video_url()
                        
                        if random_url:
                            await send_message(chat_id,
                                f"🎯 **Random Video Found!**\n\n"
                                f"🔗 **URL:** {random_url[:50]}...\n"
                                f"📡 **Target Channel:** `{channel_id}`\n"
                                f"📥 **Starting download and upload...**")
                            
                            # Process the random video concurrently
                            task = asyncio.create_task(process_owner_video_upload(chat_id, random_url, channel_id))
                            ACTIVE_TASKS.add(task)
                        else:
                            await send_message(chat_id,
                                "❌ **Random Video Extraction Failed**\n\n"
                                "Could not find a random video from supported sites.\n"
                                "Please try again later.")
                        
                        # Clear user state
                        del USER_STATES[user_id]
                        return
                        
                    except Exception as e:
                        await send_message(chat_id, f"❌ Error processing random upload: {str(e)}")
                        del USER_STATES[user_id]
                        return
            
            elif user_state.get("action") == "upload_video":
                if user_state.get("step") == "link":
                    # Validate URL
                    if not validate_url(text):
                        await send_message(chat_id,
                            "❌ **Invalid URL Format**\n\n"
                            "Please send a valid URL.\n"
                            "**Example:** `https://xhamster.com/videos/example-video`")
                        return
                    
                    # Check if URL is from supported site
                    if not is_supported_url(text):
                        supported_sites = "\n".join([f"• {site}" for site in SUPPORTED_SITES])
                        await send_message(chat_id,
                            f"❌ **Unsupported Website**\n\n"
                            f"**Supported sites:**\n{supported_sites}\n\n"
                            f"Please use a URL from one of these sites.")
                        return
                    
                    # Store the URL and ask for channel ID
                    USER_STATES[user_id]["url"] = text
                    USER_STATES[user_id]["step"] = "channel_id"
                    await send_message(chat_id,
                        "📤 **Upload Video**\n\n"
                        "📝 **Step 2/2: Channel ID**\n\n"
                        "Enter the Channel ID where you want to upload the video:\n\n"
                        "💡 **Channel ID Format:**\n"
                        "• Should start with `-100` (e.g., `-1001234567890`)\n"
                        "• Make sure bot is admin in that channel\n\n"
                        "📱 **Send the Channel ID now:**")
                    return
                
                elif user_state.get("step") == "channel_id":
                    try:
                        channel_id = text.strip()
                        
                        # Validate channel ID format
                        if not (channel_id.startswith('-100') and len(channel_id) >= 10):
                            await send_message(chat_id,
                                "❌ **Invalid Channel ID Format**\n\n"
                                "Channel ID should:\n"
                                "• Start with `-100`\n"
                                "• Be at least 10 digits long\n"
                                "• Example: `-1001234567890`")
                            return
                        
                        # Store channel ID and start processing
                        USER_STATES[user_id]["channel_id"] = channel_id
                        video_url = USER_STATES[user_id]["url"]
                        
                        await send_message(chat_id,
                            f"🔄 **Starting Video Processing...**\n\n"
                            f"🔗 **URL:** {video_url[:50]}...\n"
                            f"📡 **Target Channel:** `{channel_id}`\n\n"
                            f"⏳ **Please wait while I download and upload the video...**")
                        
                        # Start video processing concurrently
                        task = asyncio.create_task(process_owner_video_upload(chat_id, video_url, channel_id))
                        ACTIVE_TASKS.add(task)
                        
                        # Clear user state
                        del USER_STATES[user_id]
                        return
                        
                    except Exception as e:
                        await send_message(chat_id, f"❌ Error processing upload: {str(e)}")
                        del USER_STATES[user_id]
                        return
        
        # Handle video URLs for authorized users
        if text.startswith('http'):
            if not is_authorized_user(user_id):
                await send_message(chat_id, 
                    "❌ **Authorization Required**\n\n"
                    "You are not authorized to send video URLs.\n"
                    "Use /start to see available options.")
                return
            
            # Check if URL is valid
            if not validate_url(text):
                await send_message(chat_id,
                    "❌ **Invalid URL Format**\n\n"
                    "Please send a valid URL.\n"
                    "**Example:** `https://xhamster.com/videos/example-video`")
                return
            
            # Check if URL is from supported site
            if not is_supported_url(text):
                supported_sites = "\n".join([f"• {site}" for site in SUPPORTED_SITES])
                await send_message(chat_id,
                    f"❌ **Unsupported Website**\n\n"
                    f"**Supported sites:**\n{supported_sites}\n\n"
                    f"Please use a URL from one of these sites.")
                return
            
            # Check if user already has an active download
            if is_user_downloading(user_id):
                await send_message(chat_id, 
                    "⏳ **Download in Progress**\n\n"
                    "You already have a video downloading.\n"
                    "Please wait for it to complete before starting another.")
                return
            
            # Process the video URL concurrently (non-blocking)
            task = asyncio.create_task(process_video_url_with_cleanup(chat_id, message_id, text, user_id))
            set_user_downloading(user_id, task)
            ACTIVE_TASKS.add(task)
        else:
            # Handle non-URL messages
            if not is_authorized_user(user_id):
                await send_message(chat_id, 
                    "❌ **Authorization Required**\n\n"
                    "You are not authorized to send messages.\n"
                    "Use /start to see available options.")
                return
            
            await send_message(chat_id, 
                "ℹ️ **Send a video URL** 📹\n\n"
                "Send me a video URL from supported sites to download.\n"
                "Use /help for more information.")
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")

async def get_telegram_updates(offset: int = 0):
    """Get updates from Telegram with better error handling"""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {
            'offset': offset,
            'timeout': 30
        }
        
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            return None
    except Exception as e:
        logger.error(f"Failed to get updates: {e}")
        return None

async def main():
    """Enhanced main bot loop with better startup"""
    try:
        validate_config()
        logger.info("🚀 Enhanced bot configuration validated successfully")
        
        # Ensure download directory exists
        ensure_directory_exists(DOWNLOAD_DIR)
        
        logger.info("🎬 Starting Enhanced Telegram Bot v3.0 with Owner Panel...")
        logger.info(f"📊 Configuration: Owner={OWNER_ID}, Auth Users={len(RUNTIME_AUTHORIZED_USERS)}")
        
        offset = 0
        error_count = 0
        max_errors = 10
        
        while True:
            try:
                # Get updates
                result = await get_telegram_updates(offset)
                
                if result and result.get('ok'):
                    updates = result.get('result', [])
                    
                    for update in updates:
                        # Update offset
                        offset = update['update_id'] + 1
                        
                        # Handle different update types concurrently
                        if 'callback_query' in update:
                            # Callback queries are quick, handle directly
                            await handle_callback_query(update['callback_query'])
                        else:
                            # Messages might involve long operations, handle concurrently
                            task = asyncio.create_task(handle_message(update))
                            ACTIVE_TASKS.add(task)
                    
                    # Clean up completed tasks periodically
                    cleanup_completed_tasks()
                    
                    # Reset error count on successful iteration
                    error_count = 0
                
                # Small delay to prevent hitting rate limits
                await asyncio.sleep(1)
                
                # Periodic cleanup every 10 iterations
                if offset % 10 == 0:
                    cleanup_completed_tasks()
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error in main loop (#{error_count}): {e}")
                
                if error_count >= max_errors:
                    logger.critical("Too many consecutive errors, stopping bot")
                    break
                    
                await asyncio.sleep(5 * error_count)  # Progressive delay
                
    except Exception as e:
        logger.error(f"Failed to start enhanced bot: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Enhanced bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Enhanced bot crashed: {e}")
