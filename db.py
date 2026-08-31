import os
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

SupaBase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)