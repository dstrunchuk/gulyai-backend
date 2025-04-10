from fastapi import FastAPI, Request
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)

app = FastAPI()

@app.post("/api/form")
async def receive_form(request: Request):
    data = await request.json()

    user_id = data.get("telegram_id")
    name = data.get("name", "—")
    address = data.get("address", "—")
    age = data.get("age", "—")
    interests = data.get("interests", "—")
    activity = data.get("activity", "—")
    vibe = data.get("vibe", "—")

    text = (
        f"📬 Анкета получена!\n\n"
        f"Имя: {name}\n"
        f"Адрес: {address}\n"
        f"Возраст: {age}\n"
        f"Интересы: {interests}\n"
        f"Цель: {activity}\n"
        f"Настроение: {vibe}"
    )

    if user_id:
        await bot.send_message(chat_id=user_id, text=text)

    return {"ok": True}
