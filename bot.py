import os
import re
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import yt_dlp

# ── Logging: prints activity to console so you can monitor what's happening ──
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Grab the bot token from environment variable (you'll set this on Render) ──
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ── Detect if the message contains an Instagram URL ──
def is_instagram_url(text):
    pattern = r'(https?://)?(www\.)?instagram\.com/\S+'
    return bool(re.search(pattern, text))

# ── /start command: greets the user ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! Send me any Instagram video URL and I'll download it for you.\n\n"
        "Supports: Reels, Posts, Stories (public only)"
    )

# ── Main handler: receives a message, checks for IG URL, downloads & sends ──
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not is_instagram_url(text):
        await update.message.reply_text("⚠️ Please send a valid Instagram URL.")
        return

    await update.message.reply_text("⏳ Downloading... please wait.")
    logger.info(f"Download request: {text}")

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

        # Check file size — Telegram bots have a 50MB limit
        file_size = os.path.getsize(output_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Video is too large (over 50MB). Telegram doesn't allow bigger files via bots.")
            os.remove(output_path)
            return

        with open(output_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="✅ Here's your video!",
                supports_streaming=True
            )
        logger.info("Video sent successfully.")

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        await update.message.reply_text(
            "❌ Couldn't download this video. Possible reasons:\n"
            "• The account is private\n"
            "• The link is expired or broken\n"
            "• Instagram is blocking the request temporarily\n\n"
            "Try again in a few minutes."
        )

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again.")

    finally:
        # Always clean up the temp file whether it worked or not
        if os.path.exists(output_path):
            os.remove(output_path)

# ── Build and start the bot ──
if __name__ == '__main__':
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()
