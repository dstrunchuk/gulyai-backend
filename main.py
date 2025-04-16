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

        # 2. Prepare data
        user_data = {
            "name": name,
            "address": address,
            "age": age,
            "interests": interests,
            "activity": activity,
            "vibe": vibe,
            "chat_id": chat_id,
        }
        if photo_url:
            user_data["photo_url"] = photo_url

        # 3. Check if user exists
        existing = supabase.table("users").select("id").eq("chat_id", chat_id).execute()
        if existing.data:
            user_id = existing.data[0]["id"]
            supabase.table("users").update(user_data).eq("id", user_id).execute()
            print("✏️ Анкета обновлена")
        else:
            supabase.table("users").insert(user_data).execute()
            print("✅ Анкета создана")

        # 4. Telegram notify
        msg = (
            f"📬 Анкета получена!\n\n"
            f"Имя: {name}\n"
            f"Адрес: {address}\n"
            f"Возраст: {age}\n"
            f"Интересы: {interests}\n"
            f"Цель: {activity}\n"
            f"Настроение: {vibe}"
        )
        await httpx.post(TELEGRAM_API, json={"chat_id": chat_id, "text": msg})

        return JSONResponse(content={"ok": True, "photo_url": photo_url})

    except Exception as e:
        print(f"❌ Ошибка анкеты: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})