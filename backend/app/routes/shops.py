from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/shops", tags=["Shops"])


@router.patch("/{shop_id}/toggle")
def toggle_shop_orders(shop_id: str):
    query = text("""
        UPDATE shops
        SET accepting_orders = NOT accepting_orders
        WHERE id = :shop_id
        RETURNING id, accepting_orders
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"shop_id": shop_id})
        row = result.fetchone()
        connection.commit()

    if not row:
        raise HTTPException(status_code=404, detail="Shop not found")

    return {
        "shop_id": row.id,
        "accepting_orders": row.accepting_orders
    }

@router.get("/{shop_id}/orders")
def get_shop_orders(shop_id: str):
    query = text("""
        SELECT
            id,
            student_id,
            status,
            payment_status,
            total_pages,
            estimated_ready_time,
            created_at
        FROM orders
        WHERE shop_id = :shop_id
        ORDER BY created_at ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"shop_id": shop_id})
        orders = [dict(row._mapping) for row in result]

    return orders
