import os
import time
import httpx
from datetime import datetime
from supabase import create_client
from timezonefinder import TimezoneFinder
from datetime import datetime, timezone
import time
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
        today = datetime.now(timezone.utc).date().isoformat()
        now_ts = int(time.time() * 1000)
        users = supabase.table("users").select("*").execute().data

        online_users = [
            u for u in users
            if u.get("status") == "online"
            and isinstance(u.get("online_until"), int)
            and u["online_until"] > now_ts
        ]

        for user in users:
            if not user.get("latitude") or not user.get("longitude") or not user.get("chat_id"):
                continue

            tz_name = tf.timezone_at(lat=user["latitude"], lng=user["longitude"]) or "UTC"
            tz = pytz.timezone(tz_name)
            user_time = datetime.now(tz)

            weekday = user_time.weekday()  # 6 — воскресенье

            # ✅ СПЕЦИАЛЬНО ДЛЯ ВОСКРЕСЕНЬЯ: диапазон с 10:00 до 20:00
            if weekday == 6:
                if not (10 <= user_time.hour < 20):
                    continue
            else:
                if user_time.hour < 17:
                    continue  # В другие дни — только после 17:00

            if user.get("last_notify_date") == today:
                continue  # Уже было уведомление сегодня

            # Ищем онлайн-людей рядом
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
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": user["chat_id"],
                                "text": "👋 Рядом с вами появился новый человек онлайн! Загляните в приложение."
                            }
                        )

                    supabase.table("users").update({
                        "last_notify_date": today
                    }).eq("chat_id", user["chat_id"]).execute()

                    print(f"✅ Уведомление отправлено: {user['chat_id']}")

                except Exception as e:
                    print(f"❌ Ошибка при отправке уведомления: {e}")

    except Exception as e:
        print(f"❌ Ошибка в notify_nearby_users: {e}")

async def send_daily_summary():
    try:
        now_utc = datetime.utcnow()
        yesterday = now_utc.date().toordinal() - 1

        users = supabase.table("users").select("*").execute().data

        for user in users:
            if not user.get("latitude") or not user.get("longitude") or not user.get("chat_id"):
                continue

            # Определяем часовой пояс пользователя
            tz_name = tf.timezone_at(lat=user["latitude"], lng=user["longitude"]) or "UTC"
            tz = pytz.timezone(tz_name)
            local_time = datetime.now(tz)

            # Отправляем только с 9 до 12 по местному времени
            if not (9 <= local_time.hour < 12):
                continue

            # Проверка: отправляли ли уже сегодня
            last_summary = user.get("last_summary_sent")
            if last_summary:
                try:
                    if isinstance(last_summary, str):
                        # Вдруг старый формат — пропускаем
                        print(f"[!] last_summary_sent в строковом формате, пропускаем: {user['chat_id']}")
                        continue

                    last_dt_utc = datetime.fromtimestamp(last_summary / 1000, tz=pytz.utc)
                    last_dt_local = last_dt_utc.astimezone(tz)

                    if last_dt_local.date() == local_time.date():
                        continue  # Уже отправлено сегодня

                except Exception as e:
                    print(f"[!] Ошибка при разборе last_summary_sent у {user['chat_id']}: {e}")
                    continue

            # Ищем пользователей, кто был онлайн вчера рядом
            found = False
            for other in users:
                if other["chat_id"] == user["chat_id"]:
                    continue
                if not other.get("latitude") or not other.get("longitude"):
                    continue

                last_online_str = other.get("last_online_date")
                if not last_online_str:
                    continue

                try:
                    last_online_date = datetime.strptime(last_online_str, "%Y-%m-%d").date()
                    if last_online_date.toordinal() != yesterday:
                        continue

                    dist = calculate_distance(
                        user["latitude"], user["longitude"],
                        other["latitude"], other["longitude"]
                    )

                    if dist <= 30000:
                        found = True
                        break

                except Exception:
                    continue

            if found:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": user["chat_id"],
                                "text": "📍 Вчера рядом с вами был кто-то онлайн. Не упустите возможность встретиться сегодня!"
                            }
                        )

                    # Сохраняем в UTC как timestamp в миллисекундах
                    supabase.table("users").update({
                        "last_summary_sent": int(datetime.utcnow().timestamp() * 1000)
                    }).eq("chat_id", user["chat_id"]).execute()

                    print(f"📬 Уведомление отправлено: {user['chat_id']}")

                except Exception as e:
                    print(f"❌ Ошибка при отправке уведомления: {e}")

    except Exception as e:
        print(f"❌ Ошибка в send_daily_summary: {e}")