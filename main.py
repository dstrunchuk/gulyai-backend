from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import json, os
import httpx

app = FastAPI()

# 🌐 CORS (разрешаем запросы от фронта)
origins = [
    "https://gulyai-webapp.vercel.app",  # продакшн
    "http://localhost:5173",             # локалка
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📁 Константы
TELEGRAM_TOKEN = os.getenv("TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
USERS_FILE = "users.json"

# 🔥 Проверка
@app.get("/")
def read_root():
    return {"msg": "🔥 Gulyai backend работает!"}

# 📩 Прием анкеты
@app.post("/api/form")
async def receive_form(req: Request):
    data = await req.json()

    # 📸 Проверим base64-фото (если есть)
    if data.get("photo"):
        print("📸 Фото (base64), длина:", len(data["photo"]))

    # 💾 Сохраняем анкету
    users = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    users.append(data)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    # 🤖 Ответ в Telegram
    chat_id = data.get("chat_id")
    if chat_id:
        msg = (
            f"📬 Анкета получена!\n\n"
            f"Имя: {data.get('name', '—')}\n"
            f"Адрес: {data.get('address', '—')}\n"
            f"Возраст: {data.get('age', '—')}\n"
            f"Интересы: {data.get('interests', '—')}\n"
            f"Цель: {data.get('activity', '—')}\n"
            f"Настроение: {data.get('vibe', '—')}"
        )
        await httpx.post(TELEGRAM_API, json={"chat_id": chat_id, "text": msg})

    return {"ok": True}
