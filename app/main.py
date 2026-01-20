from fastapi import FastAPI
from pymongo import MongoClient

app = FastAPI()

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["bookstore_db"]
collection = db["Book_inventory"]

@app.get("/")
def read_root():
    return {"message": "Welcome to the Bookstore API!"}

@app.get("/books")
def get_books():
    # We fetch only 10 books so it loads fast
    books = list(collection.find({}, {"_id": 0}).limit(10))
    return books