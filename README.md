# Bookstore Backend Project

## Overview
A FastAPI-based backend that manages 10,000+ book records using MongoDB.

## Features
- **Data Ingestion**: Python scripts to clean and upload Excel data.
- **API**: Built with FastAPI for high-performance data retrieval.
- **Search**: Dynamic filtering by School and Board.

## How to Run
1. Install requirements: `pip install fastapi uvicorn pymongo pandas openpyxl`
2. Start API: `uvicorn app.main:app --reload`
3. View Docs: `http://127.0.0.1:8000/docs`