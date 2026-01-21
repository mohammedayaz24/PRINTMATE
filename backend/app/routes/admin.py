from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/analytics")
def admin_analytics():
    query = text("""
        SELECT
            DATE(created_at) AS day,
            COUNT(*) AS total_orders,
            SUM(estimated_cost) AS total_sales
        FROM orders
        WHERE payment_status = 'PAID'
        GROUP BY day
        ORDER BY day DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        daily = [dict(row._mapping) for row in result]

    return {
        "daily": daily
    }


@router.get("/orders")
def get_all_orders():
    query = text("""
        SELECT
            id,
            student_id,
            shop_id,
            total_pages,
            estimated_cost,
            status,
            payment_status,
            created_at
        FROM orders
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        orders = [dict(row._mapping) for row in result]

    return orders

@router.get("/orders/pending")
def pending_orders():
    query = text("""
        SELECT *
        FROM orders
        WHERE status = 'PENDING'
        ORDER BY created_at ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        orders = [dict(row._mapping) for row in result]

    return orders

@router.get("/orders/completed")
def completed_orders():
    query = text("""
        SELECT *
        FROM orders
        WHERE status = 'COMPLETED'
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        orders = [dict(row._mapping) for row in result]

    return orders

@router.get("/admin/delivered")
def delivered_orders():
    query = text("""
        SELECT *
        FROM orders
        WHERE status = 'DELIVERED'
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        orders = [dict(row._mapping) for row in result]

    return orders
