from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.test_db import router as test_db_router
from app.routes.shops import router as shops_router
from app.routes.orders import router as orders_router
from app.routes import admin
from app.routes.student import router as student_router


app = FastAPI()

# CORS: allow local dev servers + MVP wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://127.0.0.1",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include each router exactly once to avoid duplicate routes/operation_ids.
app.include_router(test_db_router)
app.include_router(shops_router)
app.include_router(orders_router)
app.include_router(admin.router)
app.include_router(student_router)
