# MediaGenie_Bot

# YouTube Downloader Telegram Bot

## Overview

This is a Python-based Telegram bot that allows users to download YouTube videos and audio files directly through Telegram chat. The bot provides an intuitive interface with inline keyboards and supports multiple quality options for both video and audio downloads. It features a file-based caching system to improve performance and reduce redundant downloads.

## System Architecture

The application follows a modular architecture with clear separation of concerns:

- **Bot Interface Layer**: Handles Telegram bot interactions and user commands
- **Download Engine**: Manages YouTube content extraction and downloading using yt-dlp
- **Caching Layer**: File-based JSON database for storing download metadata
- **Configuration Management**: Centralized configuration and constants

The system is designed as a single-process application that runs continuously, polling for Telegram updates.

## Key Components

### 1. Bot Handlers (`bot_handlers.py`)
- **Purpose**: Manages all Telegram bot interactions and user workflows
- **Key Features**:
  - Start command with welcome interface
  - Inline keyboard navigation (Help/About buttons)
  - User state management for download processes
  - Integration with download and database managers

### 2. YouTube Downloader (`youtube_downloader.py`)
- **Purpose**: Handles YouTube content extraction and downloading
- **Technology**: Uses yt-dlp library for robust YouTube support
- **Features**:
  - Video information extraction without downloading
  - Multiple quality options for video (240p, 360p, 480p, 1080p)
  - Multiple quality options for audio (low, medium, high, best)
  - Progress callback system for real-time download updates
  - File size validation (50MB Telegram limit)

### 3. Database Manager (`database_manager.py`)
- **Purpose**: Manages file-based caching system
- **Architecture**: JSON files organized by media type and quality
- **Structure**:
  ```
  database/
  ├── video/
  │   ├── 240p.json
  │   ├── 360p.json
  │   ├── 480p.json
  │   └── 1080p.json
  └── audio/
      ├── low.json
      ├── medium.json
      ├── high.json
      └── best.json
  ```
- **Benefits**: Reduces redundant downloads and improves response times

### 4. Configuration (`config.py`)
- **Purpose**: Centralizes all configuration settings
- **Key Settings**:
  - Bot token management
  - Quality mappings for video/audio
  - File size limits
  - Timeout configurations
  - User interface messages

### 5. Main Application (`main.py`)
- **Purpose**: Application entry point and bot lifecycle management
- **Features**:
  - Async/await pattern for non-blocking operations
  - Handler registration and routing
  - Error handling and graceful shutdown

## Data Flow

1. **User Interaction**: User sends YouTube URL to bot
2. **URL Validation**: Bot validates and extracts video information
3. **Quality Selection**: User chooses preferred quality via inline keyboard
4. **Cache Check**: System checks if file already exists in cache
5. **Download Process**: If not cached, downloads content using yt-dlp
6. **File Delivery**: Bot sends file to user via Telegram
7. **Cache Storage**: Download metadata saved for future requests

## External Dependencies

### Core Libraries
- **python-telegram-bot**: Telegram Bot API wrapper for Python
- **yt-dlp**: YouTube video/audio extraction and downloading
- **asyncio**: Asynchronous programming support

### System Requirements
- **Python 3.11+**: Required for modern async features
- **Nix Package Manager**: Used for reproducible environment setup
- **Replit Infrastructure**: Cloud hosting and execution environment

## Deployment Strategy

### Development Environment
- **Platform**: Replit with Nix configuration
- **Package Management**: UV lock file for dependency management
- **Hot Reloading**: Automatic restart on code changes

### Production Considerations
- **Process Management**: Single-process polling bot
- **Error Handling**: Comprehensive logging and graceful error recovery
- **Resource Limits**: 50MB file size limit for Telegram compatibility
- **Timeout Management**: 5-minute download timeout to prevent hanging

### Environment Variables
- `BOT_TOKEN`: Telegram bot token (required)

## Changelog

- June 16, 2025. Initial setup - Created complete single-file YouTube downloader bot
- June 16, 2025. Simplified architecture into main.py - Combined all components into single file per user request
- June 16, 2025. Bot successfully deployed and running with polling method
- June 16, 2025. Fixed audio/video download issues - Installed ffmpeg, updated quality mappings, resolved upload errors
- June 16, 2025. Fixed quality selection bug - Each quality level now downloads different resolution instead of same file

## User Preferences

Preferred communication style: Simple, everyday language.
Code style: Single file approach, simple implementation over complex architecture.
