import asyncio
import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

API_TOKEN = '5111196744:AAHk1ecAM9XcI3ShPilY0OUSOqCHfFFreNA'

# Load excuses from JSON file
with open('excuses.json', encoding='utf-8') as f:
    EXCUSES = json.load(f)

# Track sent excuses per user
user_excuses = {}
# Track sent excuses per group
group_excuses = {}

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.chat.type == "private":
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="отмазка")]],
            resize_keyboard=True
        )
        await message.answer("Генерируй отмазки", reply_markup=keyboard)


@dp.message()
async def universal_handler(message: types.Message):
    text = message.text.lower().strip() if message.text else ""

    # === приватный чат и кнопка ===
    if message.chat.type == "private" and text == "отмазка":
        user_id = message.from_user.id
        sent = user_excuses.get(user_id, set())
        available = [e for e in EXCUSES if e not in sent]
        if not available:
            sent = set()
            available = EXCUSES.copy()
        excuse = random.choice(available)
        sent.add(excuse)
        user_excuses[user_id] = sent
        await message.answer(excuse)

    # === группа, слово "оливье" ===
    elif message.chat.type in ["group", "supergroup"] and "оливье" in text:
        group_id = message.chat.id
        sent = group_excuses.get(group_id, set())
        available = [e for e in EXCUSES if e not in sent]
        if not available:
            sent = set()
            available = EXCUSES.copy()
        excuse = random.choice(available)
        sent.add(excuse)
        group_excuses[group_id] = sent
        await message.reply(excuse, reply_markup=ReplyKeyboardRemove())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())