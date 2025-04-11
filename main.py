from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os, json
import httpx

app = FastAPI()

# ✅ Разрешённые источники
origins = [
    "https://gulyai-webapp.vercel.app",
    "http://localhost:5173"
]

# ✅ Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_TOKEN = os.getenv("TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
USERS_FILE = "users.json"

@app.get("/")
def read_root():
    return {"msg": "🔥 Gulyai backend работает!"}

@app.post("/api/form")
async def receive_form(req: Request):
    data = await req.json()

    # ✅ Сохраняем в файл
    users = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)

    users.append(data)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    # ✅ Ответ пользователю в Telegram
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
