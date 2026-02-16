from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/shops", tags=["Shops"])


# -------------------------
# List Shops
# -------------------------

@router.get("/")
def list_shops():
    query = text("""
        SELECT
            id,
            shop_name,
            address,
            phone,
            accepting_orders,
            avg_print_time_per_page
        FROM shops
        ORDER BY shop_name ASC
    """)

    with engine.connect() as connection:
        rows = connection.execute(query).mappings().all()

    return rows



# -------------------------
# Get Single Shop Details
# -------------------------

@router.get("/{shop_id}")
def get_shop(shop_id: str):
    query = text("""
        SELECT
            id,
            shop_name,
            address,
            phone,
            accepting_orders,
            avg_print_time_per_page
        FROM shops
        WHERE id = :shop_id
    """)

    with engine.connect() as connection:
        shop = connection.execute(query, {"shop_id": shop_id}).mappings().first()

    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    return shop


# -------------------------
# Toggle Shop
# -------------------------

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


# -------------------------
# Shop Orders
# -------------------------

@router.get("/{shop_id}/orders")
def get_shop_orders(shop_id: str):
    query = text("""
        SELECT
            o.id,
            o.total_pages,
            o.estimated_cost,
            o.status,
            o.payment_status,
            o.created_at,
            u.full_name,
            u.roll_no
        FROM orders o
        JOIN users u ON o.student_id = u.id
        WHERE o.shop_id = :shop_id
        ORDER BY o.created_at ASC
    """)

    with engine.connect() as connection:
        orders = connection.execute(query, {"shop_id": shop_id}).mappings().all()

    return orders


# -------------------------
# Queue
# -------------------------

@router.get("/{shop_id}/queue")
def get_shop_queue(shop_id: str):
    query = text("""
        SELECT
            o.id,
            o.total_pages,
            o.status,
            o.estimated_ready_time,
            o.created_at,
            u.full_name,
            u.roll_no
        FROM orders o
        JOIN users u ON o.student_id = u.id
        WHERE o.shop_id = :shop_id
          AND o.status IN ('PENDING', 'IN_PROGRESS')
        ORDER BY o.created_at ASC
    """)

    with engine.connect() as connection:
        rows = connection.execute(query, {"shop_id": shop_id}).mappings().all()

    queue = []
    for index, row in enumerate(rows, start=1):
        queue.append({
            "queue_position": index,
            "order_id": row["id"],
            "student_name": row["full_name"],
            "roll_no": row["roll_no"],
            "status": row["status"],
            "total_pages": row["total_pages"],
            "estimated_ready_time": row["estimated_ready_time"],
            "created_at": row["created_at"]
        })

    return {
        "shop_id": shop_id,
        "queue_length": len(queue),
        "queue": queue
    }

@router.get("/{shop_id}")
def get_shop(shop_id: str):
    query = text("""
        SELECT
            id,
            shop_name,
            address,
            phone,
            accepting_orders,
            avg_print_time_per_page
        FROM shops
        WHERE id = :shop_id
    """)

    with engine.connect() as connection:
        shop = connection.execute(
            query,
            {"shop_id": shop_id}
        ).mappings().first()

    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    return shop
