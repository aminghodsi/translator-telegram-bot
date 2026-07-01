from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message,ReplyKeyboardMarkup,KeyboardButton,InlineKeyboardButton,InlineKeyboardMarkup
from aiogram.filters import CommandStart
import asyncio
from aiogram.client.session.aiohttp import AiohttpSession
from deep_translator import GoogleTranslator
from pydub import AudioSegment
from faster_whisper import WhisperModel
import uuid
import os
import json
from pathlib import Path
from dotenv import load_dotenv

model = WhisperModel("tiny", device="cpu", compute_type="int8")

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()



language_options = {
    "فارسی":"fa",
    "فرانسوی":"fr",
    "انگلیسی":"en",
    "آلمانی":"de",
}




def get_language_key_board():
    buttons = [[KeyboardButton(text= name) for name in list(language_options.keys())[i:i+2]]
    for i in range(0, len(language_options), 2)]

    return ReplyKeyboardMarkup(keyboard= buttons, resize_keyboard= True)



USER_LANG = Path("user_langs.json")

def load_user_langs():
    if USER_LANG.exists():
        with USER_LANG.open("r",encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_user_langs(data):
    with USER_LANG.open("w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

user_langs = load_user_langs()


@dp.message(CommandStart())
async def start_reply(message: Message):
    user_id = str(message.from_user.id)
    user_langs.pop(user_id, None)
    save_user_langs(user_langs)
    await message.answer("سلام من ربات ترجمه ویس و متن هستم. لطفا زبان مقصد را انتخاب کنید.",
                         reply_markup= get_language_key_board())


@dp.message(F.text.in_(language_options.keys()))
async def handler_language_selection(message: Message):
    user_id = str(message.from_user.id)
    selected_lang = language_options[message.text]
    user_langs[user_id] = selected_lang
    save_user_langs(user_langs)
    await message.answer(
    "متن و یا ویس مورد نظر را ارسال کنید.\nپی نوشت:\nبرای نتیجه نزدیکتر بهتر است ویس واضح و بدون نویز باشد.",
    reply_markup=types.ReplyKeyboardRemove()
)


@dp.callback_query(F.data=="change_target")
async def change_target(callback:types.CallbackQuery):
    user_id = str(callback.from_user.id)
    user_langs.pop(user_id,None)
    save_user_langs(user_langs)
    await callback.message.answer(
    "زبان مقصد را انتخاب کنید",
    reply_markup= get_language_key_board()
    )
    await callback.answer()


@dp.message(F.text)
async def reply_message(message: Message):
    user_id = str(message.from_user.id)
    lang_data = user_langs.get(user_id)

    if not lang_data:
        await message.answer("دوباره امتحان کنید")
        return



    try:
        translate = GoogleTranslator(source= "auto",target= lang_data).translate(message.text)
        await message.reply("ترجمه متن ارسالی:\n%s" %(translate))
    except Exception:
        await message.answer("خطایی رخ داده")


@dp.message(F.voice)
async def voice_translator(message: Message):
    user_id = str(message.from_user.id)
    lang_data = user_langs.get(user_id)

    if not lang_data:
        await message.answer("زبان مقصد را انتخاب نکردید")
        return

    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    file_id = str(uuid.uuid4())
    ogg_path = f"voice_{file_id}.ogg"

    with open(ogg_path, "wb") as f:
        f.write(downloaded_file.getvalue())

    wav_path = f"voice_{file_id}.wav"
    try:
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format="wav")

        segments, info = await asyncio.to_thread(model.transcribe, wav_path)

        txt = "".join([seg.text for seg in segments])

        detected_lang = info.language

        translate = GoogleTranslator(
            source="auto",
            target=lang_data
        ).translate(txt)

        await message.reply(f"زبان تشخیص داده شده: {detected_lang}\nمتن ویس: {txt}")
        await message.reply(f"متن ترجمه: {translate}")
        await message.reply(f"ممنونم که از بات ما استفاده کردید.")
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())