from fastapi import FastAPI, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os, httpx
from dotenv import load_dotenv
from cloudinary_utils import upload_to_cloudinary
from supabase import create_client, Client
from cloudinary.uploader import destroy

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

TELEGRAM_TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
def root():
    return {"msg": "🔥 Gulyai backend работает!"}

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
        # 1. Найдём старое фото (если было)
        old = supabase.table("users").select("photo_url").eq("chat_id", chat_id).single().execute()
        old_url = old.data.get("photo_url") if old.data else None

        # 2. Удалим старую анкету
        supabase.table("users").delete().eq("chat_id", chat_id).execute()

        # 3. Удалим старое фото из Cloudinary
        if old_url:
            try:
                public_id = old_url.split("/")[-1].split(".")[0]
                destroy(f"gulyai_profiles/{public_id}")
                print("🧹 Удалено старое фото:", public_id)
            except Exception as e:
                print("⚠️ Не удалось удалить фото:", e)

        # 4. Загрузим новое фото (если есть)
        photo_url = None
        if photo:
            photo_url = await upload_to_cloudinary(photo)

        # 5. Сохраняем анкету
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

        supabase.table("users").insert(user_data).execute()

        # 6. Отправим в Telegram
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
            await httpx.post(TELEGRAM_API, json={"chat_id": chat_id, "text": msg})

        return JSONResponse(content={"ok": True, "photo_url": photo_url})
    except Exception as error:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(error)})

@app.post("/api/update-profile")
async def update_profile(data: dict):
    try:
        chat_id = data.pop("chat_id")
        supabase.table("users").update(data).eq("chat_id", chat_id).execute()
        return {"ok": True}
    except Exception as error:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(error)})

@app.get("/api/profile/{chat_id}")
def get_profile(chat_id: str):
    try:
        result = supabase.table("users").select("*").eq("chat_id", chat_id).single().execute()
        return result.data
    except Exception as error:
        print("❌ Ошибка при получении профиля:", error)
        return JSONResponse(status_code=500, content={"error": str(error)})