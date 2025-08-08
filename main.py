import asyncio
import json
import random
import logging
import os
import sys
import tempfile
import shutil
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timezone

MAX_UPDATE_AGE = 60  # секунд

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Config ===
API_TOKEN = os.environ.get("BOT_API_TOKEN")
if not API_TOKEN:
    logger.error("BOT_API_TOKEN environment variable not set.")
    sys.exit(1)

# === Paths ===
EXCUSES_FILE = Path("excuses.json")
USER_EXCUSES_FILE = Path("user_excuses.json")
GROUP_EXCUSES_FILE = Path("group_excuses.json")

# === Reply Keyboard ===
keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="отмазка")]],
    resize_keyboard=True
)

# === Load Excuses ===
def load_excuses_list(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
        sys.exit(1)

def load_excuses(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"{path} not found. Creating new.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"{path} is corrupted. Using empty dict.")
        return {}

def save_excuses(path: Path, data: dict):
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2)
            temp_name = tf.name
        shutil.move(temp_name, path)
    except Exception as e:
        logger.error(f"Error saving {path}: {e}")

# === Initialize Data ===
EXCUSES = load_excuses_list(EXCUSES_FILE)
user_excuses = load_excuses(USER_EXCUSES_FILE)
group_excuses = load_excuses(GROUP_EXCUSES_FILE)

user_excuses_lock = asyncio.Lock()
group_excuses_lock = asyncio.Lock()

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# === Reply Keyboard ===
keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="отмазка")]],
    resize_keyboard=True
)

send_queue = asyncio.Queue()
SEND_DELAY = 0.05  # ~20 сообщений/сек (Telegram максимум ~30)

async def message_sender_worker():
    while True:
        chat_id, text, reply_to_message_id, reply_markup = await send_queue.get()
        try:
            logger.info(f"⏳ Отправка сообщения в чат {chat_id}...")
            await bot.send_message(
                chat_id,
                text,
                reply_to_message_id=reply_to_message_id,
                reply_markup=reply_markup
            )
            logger.info(f"✅ Успешно отправлено в {chat_id}: {text[:50]}...")
        except Exception as e:
            error_text = str(e)
            if "Too Many Requests" in error_text:
                try:
                    error_json = json.loads(error_text.split("Response: ")[-1])
                    retry_after = error_json.get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"🚨 Rate limit! retry_after={retry_after} сек. Ждём...")
                    await asyncio.sleep(retry_after + 1)
                except Exception as parse_error:
                    logger.warning(f"⚠️ Не удалось распарсить retry_after. Ждём 1 сек.")
                    await asyncio.sleep(1)
            else:
                logger.error(f"❌ Ошибка при отправке в {chat_id}: {e}")
        await asyncio.sleep(SEND_DELAY)


# === Handlers ===
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.chat.type == "private":
        try:
            await send_queue.put((message.chat.id, "Генерируй отмазки", None, keyboard))
        except Exception as e:
            logger.error("Error sending /start message", exc_info=True)

@dp.message()
async def universal_handler(message: types.Message):
    text = message.text.lower().strip() if message.text else ""
    # фильтр "старых" апдейтов
    now = datetime.now(timezone.utc)
    age = (now - message.date).total_seconds()
    if age > MAX_UPDATE_AGE:
        logger.info(f"⏩ Пропущено старое сообщение ({int(age)} сек. назад) от {message.from_user.id}")
        return

    text = message.text.lower().strip() if message.text else ""
    # === Private Chat ===
    if message.chat.type == "private":
        user_id = str(message.from_user.id)

        if text == "отмазка":
            async with user_excuses_lock:
                sent = set(user_excuses.get(user_id, []))
                available = [e for e in EXCUSES if e not in sent]

                if not available:
                    sent.clear()
                    available = EXCUSES.copy()

                excuse = random.choice(available)
                sent.add(excuse)
                user_excuses[user_id] = list(sent)
                save_excuses(USER_EXCUSES_FILE, user_excuses)

            try:
                await send_queue.put((message.chat.id, excuse, None, keyboard))
            except Exception as e:
                logger.error("Error sending private excuse", exc_info=True)

        else:
            try:
                await send_queue.put((message.chat.id, "Нажми кнопку ниже или напиши 'отмазка'", None, keyboard))
            except Exception as e:
                logger.error("Error sending prompt message", exc_info=True)

    # === Group Chat: Mention of "оливье" ===
    elif message.chat.type in ["group", "supergroup"] and "оливье" in text:
        group_id = str(message.chat.id)

        async with group_excuses_lock:
            sent = set(group_excuses.get(group_id, []))
            available = [e for e in EXCUSES if e not in sent]

            if not available:
                sent.clear()
                available = EXCUSES.copy()

            excuse = random.choice(available)
            sent.add(excuse)
            group_excuses[group_id] = list(sent)
            save_excuses(GROUP_EXCUSES_FILE, group_excuses)

        logger.info(f"Sent excuse to group {group_id}: {excuse}")

        try:
            await send_queue.put((message.chat.id, excuse, message.message_id, None))
        except Exception as e:
            logger.error(f"Error sending group excuse to group {group_id}", exc_info=True)

# === Entry Point ===
async def main():
    asyncio.create_task(message_sender_worker())  # Запуск очереди

    await dp.start_polling(bot, allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post"])

if __name__ == "__main__":
    asyncio.run(main())
