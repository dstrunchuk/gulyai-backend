import time
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def auto_reset_status():
    try:
        now = int(time.time() * 1000)  # текущее время в миллисекундах

        # Получаем пользователей, чей online_until уже истёк
        response = supabase.table("users").select("*").lte("online_until", now).eq("status", "online").execute()
        users = response.data

        for user in users:
            chat_id = user["chat_id"]

            # Обновляем статус
            supabase.table("users").update({
                "status": "offline",
                "online_until": None,
                "status_duration": None
            }).eq("chat_id", chat_id).execute()

            # Отправляем уведомление в Telegram
            import requests
            TOKEN = os.getenv("TOKEN")
            text = f"⏱ Время действия твоего статуса закончилось. Мы переключили тебя на 'Гуляю один(-а)'"
            requests.get(f"https://api.telegram.org/bot{TOKEN}/sendMessage", params={
                "chat_id": chat_id,
                "text": text
            })

    except Exception as e:
        print("❌ Ошибка автообновления статуса:", e)