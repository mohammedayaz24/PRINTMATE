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

from sqlalchemy import text

@router.get("/{shop_id}/queue")
def get_shop_queue(shop_id: str):
    """
    Returns active print queue for a shop
    (PENDING + IN_PROGRESS orders only)
    """

    query = text("""
        SELECT
            id,
            student_id,
            status,
            total_pages,
            estimated_ready_time,
            created_at
        FROM orders
        WHERE shop_id = :shop_id
          AND status IN ('PENDING', 'IN_PROGRESS')
        ORDER BY created_at ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"shop_id": shop_id})
        rows = result.fetchall()

    queue = []
    for index, row in enumerate(rows, start=1):
        queue.append({
            "queue_position": index,
            "order_id": row.id,
            "student_id": row.student_id,
            "status": row.status,
            "total_pages": row.total_pages,
            "estimated_ready_time": row.estimated_ready_time,
            "created_at": row.created_at
        })

    return {
        "shop_id": shop_id,
        "queue_length": len(queue),
        "queue": queue
    }

from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/shops", tags=["Shops"])


@router.get("/{shop_id}/orders")
def get_shop_orders(shop_id: str):
    query = text("""
        SELECT
            id,
            student_id,
            total_pages,
            estimated_cost,
            status,
            payment_status,
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


@router.get("/{shop_id}/orders/pending")
def get_pending_orders(shop_id: str):
    query = text("""
        SELECT
            id,
            student_id,
            total_pages,
            estimated_cost,
            status,
            payment_status,
            created_at
        FROM orders
        WHERE shop_id = :shop_id
          AND status = 'PENDING'
        ORDER BY created_at ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"shop_id": shop_id})
        orders = [dict(row._mapping) for row in result]

    return orders


@router.get("/{shop_id}/orders/in-progress")
def get_in_progress_orders(shop_id: str):
    query = text("""
        SELECT
            id,
            student_id,
            total_pages,
            estimated_cost,
            status,
            payment_status,
            created_at
        FROM orders
        WHERE shop_id = :shop_id
          AND status = 'IN_PROGRESS'
        ORDER BY created_at ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"shop_id": shop_id})
        orders = [dict(row._mapping) for row in result]

    return orders


@router.get("/{shop_id}/orders/completed")
def get_completed_orders(shop_id: str):
    query = text("""
        SELECT
            id,
            student_id,
            total_pages,
            estimated_cost,
            status,
            payment_status,
            created_at
        FROM orders
        WHERE shop_id = :shop_id
          AND status = 'COMPLETED'
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"shop_id": shop_id})
        orders = [dict(row._mapping) for row in result]

    return orders
