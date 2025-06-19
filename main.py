import os             
import json        
import logging    
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup          
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes         
import yt_dlp      
import asyncio
from urllib.parse import urlparse, parse_qs
import shutil
import threading
from datetime import datetime

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Token - Get from environment variable or use default
BOT_TOKEN = os.getenv("BOT_TOKEN")
LIVE_LOG_CHANNEL_ID = os.getenv("LIVE_LOG_CHANNEL_ID")
DOWNLOAD_LOG_CHANNEL_ID = os.getenv("DOWNLOAD_LOG_CHANNEL_ID")

# Files to store data
DATA_FILE = "video_data.json"
USERS_FILE = "users_data.json"

class YouTubeBot:
    def __init__(self):
        self.video_data = self.load_data()
        self.users_data = self.load_users_data()

    def load_data(self):
        """Load saved video data from file"""
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return {}

    def load_users_data(self):
        """Load saved users data from file with grouped structure"""
        try:
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            # Initialize empty structure for all digits 0-9
            return {f"Users_{i}": [] for i in range(10)}
        except Exception as e:
            logger.error(f"Error loading users data: {e}")
            return {f"Users_{i}": [] for i in range(10)}

    def save_data(self):
        """Save video data to file"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.video_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def save_users_data(self):
        """Save users data to file with grouped structure"""
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving users data: {e}")

    def get_user_group(self, user_id):
        """Get user group based on first digit of user ID"""
        first_digit = str(user_id)[0]
        return f"Users_{first_digit}"

    def add_user(self, user_id):
        """Add new user to appropriate group and save to file"""
        user_id_str = str(user_id)
        group_key = self.get_user_group(user_id)

        # Add user to appropriate group if not already exists
        if user_id_str not in self.users_data[group_key]:
            self.users_data[group_key].append(user_id_str)
            self.save_users_data()

    def is_returning_user(self, user_id):
        """Check if user has used bot before (efficient group-based search)"""
        user_id_str = str(user_id)
        group_key = self.get_user_group(user_id)
        return user_id_str in self.users_data[group_key]

    def extract_video_id(self, url):
        """Extract video ID from YouTube URL (supports all YouTube URL formats)"""
        try:
            # Handle different URL formats
            if 'youtu.be/' in url:
                return url.split('youtu.be/')[-1].split('?')[0].split('&')[0]
            elif 'youtube.com' in url:
                parsed_url = urlparse(url)
                # Handle /watch?v= format
                if 'v=' in parsed_url.query:
                    return parse_qs(parsed_url.query).get('v', [None])[0]
                # Handle /embed/ format
                elif '/embed/' in parsed_url.path:
                    return parsed_url.path.split('/embed/')[-1].split('?')[0]
                # Handle /v/ format
                elif '/v/' in parsed_url.path:
                    return parsed_url.path.split('/v/')[-1].split('?')[0]
            elif 'oauth-redirect.googleusercontent.com' in url and 'youtube.com' in url:
                # Extract from redirect URL
                if 'v=' in url:
                    return url.split('v=')[-1].split('&')[0]
            return None
        except Exception as e:
            logger.error(f"Error extracting video ID: {e}")
            return None

    def is_youtube_url(self, url):
        """Check if URL is a valid YouTube URL (supports all YouTube domains)"""
        youtube_domains = [
            'youtube.com', 'youtu.be', 'www.youtube.com',
            'm.youtube.com', 'music.youtube.com', 'gaming.youtube.com',
            'studio.youtube.com', 'oauth-redirect.googleusercontent.com'
        ]
        try:
            parsed = urlparse(url.lower())
            return any(domain in parsed.netloc for domain in youtube_domains)
        except:
            return False

    async def get_video_info(self, url):
        """Get video information using yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown')
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None

bot_instance = YouTubeBot()

def send_logs_to_channel():
    """Send current console logs to specified channel"""
    try:
        # Read recent logs (you can implement log file reading here)
        log_message = "🔧 **Bot Status Update**\n\n"
        log_message += "✅ Bot is running normally\n"
        log_message += "📊 Current issues resolved:\n"
        log_message += "- Event loop error fixed\n"
        log_message += "- Quality detection improved\n"
        log_message += "- Fallback mechanism enhanced\n\n"
        log_message += f"🕒 **Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Send to specified channel
        bot_token = BOT_TOKEN
        channel_id = "-1002727649483"

        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={
                'chat_id': channel_id,
                'text': log_message,
                'parse_mode': 'Markdown'
            }
        )

        logger.info("Logs sent to channel successfully")

    except Exception as e:
        logger.error(f"Error sending logs to channel: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = str(user.id)

    # Check if user is new or returning
    if not bot_instance.is_returning_user(user_id):
        # First time user
        welcome_msg = f"""
🎉 **Welcome to YouTube Downloader Bot!** 🎉

Hello {user.first_name}! 👋

मैं आपका YouTube Video Downloader Bot हूं! 🤖

**मैं क्या कर सकता हूं:**
📹 YouTube videos download कर सकता हूं
🎬 Multiple quality options provide करता हूं (240p, 360p, 480p, 1080p)
⚡ Previously downloaded videos को instantly भेजता हूं
💾 आपकी files को save करता हूं faster access के लिए

**कैसे use करें:**
बस मुझे कोई भी YouTube link भेज दें! 🔗

Let's get started! 🚀
        """

        # Add user to database
        bot_instance.add_user(user_id)

    else:
        # Returning user
        welcome_msg = f"""
👋 **Welcome back, {user.first_name}!**

Ready to download some awesome videos? 🎬

बस मुझे YouTube link भेज दें और मैं आपके लिए download कर दूंगा! ⚡

**Available Qualities:** 240p | 360p | 480p | 1080p 📺
        """

    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    message_text = update.message.text

    if not bot_instance.is_youtube_url(message_text):
        await update.message.reply_text(
            "❌ **Invalid YouTube URL!**\n\n"
            "कृपया एक valid YouTube link भेजें।\n"
            "**Supported formats:**\n"
            "• https://youtu.be/VIDEO_ID\n"
            "• https://www.youtube.com/watch?v=VIDEO_ID\n"
            "• https://m.youtube.com/watch?v=VIDEO_ID\n"
            "• https://youtube.com/watch?v=VIDEO_ID",
            parse_mode='Markdown'
        )
        return

    video_id = bot_instance.extract_video_id(message_text)
    if not video_id:
        await update.message.reply_text("❌ Unable to extract video ID from URL!")
        return

    # Check if video already exists in database
    if video_id in bot_instance.video_data:
        await show_quality_options(update, context, message_text, video_id, cached=True)
    else:
        # Get video info first (but don't save to database yet)
        status_msg = await update.message.reply_text("🔍 **Getting video information...**", parse_mode='Markdown')

        video_info = await bot_instance.get_video_info(message_text)
        if not video_info:
            await status_msg.edit_text("❌ **Error:** Unable to fetch video information!")
            return

        await status_msg.delete()
        await show_quality_options_new(update, context, message_text, video_id, video_info)

async def show_quality_options(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, video_id: str, cached: bool = False):
    """Show quality selection buttons for cached video"""
    video_data = bot_instance.video_data[video_id]

    # Create keyboard with quality options
    keyboard = []
    qualities = ['240p', '360p', '480p', '1080p']

    for i in range(0, len(qualities), 2):
        row = []
        for j in range(2):
            if i + j < len(qualities):
                quality = qualities[i + j]
                # Check if file exists
                if video_data['qualities'].get(quality):
                    button_text = f"✅ {quality}"
                else:
                    button_text = f"📱 {quality}"
                row.append(InlineKeyboardButton(button_text, callback_data=f"download_{video_id}_{quality}"))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = f"""
🎬 **Video Found in Database!**

**📺 Title:** {video_data['title'][:50]}{'...' if len(video_data['title']) > 50 else ''}
**👤 Channel:** {video_data['uploader']}
**⏱️ Duration:** {video_data['duration']//60}:{video_data['duration']%60:02d}

**Select Quality:**
✅ = Already downloaded (instant)
📱 = Need to download
    """

    await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_quality_options_new(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, video_id: str, video_info: dict):
    """Show quality selection buttons for new video (not saved yet)"""
    # Create keyboard with quality options
    keyboard = []
    qualities = ['240p', '360p', '480p', '1080p']

    for i in range(0, len(qualities), 2):
        row = []
        for j in range(2):
            if i + j < len(qualities):
                quality = qualities[i + j]
                button_text = f"📱 {quality}"
                row.append(InlineKeyboardButton(button_text, callback_data=f"download_new_{video_id}_{quality}"))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = f"""
🎬 **Ready to Download!**

**📺 Title:** {video_info['title'][:50]}{'...' if len(video_info['title']) > 50 else ''}
**👤 Channel:** {video_info['uploader']}
**⏱️ Duration:** {video_info['duration']//60}:{video_info['duration']%60:02d}

**Select Quality:**
    """

    # Store temp video info in context for later use
    context.user_data[f'temp_{video_id}'] = {
        'url': url,
        'title': video_info['title'],
        'uploader': video_info['uploader'],
        'duration': video_info['duration']
    }

    await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith('download_'):
        parts = query.data.split('_')

        if parts[1] == 'new':
            # Handle new video download
            video_id = parts[2]
            quality = parts[3]

            # Get temp video info from context
            temp_key = f'temp_{video_id}'
            if temp_key not in context.user_data:
                await query.edit_message_text("❌ **Error:** Video data expired!")
                return

            video_info = context.user_data[temp_key]
            await download_and_send_video_new(query, video_info, quality, video_id, context)

        else:
            # Handle cached video
            video_id = parts[1]
            quality = parts[2]

            if video_id not in bot_instance.video_data:
                await query.edit_message_text("❌ **Error:** Video data not found!")
                return

            video_data = bot_instance.video_data[video_id]

            # Check if file already exists
            if video_data['qualities'].get(quality):
                await send_cached_video(query, video_data, quality)
            else:
                await download_and_send_video(query, video_data, quality, video_id)

async def send_cached_video(query, video_data, quality):
    """Send already cached video file"""
    file_id = video_data['qualities'][quality]

    await query.edit_message_text(f"📤 **Sending {quality} video...**", parse_mode='Markdown')

    try:
        await query.message.reply_video(
            video=file_id,
            caption=f"📱 **Quality:** {quality}\n🎬 **Title:** {video_data['title']}",
            supports_streaming=True
        )
        await query.message.delete()
    except Exception as e:
        logger.error(f"Error sending cached video: {e}")
        await query.edit_message_text("❌ **Error:** Unable to send cached video. Try downloading again.")

async def download_and_send_video_new(query, video_info, quality, video_id, context):
    """Download and send video for new entry"""
    await query.edit_message_text(f"⬇️ **Downloading {quality} video...**\n*Please wait...*", parse_mode='Markdown')

    # Enhanced quality mapping with more fallback options
    quality_formats = {
        '240p': [
            'worst[height<=240]',
            'worst[height<=360]/worst[height<=240]',
            'worst[ext=mp4][height<=240]',
            'worst[ext=webm][height<=240]',
            'worst[height<=360]',
            'worst'
        ],
        '360p': [
            'worst[height<=360]',
            'best[height<=360]/worst[height<=360]',
            'worst[ext=mp4][height<=360]',
            'worst[ext=webm][height<=360]',
            'worst[height<=480]',
            'worst'
        ],
        '480p': [
            'best[height<=480]',
            'worst[height<=480]',
            'best[ext=mp4][height<=480]',
            'best[ext=webm][height<=480]',
            'best[height<=720]/worst[height<=480]',
            'best[height<=480]/worst'
        ],
        '1080p': [
            'best[height<=1080]',
            'best[ext=mp4][height<=1080]',
            'best[ext=webm][height<=1080]',
            'best[height<=720]',
            'best[height<=1080]/best',
            'best'
        ]
    }

    # Check if video already exists in database and has requested quality
    if video_id in bot_instance.video_data:
        existing_data = bot_instance.video_data[video_id]
        if existing_data['qualities'].get(quality):
            # Use existing file ID
            file_id = existing_data['qualities'][quality]
            await query.edit_message_text(f"📤 **Sending {quality} video...**", parse_mode='Markdown')

            try:
                await query.message.reply_video(
                    video=file_id,
                    caption=f"📱 **Quality:** {quality}\n🎬 **Title:** {video_info['title']}",
                    supports_streaming=True
                )
                await query.message.delete()
                return
            except Exception as e:
                logger.error(f"Error sending cached video: {e}")
                # Continue to download if cached fails

    filename = f"{video_id}_temp.%(ext)s"

    # Try different format options
    downloaded_quality = None
    for format_option in quality_formats[quality]:
        ydl_opts = {
            'format': format_option,
            'outtmpl': f'downloads/{filename}',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'ignoreerrors': False,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'prefer_ffmpeg': True,
            'postprocessors': []
        }

        # Add FFmpeg postprocessor if available
        if shutil.which('ffmpeg'):
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            })

        try:
            # Create downloads directory if it doesn't exist
            os.makedirs('downloads', exist_ok=True)

            # First try to get actual available formats info
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'listformats': True}) as ydl_info:
                    info = ydl_info.extract_info(video_info['url'], download=False)
                    available_formats = info.get('formats', [])

                    # Log available formats for debugging
                    print(f"DEBUG: Available formats for quality {quality}:")
                    for fmt in available_formats[:5]:  # Show first 5 formats
                        print(f"  - Height: {fmt.get('height', 'N/A')}, Format: {fmt.get('format_id', 'N/A')}")
            except:
                available_formats = []

            # Download video with enhanced detection
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Extract info about what will be downloaded
                    extract_info = ydl.extract_info(video_info['url'], download=False)
                    requested_format = extract_info.get('requested_formats', [])
                    if requested_format and len(requested_format) > 0:
                        actual_height = requested_format[0].get('height', 0)
                    else:
                        # Fallback to direct format info
                        actual_height = extract_info.get('height', 0)

                    print(f"DEBUG: Selected format height: {actual_height} for requested {quality}")

                    # Now download
                    ydl.download([video_info['url']])

                    # Determine quality based on actual selected format
                    if actual_height and actual_height <= 240:
                        downloaded_quality = '240p'
                    elif actual_height and actual_height <= 360:
                        downloaded_quality = '360p'
                    elif actual_height and actual_height <= 480:
                        downloaded_quality = '480p'
                    elif actual_height and actual_height <= 720:
                        downloaded_quality = '720p'
                    else:
                        downloaded_quality = '1080p'

                    print(f"DEBUG: Detected quality: {downloaded_quality}")

                except Exception as e:
                    logger.error(f"Error in download process: {e}")
                    downloaded_quality = quality  # Fallback to requested

            # Find downloaded file
            downloaded_file = None
            for file in os.listdir('downloads'):
                if file.startswith(f"{video_id}_temp"):
                    downloaded_file = f"downloads/{file}"
                    break

            if downloaded_file and os.path.exists(downloaded_file):
                # Final quality check based on file size if height detection failed
                if not downloaded_quality or downloaded_quality == quality:
                    file_size = os.path.getsize(downloaded_file)
                    duration_minutes = video_info.get('duration', 300) / 60  # Default 5 min if unknown

                    # Quality estimation based on file size per minute
                    size_per_minute = file_size / duration_minutes / (1024 * 1024)  # MB per minute

                    if size_per_minute < 1.5:  # Less than 1.5MB per minute
                        downloaded_quality = '240p'
                    elif size_per_minute < 3:  # Less than 3MB per minute
                        downloaded_quality = '360p'
                    elif size_per_minute < 6:  # Less than 6MB per minute
                        downloaded_quality = '480p'
                    else:
                        downloaded_quality = '1080p'

                    print(f"DEBUG: File size based quality detection: {downloaded_quality} (Size: {file_size/1024/1024:.1f}MB, Rate: {size_per_minute:.1f}MB/min)")

                print(f"DEBUG: Final detected quality: {downloaded_quality} for requested: {quality}")

                # Check if we already have this detected quality cached
                if video_id in bot_instance.video_data:
                    existing_data = bot_instance.video_data[video_id]
                    if existing_data['qualities'].get(downloaded_quality):
                        # Use existing file ID for detected quality
                        file_id = existing_data['qualities'][downloaded_quality]

                        # Clean up downloaded file since we have cached version
                        os.remove(downloaded_file)

                        quality_message = downloaded_quality
                        note_message = f"\n*Note: {quality} was not available, sending {downloaded_quality}*" if downloaded_quality != quality else ""

                        await query.edit_message_text(f"📤 **Sending {quality_message} video...**\n*(Found in cache)*", parse_mode='Markdown')

                        try:
                            await query.message.reply_video(
                                video=file_id,
                                caption=f"📱 **Quality:** {quality_message}\n🎬 **Title:** {video_info['title']}{note_message}",
                                supports_streaming=True
                            )
                            await query.message.delete()
                            return
                        except Exception as e:
                            logger.error(f"Error sending cached video: {e}")
                            # Continue to upload new file if cached fails

                # Upload new video file
                quality_message = downloaded_quality
                note_message = f"\n*Note: {quality} was not available, downloaded {downloaded_quality}*" if downloaded_quality != quality else ""

                await query.edit_message_text(f"📤 **Uploading {quality_message} video...**", parse_mode='Markdown')

                # Send video
                with open(downloaded_file, 'rb') as video_file:
                    message = await query.message.reply_video(
                        video=video_file,
                        caption=f"📱 **Quality:** {quality_message}\n🎬 **Title:** {video_info['title']}{note_message}",
                        supports_streaming=True
                    )

                    # Save to database with correct detected quality
                    file_id = message.video.file_id

                    if video_id not in bot_instance.video_data:
                        bot_instance.video_data[video_id] = {
                            'url': video_info['url'],
                            'title': video_info['title'],
                            'uploader': video_info['uploader'],
                            'duration': video_info['duration'],
                            'qualities': {}
                        }
                        # Initialize all qualities as None
                        for q in ['240p', '360p', '480p', '1080p']:
                            bot_instance.video_data[video_id]['qualities'][q] = None

                    # Save file_id with detected quality (not requested quality)
                    bot_instance.video_data[video_id]['qualities'][downloaded_quality] = file_id
                    bot_instance.save_data()

                # Clean up downloaded file
                os.remove(downloaded_file)

                # Clean up temp data
                temp_key = f'temp_{video_id}'
                if temp_key in context.user_data:
                    del context.user_data[temp_key]

                await query.message.delete()
                return

        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp error with format {format_option}: {e}")
            # Clean up any partial downloads
            for file in os.listdir('downloads'):
                if file.startswith(f"{video_id}_temp"):
                    try:
                        os.remove(f"downloads/{file}")
                    except:
                        pass
            continue
        except Exception as e:
            logger.error(f"Unexpected error with format {format_option}: {e}")
            # Clean up any partial downloads
            for file in os.listdir('downloads'):
                if file.startswith(f"{video_id}_temp"):
                    try:
                        os.remove(f"downloads/{file}")
                    except:
                        pass
            continue

    # If all formats failed, try ultimate fallback
    try:
        # Try with just 'best' format as last resort
        ydl_opts_fallback = {
            'format': 'best[height<=720]/best',
            'outtmpl': f'downloads/{filename}',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
            ydl.download([video_info['url']])

        # Find downloaded file
        downloaded_file = None
        for file in os.listdir('downloads'):
            if file.startswith(f"{video_id}_temp"):
                downloaded_file = f"downloads/{file}"
                break

        if downloaded_file and os.path.exists(downloaded_file):
            # Use file size to estimate quality
            file_size = os.path.getsize(downloaded_file)
            duration_minutes = video_info.get('duration', 300) / 60
            size_per_minute = file_size / duration_minutes / (1024 * 1024)

            if size_per_minute < 2:
                fallback_quality = '240p'
            elif size_per_minute < 4:
                fallback_quality = '360p'
            elif size_per_minute < 8:
                fallback_quality = '480p'
            else:
                fallback_quality = '720p'

            await query.edit_message_text(f"📤 **Uploading {fallback_quality} video...**\n*({quality} not available, sending best available)*", parse_mode='Markdown')

            # Send video
            with open(downloaded_file, 'rb') as video_file:
                message = await query.message.reply_video(
                    video=video_file,
                    caption=f"📱 **Quality:** {fallback_quality}\n🎬 **Title:** {video_info['title']}\n*Note: {quality} was not available*",
                    supports_streaming=True
                )

                user = query.from_user
                log_text = (
                    f"🎬 *Video Downloaded!*\n"
                    f"👤 *User:* [{user.first_name}](tg://user?id={user.id}) (`{user.id}`)\n"
                    f"🔗 *Link:* {video_info['url'] if 'url' in video_info else video_data['url']}\n"
                    f"📥 *Quality:* {quality}\n"
                    f"🆔 *File ID:* `{message.video.file_id}`\n"
                    f"🕒 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                try:
                   requests.post(
                       f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                       data={
                           'chat_id': DOWNLOAD_LOG_CHANNEL_ID,
                           'text': log_text,
                           'parse_mode': 'Markdown'
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to send download log: {e}")

                # Save to database
                file_id = message.video.file_id
                if video_id not in bot_instance.video_data:
                    bot_instance.video_data[video_id] = {
                        'url': video_info['url'],
                        'title': video_info['title'],
                        'uploader': video_info['uploader'],
                        'duration': video_info['duration'],
                        'qualities': {q: None for q in ['240p', '360p', '480p', '1080p']}
                    }

                bot_instance.video_data[video_id]['qualities'][fallback_quality] = file_id
                bot_instance.save_data()

            os.remove(downloaded_file)

            temp_key = f'temp_{video_id}'
            if temp_key in context.user_data:
                del context.user_data[temp_key]

            await query.message.delete()
            return

    except Exception as e:
        logger.error(f"Ultimate fallback failed: {e}")

    # If everything fails
    await query.edit_message_text(
        f"❌ **Download Error:**\n"
        f"Unable to download {quality} quality.\n"
        f"This video may be:\n"
        f"• Restricted in your region\n"
        f"• Age-restricted\n"
        f"• Live stream (not downloadable)\n"
        f"• Premium content\n\n"
        f"Try a different YouTube video."
    )


def live_log_loop():
    import time
    while True:
        try:
            log_message = f"🤖 Bot is alive\n🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    'chat_id': LIVE_LOG_CHANNEL_ID,
                    'text': log_message,
                    'parse_mode': 'Markdown'
                }
            )
            time.sleep(15)
        except Exception as e:
            logger.error(f"Live log error: {e}")
            time.sleep(15)

# Start live logger in background
threading.Thread(target=live_log_loop, daemon=True).start()


def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 Bot is starting...")
    print("🚀 Bot is running! Press Ctrl+C to stop.")

    # Send startup logs
    try:
        send_logs_to_channel()
    except Exception as e:
        logger.error(f"Error sending startup logs: {e}")

    # Run the bot (this creates its own event loop)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
