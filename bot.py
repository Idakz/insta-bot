import os
import re
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
    def log_message(self, format, *args):
        pass

def run_web_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

def is_instagram_url(text):
    pattern = r'(https?://)?(www\.)?instagram\.com/\S+'
    return bool(re.search(pattern, text))

def get_user_info(update: Update):
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "no username"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return f"User: {username} (ID: {user.id}) | Name: {name}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = get_user_info(update)
    logger.info(f"New user started bot — {user_info}")
    await update.message.reply_text(
        "👋 Hello! Send me any Instagram video URL and I'll download it for you.\n\n"
        "Supports: Reels, Posts, Stories (public only)"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_info = get_user_info(update)

    if not is_instagram_url(text):
        await update.message.reply_text("⚠️ Please send a valid Instagram URL.")
        return

    await update.message.reply_text("⏳ Downloading... please wait.")
    logger.info(f"Download request — {user_info} | URL: {text}")

    output_path = f"tmp_{update.message.message_id}.mp4"

    ydl_opts = {
        'outtmpl': output_path,
        'format': 'mp4/best',
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([text])

        file_size = os.path.getsize(output_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Video is too large (over 50MB).")
            os.remove(output_path)
            return

        with open(output_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="✅ Here's your video!",
                supports_streaming=True
            )
        logger.info(f"Video sent successfully — {user_info}")

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error for {user_info}: {e}")
        await update.message.reply_text(
            "❌ Couldn't download this video. Possible reasons:\n"
            "• The account is private\n"
            "• The link is expired or broken\n"
            "• Instagram is blocking the request temporarily\n\n"
            "Try again in a few minutes."
        )

    except Exception as e:
        logger.error(f"Unexpected error for {user_info}: {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again.")

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")

    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info(f"Web server started on port {PORT}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
