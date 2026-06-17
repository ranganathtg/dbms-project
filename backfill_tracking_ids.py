import os
import random
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials not set in .env.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def backfill():
    print("Fetching grievances without tracking IDs...")
    res = supabase.table('grievances').select('id').is_('tracking_id', 'null').execute()
    rows = res.data
    
    if not rows:
        print("All grievances already have tracking IDs.")
        return
        
    print(f"Found {len(rows)} grievances to update.")
    for row in rows:
        gid = row['id']
        while True:
            tid = f"GT-{random.randint(100000, 999999)}"
            chk = supabase.table('grievances').select('id').eq('tracking_id', tid).execute()
            if not chk.data:
                tracking_id = tid
                break
        
        print(f"Updating Grievance #{gid} with Tracking ID: {tracking_id}")
        supabase.table('grievances').update({'tracking_id': tracking_id}).eq('id', gid).execute()

    print("Backfill complete!")

if __name__ == "__main__":
    backfill()
