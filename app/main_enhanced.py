from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from functools import wraps
import os
from pathlib import Path

app = FastAPI(title="Used Book Store API")

# CORS Configuration - Only allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Timestamp"],
)

# MongoDB Connection
client = MongoClient("mongodb://localhost:27017/")
db = client["bookstore_db"]
books_collection = db["Book_inventory"]
users_collection = db["users"]

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
security = HTTPBearer()

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Helper Functions
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_admin(current_user: dict = Depends(verify_token)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def create_token(user_id: str, role: str):
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# Rate Limiting (Simple in-memory store - use Redis in production)
request_counts = {}
RATE_LIMIT = 100  # requests per minute

def rate_limit(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # In production, use Redis or a proper rate limiting library
        return await func(*args, **kwargs)
    return wrapper

# Routes
@app.get("/")
def read_root():
    return {"message": "Welcome to the Used Book Store API!"}

# Authentication Routes
@app.post("/auth/register")
async def register(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
):
    # Check if user exists
    if users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate role
    if role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Hash password
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    
    # Create user
    user = {
        "name": name,
        "email": email,
        "password": hashed_password.decode("utf-8"),
        "role": role,
        "created_at": datetime.utcnow(),
    }
    result = users_collection.insert_one(user)
    user_id = str(result.inserted_id)
    
    # Generate token
    token = create_token(user_id, role)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role,
        },
    }

@app.post("/auth/login")
async def login(email: str = Form(...), password: str = Form(...), role: str = Form("user")):
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check role
    if user.get("role") != role:
        raise HTTPException(status_code=403, detail="Invalid role for this account")
    
    user_id = str(user["_id"])
    token = create_token(user_id, user["role"])
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
    }

# Book Routes
@app.get("/books")
async def get_books(
    search: Optional[str] = None,
    category: Optional[str] = None,
    condition: Optional[str] = None,
    priceRange: Optional[str] = None,
    limit: int = 50,
):
    query = {}
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"author": {"$regex": search, "$options": "i"}},
        ]
    
    if category:
        query["category"] = category
    
    if condition:
        query["condition"] = condition
    
    if priceRange:
        if priceRange == "0-20":
            query["price"] = {"$gte": 0, "$lte": 20}
        elif priceRange == "20-50":
            query["price"] = {"$gte": 20, "$lte": 50}
        elif priceRange == "50-100":
            query["price"] = {"$gte": 50, "$lte": 100}
        elif priceRange == "100+":
            query["price"] = {"$gte": 100}
    
    books = list(books_collection.find(query).limit(limit))
    for book in books:
        book["_id"] = str(book["_id"])
        # Map old schema to new schema
        if "title" not in book and "Book Name" in book:
            book["title"] = book.get("Book Name", "Untitled")
        if "author" not in book:
            book["author"] = book.get("Publisher", "Unknown")
        if "price" not in book:
            book["price"] = book.get("Price", 0)
        if "image" not in book and "images" in book:
            book["image"] = book["images"][0] if book["images"] else None
    
    return books

@app.get("/books/{book_id}")
async def get_book(book_id: str):
    try:
        book = books_collection.find_one({"_id": ObjectId(book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        book["_id"] = str(book["_id"])
        # Map old schema
        if "title" not in book:
            book["title"] = book.get("Book Name", "Untitled")
        if "author" not in book:
            book["author"] = book.get("Publisher", "Unknown")
        if "image" not in book and "images" in book:
            book["image"] = book["images"][0] if book["images"] else None
        return book
    except Exception:
        raise HTTPException(status_code=404, detail="Book not found")

@app.post("/books/upload")
async def upload_book(
    title: str = Form(...),
    author: str = Form(...),
    price: float = Form(...),
    category: str = Form(...),
    condition: str = Form(...),
    description: Optional[str] = Form(None),
    isbn: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(verify_token),
):
    # Save image if provided
    image_url = None
    if image:
        file_path = UPLOAD_DIR / f"{datetime.utcnow().timestamp()}_{image.filename}"
        with open(file_path, "wb") as f:
            f.write(await image.read())
        image_url = f"/uploads/{file_path.name}"
    
    book = {
        "title": title,
        "author": author,
        "price": price,
        "category": category,
        "condition": condition,
        "description": description,
        "isbn": isbn,
        "image": image_url,
        "sellerId": current_user["id"],
        "sellerEmail": current_user["email"],
        "sellerName": current_user["name"],
        "status": "active",
        "created_at": datetime.utcnow(),
    }
    
    result = books_collection.insert_one(book)
    book["_id"] = str(result.inserted_id)
    return book

@app.put("/books/{book_id}")
async def update_book(
    book_id: str,
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    category: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(verify_token),
):
    book = books_collection.find_one({"_id": ObjectId(book_id)})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check ownership or admin
    if current_user["role"] != "admin" and str(book.get("sellerId")) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = {}
    if title:
        update_data["title"] = title
    if author:
        update_data["author"] = author
    if price is not None:
        update_data["price"] = price
    if category:
        update_data["category"] = category
    if condition:
        update_data["condition"] = condition
    if description:
        update_data["description"] = description
    if status:
        update_data["status"] = status
    
    if image:
        file_path = UPLOAD_DIR / f"{datetime.utcnow().timestamp()}_{image.filename}"
        with open(file_path, "wb") as f:
            f.write(await image.read())
        update_data["image"] = f"/uploads/{file_path.name}"
    
    books_collection.update_one({"_id": ObjectId(book_id)}, {"$set": update_data})
    updated_book = books_collection.find_one({"_id": ObjectId(book_id)})
    updated_book["_id"] = str(updated_book["_id"])
    return updated_book

@app.delete("/books/{book_id}")
async def delete_book(book_id: str, current_user: dict = Depends(verify_token)):
    book = books_collection.find_one({"_id": ObjectId(book_id)})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Check ownership or admin
    if current_user["role"] != "admin" and str(book.get("sellerId")) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    books_collection.delete_one({"_id": ObjectId(book_id)})
    return {"message": "Book deleted successfully"}

# Serve uploaded files
@app.get("/uploads/{filename}")
async def get_upload(filename: str):
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")
