import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "printmate-files")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Supabase environment variables not set")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def upload_file(order_id: str, file_bytes: bytes, filename: str):
    path = f"{order_id}/{filename}"

    supabase.storage.from_(SUPABASE_BUCKET).upload(
        path,
        file_bytes,
        {"content-type": "application/pdf", "upsert": "true"}
    )

    public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(path)

    return public_url
