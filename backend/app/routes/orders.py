from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/")
def create_order(order: dict):
    """
    Expected input:
    {
      "student_id": "...",
      "shop_id": "...",
      "estimated_cost": 25,
      "estimated_ready_time": "2026-01-22 10:30:00"
    }
    """

    query = text("""
    INSERT INTO orders (
        student_id,
        shop_id,
        status,
        payment_status,
        estimated_cost,
        estimated_ready_time
    )
    VALUES (
        :student_id,
        :shop_id,
        'PENDING',
        'UNPAID',
        :estimated_cost,
        :estimated_ready_time
    )
    RETURNING id, status, payment_status
""")


    with engine.connect() as connection:
        result = connection.execute(query, order)
        row = result.fetchone()
        connection.commit()

    return {
        "order_id": row[0],
        "status": row[1],
        "payment_status": row[2]
    }


@router.get("/student/{student_id}")
def get_student_orders(student_id: str):
    query = text("""
        SELECT
            id,
            status,
            payment_status,
            estimated_cost,
            estimated_ready_time,
            created_at
        FROM orders
        WHERE student_id = :student_id
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"student_id": student_id})
        orders = [dict(row._mapping) for row in result]

    return orders
