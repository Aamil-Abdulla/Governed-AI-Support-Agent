import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)

# Read one row from mock_orders to confirm connection + read access
response = supabase.table("mock_orders").select("*").limit(1).execute()
print("Connection OK. Sample row:", response.data)