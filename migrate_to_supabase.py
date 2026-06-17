import os
import datetime
import mysql.connector
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY or "YOUR_SUPABASE" in SUPABASE_URL:
    print("Error: Please set SUPABASE_URL and SUPABASE_KEY in your .env file.")
    exit(1)

# Connect to Supabase
print(f"Connecting to Supabase at {SUPABASE_URL}...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Connect to local MySQL
print("Connecting to local MySQL database...")
mysql_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Ranga@2005",
    database="grievance_db"
)
mysql_cursor = mysql_conn.cursor(dictionary=True)

def format_dt(dt):
    if dt is None:
        return None
    if isinstance(dt, (datetime.datetime, datetime.date)):
        return dt.isoformat()
    return str(dt)

def migrate_table(table_name, date_fields=None):
    if date_fields is None:
        date_fields = []
    
    print(f"\nMigrating table '{table_name}'...")
    mysql_cursor.execute(f"SELECT * FROM {table_name}")
    rows = mysql_cursor.fetchall()
    print(f"Found {len(rows)} records in local MySQL '{table_name}'.")

    if not rows:
        print(f"No records to migrate for '{table_name}'.")
        return

    # Prepare data for insertion
    insert_data = []
    for row in rows:
        cleaned_row = {}
        for col, val in row.items():
            # Convert datetime objects to ISO strings
            if col in date_fields:
                cleaned_row[col] = format_dt(val)
            # Convert decimal values to floats for JSON compatibility
            elif isinstance(val, dict) or isinstance(val, list):
                cleaned_row[col] = val
            elif hasattr(val, 'to_eng_string') or type(val).__name__ == 'Decimal':
                cleaned_row[col] = float(val) if val is not None else None
            else:
                cleaned_row[col] = val
        insert_data.append(cleaned_row)

    # Insert into Supabase in chunks to avoid size limits
    chunk_size = 100
    for i in range(0, len(insert_data), chunk_size):
        chunk = insert_data[i:i + chunk_size]
        try:
            res = supabase.table(table_name).upsert(chunk).execute()
            print(f"Successfully upserted records {i + 1} to {i + len(chunk)} into '{table_name}'.")
        except Exception as e:
            print(f"Error upserting chunk into '{table_name}': {e}")
            # Try inserting one by one to see where the error is
            for idx, item in enumerate(chunk):
                try:
                    supabase.table(table_name).upsert(item).execute()
                except Exception as ex:
                    print(f"Failed row: {item}")
                    print(f"Row error: {ex}")
            raise e

def migrate_storage():
    print("\nMigrating local files to Supabase Storage...")
    upload_dir = "static/uploads"
    if not os.path.exists(upload_dir):
        print(f"Upload directory '{upload_dir}' does not exist. Skipping file migration.")
        return

    # Check or create 'uploads' bucket
    bucket_name = "uploads"
    try:
        buckets = supabase.storage.list_buckets()
        bucket_exists = any(b.name == bucket_name for b in buckets)
    except Exception as e:
        print(f"Error listing buckets: {e}. Attempting to proceed...")
        bucket_exists = False

    if not bucket_exists:
        try:
            print(f"Creating public Supabase Storage bucket '{bucket_name}'...")
            supabase.storage.create_bucket(bucket_name, options={"public": True})
            print(f"Bucket '{bucket_name}' created successfully.")
        except Exception as e:
            print(f"Warning: Could not create bucket: {e}. Please ensure bucket '{bucket_name}' exists and is public in Supabase dashboard.")

    # Upload files
    files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    print(f"Found {len(files)} files in '{upload_dir}' to upload.")

    success_count = 0
    for file_name in files:
        file_path = os.path.join(upload_dir, file_name)
        try:
            with open(file_path, "rb") as f:
                # Use upsert=True to overwrite if file already exists
                supabase.storage.from_(bucket_name).upload(
                    path=file_name,
                    file=f,
                    file_options={"cache-control": "3600", "x-upsert": "true"}
                )
            success_count += 1
            print(f"[{success_count}/{len(files)}] Uploaded '{file_name}' to Supabase Storage.")
        except Exception as e:
            # Check if error message indicates it already exists, which means it's ok
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                success_count += 1
                print(f"[{success_count}/{len(files)}] File '{file_name}' already exists in Storage. Skipped upload.")
            else:
                print(f"Error uploading '{file_name}': {e}")

    print(f"Finished file migration. Uploaded {success_count} of {len(files)} files.")

if __name__ == "__main__":
    try:
        # Migrate data in order of dependency
        migrate_table("users")
        migrate_table("grievances", date_fields=["created_at", "resolved_at"])
        migrate_table("chat_logs", date_fields=["timestamp"])
        migrate_table("feedback", date_fields=["created_at"])
        migrate_table("complaint_locations", date_fields=["created_at"])
        
        # Migrate files
        migrate_storage()
        
        print("\n🎉 Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
    finally:
        mysql_cursor.close()
        mysql_conn.close()
