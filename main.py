import asyncio
import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os
import sys

API_TOKEN = os.environ.get("BOT_API_TOKEN")
if not API_TOKEN:
    print("Error: BOT_API_TOKEN environment variable not set.")
    sys.exit(1)

USER_EXCUSES_FILE = "user_excuses.json"
GROUP_EXCUSES_FILE = "group_excuses.json"

def load_excuses(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {filename} not found. Creating new.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: {filename} is corrupted. Using empty dict.")
        return {}

def load_excuses_list(filename):
    try:
        with open(filename, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        sys.exit(1)

def save_excuses(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

EXCUSES = load_excuses_list('excuses.json')
user_excuses_lock = asyncio.Lock()
group_excuses_lock = asyncio.Lock()
user_excuses = load_excuses(USER_EXCUSES_FILE)
group_excuses = load_excuses(GROUP_EXCUSES_FILE)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.chat.type == "private":
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="отмазка")]],
            resize_keyboard=True
        )
        try:
            await message.answer("Генерируй отмазки", reply_markup=keyboard)
        except Exception as e:
            print(f"Error sending start message: {e}")

@dp.message()
async def universal_handler(message: types.Message):
    text = message.text.lower().strip() if message.text else ""

    if message.chat.type == "private":
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="отмазка")]],
            resize_keyboard=True
        )
        if text == "отмазка":
            user_id = str(message.from_user.id)
            async with user_excuses_lock:
                sent = set(user_excuses.get(user_id, []))
                available = [e for e in EXCUSES if e not in sent]
                if not available:
                    sent = set()
                    available = EXCUSES.copy()
                excuse = random.choice(available)
                sent.add(excuse)
                user_excuses[user_id] = list(sent)
                save_excuses(USER_EXCUSES_FILE, user_excuses)
            try:
                await message.answer(excuse, reply_markup=keyboard)
            except Exception as e:
                print(f"Error sending excuse: {e}")
        else:
            try:
                await message.answer("Нажми кнопку ниже или напиши 'отмазка'", reply_markup=keyboard)
            except Exception as e:
                print(f"Error sending prompt: {e}")

    elif message.chat.type in ["group", "supergroup"] and "оливье" in text:
        group_id = str(message.chat.id)
        async with group_excuses_lock:
            sent = set(group_excuses.get(group_id, []))
            available = [e for e in EXCUSES if e not in sent]
            if not available:
                sent = set()
                available = EXCUSES.copy()
            excuse = random.choice(available)
            sent.add(excuse)
            group_excuses[group_id] = list(sent)
            save_excuses(GROUP_EXCUSES_FILE, group_excuses)
        try:
            await message.reply(excuse)
        except Exception as e:
            print(f"Error sending group excuse: {e}")

async def main():
    await dp.start_polling(bot, allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post"])

if __name__ == "__main__":
    asyncio.run(main())