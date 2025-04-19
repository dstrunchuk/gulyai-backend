import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client
from cloudinary.uploader import destroy

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

cutoff_date = datetime.utcnow() - timedelta(days=30)

response = supabase.table("users").select("id, name, photo_url").lt("created_at", cutoff_date.isoformat()).execute()

for user in response.data:
    print("🧹 Удаляю:", user["name"])

    # Удаление фото из Cloudinary
    photo_url = user.get("photo_url")
    if photo_url:
        try:
            public_id = photo_url.split("/")[-1].split(".")[0]
            destroy(f"gulyai_profiles/{public_id}")
            print("🗑️ Фото удалено из Cloudinary:", public_id)
        except Exception as e:
            print("⚠️ Ошибка удаления фото:", e)

    # Удаление анкеты
    supabase.table("users").delete().eq("id", user["id"]).execute()