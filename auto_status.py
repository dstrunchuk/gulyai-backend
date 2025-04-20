import os
import time
import httpx
from fastapi import APIRouter
from supabase import create_client, Client

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
BOT_TOKEN = os.getenv("TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@router.get("/api/auto-status-check")
async def auto_status_check():
    now = int(time.time() * 1000)
    response = supabase.table("users").select("*").eq("status", "online").execute()
    users = response.data
    updated_users = []

    for user in users:
        if user.get("online_until") and user["online_until"] < now:
            supabase.table("users").update({
                "status": "offline",
                "online_until": None,
                "status_duration": None
            }).eq("chat_id", user["chat_id"]).execute()

            await send_tg_message(
                user["chat_id"],
                "⏱ Время статуса истекло.\nМы переключили тебя в режим «Гуляю один»."
            )
            updated_users.append(user["chat_id"])

    return {"ok": True, "updated": len(updated_users)}

async def send_tg_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)