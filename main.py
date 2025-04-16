from fastapi import FastAPI, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os, httpx
from dotenv import load_dotenv
from cloudinary_utils import upload_to_cloudinary
from supabase import create_client, Client

# --- Init ---
load_dotenv()
app = FastAPI()

origins = [
    "https://gulyai-webapp.vercel.app",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Env ---
TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Проверка ---
@app.get("/")
def root():
    return {"msg": "🔥 Gulyai backend работает!"}

# --- Обработка формы ---
@app.post("/api/form")
async def receive_form(
    name: str = Form(...),
    address: str = Form(...),
    age: str = Form(...),
    interests: str = Form(...),
    activity: str = Form(...),
    vibe: str = Form(...),
    chat_id: str = Form(...),
    photo: UploadFile = File(None)
):
    try:
        # 1. Upload photo to Cloudinary
        photo_url = None
        if photo:
            photo_url = await upload_to_cloudinary(photo)

        # 2. Prepare data for Supabase
        user_data = {
            "name": name,
            "address": address,
            "age": age,
            "interests": interests,
            "activity": activity,
            "vibe": vibe,
            "chat_id": chat_id,
            "photo_url": photo_url
        }

        # 3. Remove existing profile with same chat_id
        supabase.table("users").delete().eq("chat_id", chat_id).execute()

        # 4. Save new profile
        response = supabase.table("users").insert(user_data).execute()
        print("✅ Данные сохранены в Supabase")

        # 5. Send message to Telegram
        if chat_id:
            msg = (
                f"📬 Анкета получена!\n\n"
                f"Имя: {name}\n"
                f"Адрес: {address}\n"
                f"Возраст: {age}\n"
                f"Интересы: {interests}\n"
                f"Цель: {activity}\n"
                f"Настроение: {vibe}"
            )
            try:
                await httpx.post(TELEGRAM_API, json={"chat_id": chat_id, "text": msg})
                print(f"📤 Отправлено в Telegram chat_id={chat_id}")
            except Exception as e:
                print(f"❌ Ошибка при отправке в Telegram: {e}")
        else:
            print("⚠️ chat_id отсутствует — Telegram пропущен")

        return JSONResponse(content={"ok": True, "photo_url": photo_url})

    except Exception as error:
        print(f"❌ Ошибка при обработке формы: {error}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(error)})
