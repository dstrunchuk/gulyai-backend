from fastapi import APIRouter
import time
from supabase import create_client
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
router = APIRouter()

# Эту функцию будем вызывать в main при старте
async def auto_reset_status():
    try:
        now = int(time.time() * 1000)
        users = supabase.table("users").select("*").execute().data

        updated = 0
        for user in users:
            if user.get("status") == "online" and user.get("online_until") and user["online_until"] < now:
                supabase.table("users").update({
                    "status": "offline",
                    "online_until": None,
                    "status_duration": None
                }).eq("chat_id", user["chat_id"]).execute()

                # Уведомление пользователю
                try:
                    await httpx.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": user["chat_id"],
                            "text": "⏰ Время действия статуса истекло. Статус обновлён на: гуляю один.",
                        }
                    )
                except Exception as e:
                    print(f"Ошибка при отправке уведомления: {e}")

                updated += 1

        print(f"✅ Авто-сброс статуса: {updated} пользователей обновлено.")
        return {"ok": True, "updated": updated}
    except Exception as e:
        print(f"❌ Ошибка авто-сброса: {e}")
        return {"ok": False, "error": str(e)}