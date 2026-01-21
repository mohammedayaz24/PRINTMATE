from fastapi import FastAPI
from app.routes.test_db import router as test_db_router
from app.routes.shops import router as shops_router
from app.routes.orders import router as orders_router
from app.routes import shops
from app.routes import orders
from app.routes import admin

app = FastAPI()

app.include_router(test_db_router)
app.include_router(shops_router)
app.include_router(orders_router)
app.include_router(shops.router)
app.include_router(orders.router)
app.include_router(admin.router)
