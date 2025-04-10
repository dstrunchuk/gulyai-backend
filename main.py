from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# 🔐 Токен Telegram бота
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)

# 🚀 FastAPI app
app = FastAPI()

@app.get("/")
def root():
    return {"msg": "🔥 Gulyai backend работает!"}

@app.post("/api/form")
async def receive_form(request: Request):
    data = await request.json()

    name = data.get("name", "—")
    address = data.get("address", "—")
    age = data.get("age", "—")
    interests = data.get("interests", "—")
    activity = data.get("activity", "—")
    vibe = data.get("vibe", "—")
    user_id = data.get("telegram_id")

    msg = (
        f"📬 Анкета получена!\n\n"
        f"Имя: {name}\n"
        f"Адрес: {address}\n"
        f"Возраст: {age}\n"
        f"Интересы: {interests}\n"
        f"Цель: {activity}\n"
        f"Настроение: {vibe}"
    )

    if user_id:
        try:
            await bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": True}
