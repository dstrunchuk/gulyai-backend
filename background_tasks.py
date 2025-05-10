import os
import time
import httpx
from datetime import datetime
from supabase import create_client
from timezonefinder import TimezoneFinder
import pytz

# Настройки
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
tf = TimezoneFinder()

# Расчёт расстояния между двумя координатами
def calculate_distance(lat1, lon1, lat2, lon2):
    from math import radians, cos, sin, sqrt, atan2
    R = 6371e3  # метров

    φ1 = radians(lat1)
    φ2 = radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)

    a = sin(Δφ/2)**2 + cos(φ1)*cos(φ2)*sin(Δλ/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # в метрах

# Основная функция уведомления
async def notify_nearby_users():
    try:
        now_ts = int(time.time() * 1000)
        users = supabase.table("users").select("*").execute().data

        online_users = [u for u in users if u.get("status") == "online" and u.get("online_until", 0) > now_ts]

        for user in users:
            if not user.get("latitude") or not user.get("longitude"):
                continue

            if not user.get("chat_id"):
                continue

            # Получаем часовой пояс по координатам
            tz_name = tf.timezone_at(lat=user["latitude"], lng=user["longitude"]) or "UTC"
            tz = pytz.timezone(tz_name)
            user_time = datetime.now(tz)

            if user_time.hour < 17:
                continue  # только после 17:00 по местному времени

            last_notified = user.get("last_notified")
            if last_notified:
                last_dt = datetime.fromtimestamp(last_notified / 1000, tz)
                if last_dt.date() == user_time.date():
                    continue  # уже уведомлён сегодня

            # Проверяем, есть ли рядом онлайн-пользователи
            nearby_found = False
            for other in online_users:
                if other["chat_id"] == user["chat_id"]:
                    continue
                if not other.get("latitude") or not other.get("longitude"):
                    continue

                dist = calculate_distance(
                    user["latitude"], user["longitude"],
                    other["latitude"], other["longitude"]
                )

                if dist <= 30000:
                    nearby_found = True
                    break

            if nearby_found:
                # Уведомление
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": user["chat_id"],
                                "text": "👋 Рядом с вами появился новый человек онлайн! Загляните в приложение."
                            }
                        )

                    # Обновляем last_notified
                    supabase.table("users").update({
                        "last_notified": int(time.time() * 1000)
                    }).eq("chat_id", user["chat_id"]).execute()

                    print(f"✅ Уведомление отправлено: {user['chat_id']}")

                except Exception as e:
                    print(f"❌ Ошибка при отправке уведомления: {e}")

    except Exception as e:
        print(f"❌ Ошибка в notify_nearby_users: {e}")