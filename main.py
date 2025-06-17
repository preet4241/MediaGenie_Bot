#!/usr/bin/env python3

import os
import json
import asyncio
import tempfile
import yt_dlp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit for Telegram

# Quality mappings - each gets different resolution
VIDEO_QUALITIES = {
    '240p': 'worst[height<=360]',
    '360p': 'best[height<=480][height>240]', 
    '480p': 'best[height<=720][height>360]',
    '1080p': 'best[height>480]'
}

AUDIO_QUALITIES = {
    'low': 'bestaudio[abr<=96]/bestaudio[abr<=128]/bestaudio',
    'medium': 'bestaudio[abr<=128]/bestaudio[abr<=192]/bestaudio', 
    'high': 'bestaudio[abr<=192]/bestaudio[abr<=256]/bestaudio',
    'best': 'bestaudio/best[ext=m4a]/best[ext=mp3]/best'
}

# Messages
WELCOME_MESSAGE = """
🎬 Welcome to YouTube Downloader Bot! 🎵

I can help you download YouTube videos and audio files.
Just send me a YouTube link and I'll handle the rest!

Use the buttons below to get started:
"""

HELP_MESSAGE = """
📋 How to use this bot:

1️⃣ Send me a YouTube link
2️⃣ Choose Video or Audio download
3️⃣ Select your preferred quality
4️⃣ Wait for the download to complete

🎥 Video qualities: 240p, 360p, 480p, 1080p
🎵 Audio qualities: Low, Medium, High, Best

💡 Tip: Previously downloaded files are cached for faster delivery!
"""

ABOUT_MESSAGE = """
🤖 YouTube Downloader Bot

Version: 1.0
Developer: Telegram Bot Developer

This bot uses yt-dlp to download YouTube content and provides smart caching to avoid re-downloading the same files.

Features:
• Fast downloads with quality selection
• Smart caching system
• Progress tracking
• Multiple format support
"""

# Database Manager
class DatabaseManager:
    def __init__(self):
        self.ensure_database_structure()
    
    def ensure_database_structure(self):
        """Create database directory structure if it doesn't exist"""
        os.makedirs("database/video", exist_ok=True)
        os.makedirs("database/audio", exist_ok=True)
        
        # Initialize video quality files
        video_qualities = ['240p', '360p', '480p', '1080p']
        for quality in video_qualities:
            file_path = f"database/video/{quality}.json"
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump({}, f)
        
        # Initialize audio quality files
        audio_qualities = ['low', 'medium', 'high', 'best']
        for quality in audio_qualities:
            file_path = f"database/audio/{quality}.json"
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump({}, f)
    
    def get_cached_file(self, url: str, media_type: str, quality: str):
        """Get cached file data if exists"""
        try:
            db_dir = "database/video" if media_type == 'video' else "database/audio"
            file_path = f"{db_dir}/{quality}.json"
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get(url)
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None
    
    def save_file_data(self, url: str, media_type: str, quality: str, file_data: dict):
        """Save file data to cache"""
        try:
            db_dir = "database/video" if media_type == 'video' else "database/audio"
            file_path = f"{db_dir}/{quality}.json"
            
            # Read existing data
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Add new data
            data[url] = file_data
            
            # Write back to file
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved cache data for {url} - {media_type} {quality}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

# YouTube Downloader
class YouTubeDownloader:
    def __init__(self):
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback function for progress updates"""
        self.progress_callback = callback
    
    def progress_hook(self, d):
        """Progress hook for yt-dlp"""
        if self.progress_callback and d['status'] == 'downloading':
            try:
                percent = d.get('_percent_str', 'N/A')
                speed = d.get('_speed_str', 'N/A')
                self.progress_callback(f"Downloading... {percent} at {speed}")
            except:
                pass
    
    def get_video_info(self, url: str):
        """Get video information without downloading"""
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
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0)
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def download_video(self, url: str, quality: str):
        """Download video and return file path"""
        try:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, '%(title)s.%(ext)s')
            
            # Get format for requested quality
            format_selector = VIDEO_QUALITIES.get(quality, 'best')
            
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_path,
                'progress_hooks': [self.progress_hook],
                'quiet': True,
                'no_warnings': True,
            }
            
            # Only try the specific quality, no fallback to avoid same file
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.getsize(file_path) <= MAX_FILE_SIZE:
                    return file_path
                else:
                    os.remove(file_path)
                    raise Exception(f"File too large (max {MAX_FILE_SIZE/1024/1024}MB)")
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def download_audio(self, url: str, quality: str):
        """Download audio and return file path"""
        try:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, '%(title)s.%(ext)s')
            
            # Try with specific quality first, then fallback to bestaudio
            format_selector = AUDIO_QUALITIES.get(quality, 'bestaudio')
            
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_path,
                'progress_hooks': [self.progress_hook],
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as format_error:
                # If specific format fails, try with just 'bestaudio'
                logger.warning(f"Format {format_selector} failed, trying with 'bestaudio': {format_error}")
                ydl_opts['format'] = 'bestaudio'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            # Find downloaded file
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.getsize(file_path) <= MAX_FILE_SIZE:
                    return file_path
                else:
                    os.remove(file_path)
                    raise Exception(f"File too large (max {MAX_FILE_SIZE/1024/1024}MB)")
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None
    
    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL"""
        youtube_domains = [
            'youtube.com', 'www.youtube.com', 'youtu.be', 'www.youtu.be',
            'm.youtube.com', 'music.youtube.com'
        ]
        return any(domain in url for domain in youtube_domains)

# Bot Handlers
class BotHandlers:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.downloader = YouTubeDownloader()
        self.user_states = {}  # Track user states
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Help", callback_data='help'),
                InlineKeyboardButton("ℹ️ About", callback_data='about')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            WELCOME_MESSAGE,
            reply_markup=reply_markup
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'help':
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='back')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(HELP_MESSAGE, reply_markup=reply_markup)
        
        elif query.data == 'about':
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='back')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(ABOUT_MESSAGE, reply_markup=reply_markup)
        
        elif query.data == 'back':
            keyboard = [
                [
                    InlineKeyboardButton("📋 Help", callback_data='help'),
                    InlineKeyboardButton("ℹ️ About", callback_data='about')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(WELCOME_MESSAGE, reply_markup=reply_markup)
        
        elif query.data in ['video', 'audio']:
            user_id = query.from_user.id
            if user_id in self.user_states:
                self.user_states[user_id]['media_type'] = query.data
                await self.show_quality_selection(query, query.data)
        
        elif query.data.startswith('quality_'):
            await self.handle_quality_selection(query)
    
    async def show_quality_selection(self, query, media_type: str):
        """Show quality selection buttons"""
        if media_type == 'video':
            keyboard = [
                [InlineKeyboardButton("240p", callback_data='quality_video_240p')],
                [InlineKeyboardButton("360p", callback_data='quality_video_360p')],
                [InlineKeyboardButton("480p", callback_data='quality_video_480p')],
                [InlineKeyboardButton("1080p", callback_data='quality_video_1080p')]
            ]
            text = "🎥 Select video quality:"
        else:
            keyboard = [
                [InlineKeyboardButton("Low Quality", callback_data='quality_audio_low')],
                [InlineKeyboardButton("Medium Quality", callback_data='quality_audio_medium')],
                [InlineKeyboardButton("High Quality", callback_data='quality_audio_high')],
                [InlineKeyboardButton("Best Quality", callback_data='quality_audio_best')]
            ]
            text = "🎵 Select audio quality:"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def handle_quality_selection(self, query):
        """Handle quality selection and start download"""
        user_id = query.from_user.id
        if user_id not in self.user_states:
            await query.edit_message_text("❌ Session expired. Please send the YouTube link again.")
            return
        
        parts = query.data.split('_')
        media_type = parts[1]  # video or audio
        quality = parts[2]     # quality level
        
        url = self.user_states[user_id]['url']
        
        # Check cache first
        cached_data = self.db_manager.get_cached_file(url, media_type, quality)
        if cached_data:
            await query.edit_message_text("📁 Found in cache! Sending file...")
            
            if media_type == 'video':
                await query.message.reply_video(
                    video=cached_data['file_id'],
                    caption=f"🎬 {cached_data['title']}\n👤 {cached_data.get('uploader', 'Unknown')}"
                )
            else:
                await query.message.reply_audio(
                    audio=cached_data['file_id'],
                    caption=f"🎵 {cached_data['title']}\n👤 {cached_data.get('uploader', 'Unknown')}"
                )
            
            # Clean up user state
            del self.user_states[user_id]
            return
        
        # Download file
        await query.edit_message_text("📥 Starting download...")
        
        # Set progress callback
        progress_message = await query.message.reply_text("🔄 Preparing download...")
        
        async def update_progress(progress_text):
            try:
                await progress_message.edit_text(progress_text)
            except:
                pass
        
        self.downloader.set_progress_callback(lambda text: asyncio.create_task(update_progress(text)))
        
        # Get video info
        video_info = self.downloader.get_video_info(url)
        if not video_info:
            await progress_message.edit_text("❌ Failed to get video information.")
            del self.user_states[user_id]
            return
        
        # Download based on media type
        if media_type == 'video':
            file_path = self.downloader.download_video(url, quality)
        else:
            file_path = self.downloader.download_audio(url, quality)
        
        if not file_path:
            await progress_message.edit_text("❌ Download failed. Please try again.")
            del self.user_states[user_id]
            return
        
        await progress_message.edit_text("📤 Uploading file...")
        
        try:
            # Send file and get file_id
            if media_type == 'video':
                message = await query.message.reply_video(
                    video=open(file_path, 'rb'),
                    caption=f"🎬 {video_info['title']}\n👤 {video_info.get('uploader', 'Unknown')}"
                )
                file_id = message.video.file_id
            else:
                message = await query.message.reply_audio(
                    audio=open(file_path, 'rb'),
                    caption=f"🎵 {video_info['title']}\n👤 {video_info.get('uploader', 'Unknown')}"
                )
                file_id = message.audio.file_id
            
            # Save to cache
            cache_data = {
                'file_id': file_id,
                'title': video_info['title'],
                'uploader': video_info.get('uploader', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'thumbnail': video_info.get('thumbnail', '')
            }
            
            self.db_manager.save_file_data(url, media_type, quality, cache_data)
            
            await progress_message.delete()
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            await progress_message.edit_text("❌ Failed to upload file.")
        
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
            if user_id in self.user_states:
                del self.user_states[user_id]
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (YouTube URLs)"""
        text = update.message.text
        user_id = update.message.from_user.id
        
        if self.downloader.is_youtube_url(text):
            # Store URL and ask for media type
            self.user_states[user_id] = {'url': text}
            
            keyboard = [
                [
                    InlineKeyboardButton("🎥 Video", callback_data='video'),
                    InlineKeyboardButton("🎵 Audio", callback_data='audio')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "What would you like to download?",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "❌ Please send a valid YouTube URL.\n\n"
                "Example: https://www.youtube.com/watch?v=VIDEO_ID"
            )

def main():
    """Main function to run the bot"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN environment variable is not set!")
        return
    
    # Create bot handlers instance
    handlers = BotHandlers()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CallbackQueryHandler(handlers.button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    
    # Start the bot with polling
    logger.info("Starting bot...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
