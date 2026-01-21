from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from datetime import datetime, timedelta
from app.database import engine

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/")
def create_order(order: dict):
    """
    Expected input:
    {
      "student_id": "...",
      "shop_id": "...",
      "total_pages": 20,
      "estimated_cost": 30
    }
    """

    with engine.connect() as connection:

        # 1. Check shop status + avg print time
        shop_query = text("""
            SELECT accepting_orders, avg_print_time_per_page
            FROM shops
            WHERE id = :shop_id
        """)
        shop = connection.execute(shop_query, {"shop_id": order["shop_id"]}).fetchone()

        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")

        if not shop.accepting_orders:
            raise HTTPException(status_code=400, detail="Shop not accepting orders")

        avg_time = shop.avg_print_time_per_page  # seconds per page

        # 2. Count queued pages
        queue_query = text("""
            SELECT COALESCE(SUM(total_pages), 0)
            FROM orders
            WHERE shop_id = :shop_id
              AND status IN ('PENDING', 'IN_PROGRESS')
        """)
        queued_pages = connection.execute(
            queue_query, {"shop_id": order["shop_id"]}
        ).scalar()

        # 3. Calculate ETA
        total_seconds = (queued_pages + order["total_pages"]) * avg_time
        estimated_ready_time = datetime.utcnow() + timedelta(seconds=total_seconds)

        # 4. Insert order
        insert_query = text("""
            INSERT INTO orders (
                student_id,
                shop_id,
                total_pages,
                status,
                payment_status,
                estimated_cost,
                estimated_ready_time
            )
            VALUES (
                :student_id,
                :shop_id,
                :total_pages,
                'PENDING',
                'UNPAID',
                :estimated_cost,
                :estimated_ready_time
            )
            RETURNING id, estimated_ready_time
        """)

        result = connection.execute(insert_query, {
            **order,
            "estimated_ready_time": estimated_ready_time
        })

        row = result.fetchone()
        connection.commit()

    return {
        "order_id": row.id,
        "estimated_ready_time": row.estimated_ready_time
    }


from fastapi import HTTPException
from sqlalchemy import text
from app.database import engine

VALID_TRANSITIONS = {
    "PENDING": ["IN_PROGRESS"],
    "IN_PROGRESS": ["COMPLETED"],
    "COMPLETED": ["DELIVERED"]
}


@router.patch("/{order_id}/status")
def update_order_status(order_id: str, payload: dict):
    new_status = payload.get("status")

    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")

    with engine.connect() as connection:

        current_query = text("""
            SELECT status
            FROM orders
            WHERE id = :order_id
        """)
        current = connection.execute(
            current_query, {"order_id": order_id}
        ).fetchone()

        if not current:
            raise HTTPException(status_code=404, detail="Order not found")

        current_status = current.status

        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition from {current_status} to {new_status}"
            )

        update_query = text("""
            UPDATE orders
            SET status = :new_status
            WHERE id = :order_id
            RETURNING id, status
        """)

        result = connection.execute(update_query, {
            "order_id": order_id,
            "new_status": new_status
        })
        row = result.fetchone()
        connection.commit()

    return {
        "order_id": row.id,
        "status": row.status
    }

@router.get("/{order_id}/track")
def track_order(order_id: str):
    """
    Track a single order with live queue position
    """

    query = text("""
        SELECT
            o.id,
            o.student_id,
            o.shop_id,
            o.status,
            o.total_pages,
            o.estimated_ready_time,
            o.created_at,
            (
                SELECT COUNT(*)
                FROM orders q
                WHERE q.shop_id = o.shop_id
                  AND q.status IN ('PENDING', 'IN_PROGRESS')
                  AND q.created_at <= o.created_at
            ) AS queue_position
        FROM orders o
        WHERE o.id = :order_id
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"order_id": order_id})
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_id": row.id,
        "student_id": row.student_id,
        "shop_id": row.shop_id,
        "status": row.status,
        "queue_position": row.queue_position,
        "total_pages": row.total_pages,
        "estimated_ready_time": row.estimated_ready_time,
        "created_at": row.created_at
    }

@router.patch("/{order_id}/start")
def start_printing(order_id: str):
    query = text("""
        UPDATE orders
        SET status = 'IN_PROGRESS'
        WHERE id = :order_id AND status = 'PENDING'
        RETURNING id, status
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"order_id": order_id})
        row = result.fetchone()
        connection.commit()

    if not row:
        return {"detail": "Order not found or already started"}

    return {
        "order_id": row.id,
        "status": row.status
    }

@router.get("/admin/in-progress")
def get_in_progress_orders():
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
        WHERE status = 'IN_PROGRESS'
        ORDER BY created_at ASC
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        orders = [dict(row._mapping) for row in result]

    return orders

@router.patch("/{order_id}/complete")
def complete_order(order_id: str):
    query = text("""
        UPDATE orders
        SET status = 'COMPLETED'
        WHERE id = :order_id
          AND status = 'IN_PROGRESS'
        RETURNING id, status
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"order_id": order_id})
        row = result.fetchone()
        connection.commit()

    if not row:
        return {"detail": "Order not in progress or not found"}

    return {
        "order_id": row.id,
        "status": row.status
    }

@router.patch("/{order_id}/deliver")
def deliver_order(order_id: str):
    query = text("""
        UPDATE orders
        SET status = 'DELIVERED'
        WHERE id = :order_id
          AND status = 'COMPLETED'
        RETURNING id, status
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"order_id": order_id})
        row = result.fetchone()
        connection.commit()

    if not row:
        return {"detail": "Order not completed or not found"}

    return {
        "order_id": row.id,
        "status": row.status
    }
