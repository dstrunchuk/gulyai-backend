import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

cutoff_date = datetime.utcnow() - timedelta(days=30)

response = supabase.table("users").select("*").lt("created_at", cutoff_date.isoformat()).execute()

for user in response.data:
    print("🧹 Удаляю:", user["name"])
    supabase.table("users").delete().eq("id", user["id"]).execute()