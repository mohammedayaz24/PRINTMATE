from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.test_db import router as test_db_router
from app.routes.shops import router as shops_router
from app.routes.orders import router as orders_router
from app.routes import admin
from app.routes.student import router as student_router
from app.routes import super_admin
from fastapi.staticfiles import StaticFiles
import os
from app.routes import payment
from fastapi.staticfiles import StaticFiles





app = FastAPI()

# CORS: allow local dev servers + MVP wildcard.
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://localhost:3000"
]

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  # or ["*"] for all origins (not recommended for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOAD_DIR = "app/uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Serve the vanilla frontend UI (first-party) so PDF.js isn't blocked by Tracking Prevention.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_UI_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "frontend", "ui"))
if os.path.isdir(FRONTEND_UI_DIR):
    app.mount("/ui", StaticFiles(directory=FRONTEND_UI_DIR), name="ui")

# Include each router exactly once to avoid duplicate routes/operation_ids.
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

app.include_router(test_db_router)
app.include_router(shops_router)
app.include_router(orders_router)
app.include_router(admin.router)
app.include_router(student_router)
app.include_router(super_admin.router)
app.include_router(payment.router)


@app.get("/")
def root():
    return {"message": "PrintMate Backend Running"}
