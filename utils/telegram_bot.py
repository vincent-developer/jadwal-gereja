from telegram import Bot
from telegram.error import TelegramError
from config.settings import TELEGRAM_BOT_TOKEN

class TelegramBot:
    """Async Telegram bot helper for python-telegram-bot v20+."""

    def __init__(self, chat_id: str):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id

        if not self.token:
            raise ValueError("BOT_TOKEN not found in environment.")
        if not self.chat_id:
            raise ValueError("chat_id must be provided.")

        self.bot = Bot(token=self.token)

    async def send(self, text: str):
        """Send a text message asynchronously."""
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
            print(f"✅ Sent to Telegram: {text}")
        except TelegramError as e:
            print(f"❌ Failed to send message: {e}")
