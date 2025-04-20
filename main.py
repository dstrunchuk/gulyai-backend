from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import httpx
import time
import asyncio
from auto_status import auto_reset_status  # твоя логика сброса
from dotenv import load_dotenv
from cloudinary_utils import upload_to_cloudinary
from supabase import create_client, Client
from cloudinary.uploader import destroy
from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException



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

@app.get("/api/profile/{chat_id}")
async def get_profile(chat_id: str):
    try:
        # Приводим к строке, если вдруг chat_id — int
        result = supabase.table("users").select("*").eq("chat_id", str(chat_id)).single().execute()
        if result.data:
            return result.data
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    except Exception as e:
        print("❌ Ошибка при получении анкеты:", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@app.post("/api/form")
async def receive_form(
    name: str = Form(...),
    address: str = Form(...),
    age: str = Form(...),
    interests: str = Form(...),
    activity: str = Form(...),
    vibe: str = Form(...),
    chat_id: str = Form(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    photo: UploadFile = File(None)
):
    try:
        if not chat_id:
            return JSONResponse(status_code=400, content={"ok": False, "error": "chat_id is missing"})

        # 1. Найдём старое фото
        old = supabase.table("users").select("photo_url").eq("chat_id", chat_id).execute()
        old_url = old.data[0]["photo_url"] if old.data else None

        # 2. Удалим старую анкету
        supabase.table("users").delete().eq("chat_id", chat_id).execute()

        # 3. Удалим фото из Cloudinary
        if old_url:
            try:
                public_id = old_url.split("/")[-1].split(".")[0]
                destroy(f"gulyai_profiles/{public_id}")
                print("🧹 Удалено старое фото:", public_id)
            except Exception as e:
                print("⚠️ Не удалось удалить фото:", e)

        # 4. Загрузим новое фото
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
            "photo_url": photo_url,
            "latitude": latitude,
            "longitude": longitude
        }

        supabase.table("users").insert(user_data).execute()

        # 6. Уведомление в Telegram
        msg = (
            f"📬 Анкета получена!\n\n"
            f"Имя: {name}\n"
            f"Адрес: {address}\n"
            f"Возраст: {age}\n"
            f"Интересы: {interests}\n"
            f"Цель: {activity}\n"
            f"Настроение: {vibe}"
        )

        async with httpx.AsyncClient() as client:
            await client.post(TELEGRAM_API, json={"chat_id": chat_id, "text": msg})

        return JSONResponse(content={"ok": True, "photo_url": photo_url})

    except Exception as error:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(error)})

@app.post("/api/update-profile")
async def update_profile(data: dict):
    try:
        chat_id = data.get("chat_id")
        if not chat_id:
            return JSONResponse(status_code=400, content={"ok": False, "error": "chat_id is required"})

        data.pop("chat_id", None)

        # Просто выводим для проверки
        print("Получено обновление:", data)

        supabase.table("users").update(data).eq("chat_id", chat_id).execute()
        return {"ok": True}
    except Exception as error:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(error)})



@app.post("/api/delete-profile")
async def delete_profile(request: Request):
    try:
        body = await request.json()
        chat_id = body.get("chat_id")
        if not chat_id:
            return JSONResponse(status_code=400, content={"error": "chat_id is required"})

        # Получим ссылку на фото
        result = supabase.table("users").select("photo_url").eq("chat_id", chat_id).execute()
        photo_url = result.data[0]["photo_url"] if result.data else None

        # Удалим анкету
        supabase.table("users").delete().eq("chat_id", chat_id).execute()

        # Удалим фото из Cloudinary
        if photo_url:
            try:
                public_id = photo_url.split("/")[-1].split(".")[0]
                destroy(f"gulyai_profiles/{public_id}")
                print("🗑️ Фото удалено из Cloudinary:", public_id)
            except Exception as e:
                print("⚠️ Ошибка удаления фото:", e)

        return {"ok": True}
    except Exception as error:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(error)})
    
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

def delete_old_profiles():
    print("🧹 Проверка анкет старше 30 дней...")

    cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
    result = supabase.table("users").select("chat_id", "photo_url", "created_at").lt("created_at", cutoff_date).execute()
    old_users = result.data

    if not old_users:
        print("✅ Нет старых анкет.")
        return

    for user in old_users:
        chat_id = user.get("chat_id")
        photo_url = user.get("photo_url")

        # Удаление фото
        if photo_url:
            try:
                public_id = photo_url.split("/")[-1].split(".")[0]
                destroy(f"gulyai_profiles/{public_id}")
                print(f"🗑️ Фото удалено: {public_id}")
            except Exception as e:
                print("⚠️ Не удалось удалить фото:", e)

        # Удаление анкеты
        supabase.table("users").delete().eq("chat_id", chat_id).execute()
        print(f"🗑️ Удалена анкета: {chat_id}")

# Запускаем планировщик
scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_profiles, "interval", hours=24)
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()   

@app.post("/api/text")
async def broadcast_message(request: Request):
    secret = request.headers.get("Authorization")

    if secret != f"Bearer {os.getenv('BROADCAST_SECRET')}":
        return JSONResponse(status_code=403, content={"error": "Forbidden"})

    data = await request.json()
    message = data.get("message")

    if not message:
        return JSONResponse(status_code=400, content={"error": "Message is required"})

    users = supabase.table("users").select("chat_id").execute().data
    if not users:
        return {"status": "No users found"}

    success = 0
    async with httpx.AsyncClient() as client:
        for user in users:
            try:
                await client.post(
                    TELEGRAM_API,
                    json={"chat_id": user["chat_id"], "text": message}
                )
                success += 1
            except Exception as e:
                print(f"❌ Не удалось отправить {user['chat_id']}: {e}")

    return {"status": f"✅ Успешно отправлено {success} пользователям"}

@app.get("/api/people")
async def get_people():
    try:
        now = int(time.time() * 1000)  # Текущее время в миллисекундах
        result = supabase.table("users") \
            .select("*") \
            .eq("status", "online") \
            .gt("online_until", now) \
            .execute()

        return result.data
    except Exception as e:
        print("❌ Ошибка при получении людей:", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера")
    
@app.on_event("startup")
async def schedule_status_check():
    async def loop():
        while True:
            await auto_reset_status()
            await asyncio.sleep(600)  # каждые 10 минут
    asyncio.create_task(loop())
