import time
import httpx
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def auto_reset_status():
    try:
        now = int(time.time() * 1000)
        users = supabase.table("users").select("*").execute().data

        updated = 0
        async with httpx.AsyncClient() as client:
            for user in users:
                if user.get("status") == "online" and user.get("online_until") and user["online_until"] < now:
                    # Сбрасываем статус
                    supabase.table("users").update({
                        "status": "offline",
                        "online_until": None,
                        "status_duration": None
                    }).eq("chat_id", user["chat_id"]).execute()

                    # Отправляем уведомление
                    try:
                        await client.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": user["chat_id"],
                                "text": "⏰ Твой статус 'гуляю' автоматически сброшен. Теперь ты offline."
                            }
                        )
                        print(f"✅ Отправлено уведомление об offline для {user['chat_id']}")
                    except Exception as e:
                        print(f"❌ Ошибка отправки уведомления {user['chat_id']}: {e}")

                    updated += 1

        print(f"✅ Авто-сброс статуса: {updated} пользователей обновлено.")
        return {"ok": True, "updated": updated}
    except Exception as e:
        print(f"❌ Ошибка авто-сброса: {e}")
        return {"ok": False, "error": str(e)}