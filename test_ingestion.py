import pandas as pd
from pymongo import MongoClient
import datetime

client = MongoClient('mongodb://localhost:27017/')
db = client['bookstore_db']
collection = db['Book_inventory']

def run_full_ingestion(file_path, source_name):
    try:
        print(f"📡 Processing {source_name} Database...")
        df = pd.read_excel(file_path).fillna("N/A")
        
        records = []
        for _, row in df.iterrows():
            # Standardizing Board and Category
            book_title = str(row.get('Book Name', row.get('Book_Name', 'No Title')))
            
            # Simple keyword logic for Board if column is missing
            board = row.get('Board', 'General')
            if board == "N/A":
                if "Sindh" in book_title: board = "Sindh Board"
                elif "Punjab" in book_title: board = "Punjab Board"

            document = {
                "category_type": "coursebook",
                "sub_category_type": row.get('Sub Category', 'General'),
                "publisher": row.get('Publisher', 'Unknown'),
                "board": board,
                "title": book_title,
                "price": row.get('Price', 0),
                "sku": row.get('SKU', 'N/A'),
                "images": [row.get('Image URL', row.get('Image_URL', ''))],
                "attributes": {
                    "school_tags": [str(row.get('School', 'General')).lower().strip().replace(" ", "-")],
                    "class": row.get('Class', 'General'),
                },
                "source": source_name,
                "last_updated": datetime.datetime.now()
            }
            records.append(document)

        if records:
            collection.insert_many(records)
            print(f"🏆 Successfully uploaded {len(records)} books from {source_name}!")

    except Exception as e:
        print(f"❌ Error with {source_name}: {e}")

# --- RUN FOR ALL YOUR FILES ---
# Update these filenames to match yours exactly!
run_full_ingestion("Katib books.xlsx", "katib.pk")
run_full_ingestion("Tariq books.xlsx", "tariqbookstore.com")
run_full_ingestion("Idris books.xlsx", "idrisbookbank.com")