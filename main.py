from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException, APIRouter, Query
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
from timezonefinder import TimezoneFinder
from background_tasks import notify_nearby_users, send_daily_summary
import pytz


router = APIRouter()

tf = TimezoneFinder()

load_dotenv()
app = FastAPI()

app.include_router(router)


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


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.get("/api/profile/{chat_id}")
def get_profile(chat_id: str):
    try:
        result = supabase.table("users").select("*").eq("chat_id", chat_id).execute()

        if not result.data or len(result.data) == 0:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "message": "Анкета ещё не создана"}
            )

        return {"ok": True, "profile": result.data[0]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

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

    try:
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
                    print(f"⚠️ Ошибка при удалении фото {photo_url}: {e}")

            # Уведомление в Telegram
            try:
                httpx.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "⚠️ Ваша анкета была автоматически удалена, так как ей более 30 дней. Заполните её заново, если хотите продолжить использовать приложение!"
                    }
                )
                print(f"✉️ Уведомление отправлено: {chat_id}")
            except Exception as e:
                print(f"⚠️ Ошибка при отправке уведомления: {e}")

            # Удаление анкеты
            try:
                supabase.table("users").delete().eq("chat_id", chat_id).execute()
                print(f"🗑️ Удалена анкета: {chat_id}")
            except Exception as e:
                print(f"⚠️ Ошибка при удалении анкеты {chat_id}: {e}")

    except Exception as e:
        print(f"❌ Ошибка проверки старых анкет: {e}")

# Запускаем планировщик
# scheduler = BackgroundScheduler()
# scheduler.add_job(delete_old_profiles, "interval", hours=24)
# scheduler.start()

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
async def get_people(chat_id: str = Query(...)):
    try:
        now = int(time.time() * 1000)  # текущее время в мс
        result = supabase.table("users") \
            .select("*") \
            .eq("status", "online") \
            .gt("online_until", now) \
            .neq("chat_id", chat_id) \
            .execute()

        return result.data
    except Exception as e:
        print("❌ Ошибка при получении людей:", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера")
    
@app.on_event("startup")
async def startup_tasks():
    async def loop():
        while True:
            await auto_reset_status()
            await notify_nearby_users()
            await send_daily_summary()
            await asyncio.sleep(600)  # каждые 10 мин
    asyncio.create_task(loop())

@router.post("/api/set-offline")
async def set_offline(request: Request):
    data = await request.json()
    chat_id = data.get("chat_id")

    if not chat_id:
        return {"error": "chat_id is required"}

    try:
        supabase.table("users").update({
            "status": "offline",
            "online_until": None,
            "status_duration": None
        }).eq("chat_id", chat_id).execute()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}    

@app.post("/api/send-meet-request")
async def send_meet_request(data: dict):
    try:
        from_chat_id = data["from"]
        to_chat_id = data["to"]
        message = data["message"]

        print(f"📨 Приглашение от {from_chat_id} -> {to_chat_id}")
        print(f"Сообщение: {message}")

        sender = supabase.table("users").select("name").eq("chat_id", from_chat_id).single().execute().data
        sender_name = sender.get("name", "Кто-то")

        async with httpx.AsyncClient() as client:
            # Отправляем получателю
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": to_chat_id,
                    "text": f"📨 {sender_name} хочет встретиться с тобой!\n\nСообщение: {message}",
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": "👀 Посмотреть анкету", "web_app": {"url": f"https://gulyai-webapp.vercel.app/view-profile/{from_chat_id}"}}],
                            [{"text": "✅ Согласен(-на)", "callback_data": f"agree_{from_chat_id}"},
                             {"text": "❌ Не согласен(-на)", "callback_data": f"decline_{from_chat_id}"}]
                        ]
                    }
                }
            )

            # Отправляем подтверждение отправителю
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": from_chat_id,
                    "text": "✅ Приглашение отправлено!",
                }
            )

        print(f"Ответ Telegram на подтверждение: {response.status_code} | {response.text}")
        return {"ok": True}

    except Exception as e:
        print("❌ Ошибка в отправке приглашения:", str(e))
        return {"ok": False, "error": str(e)}
    
@app.get("/api/stats")
def get_stats():
    try:
        count = supabase.table("users").select("chat_id", count='exact').execute().count
        return {"count": count}
    except Exception as e:
        return {"error": str(e)}
    
