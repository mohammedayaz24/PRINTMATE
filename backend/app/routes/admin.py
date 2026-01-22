from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.database import engine
from app.dependencies.admin_auth import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


# -------------------- ORDERS --------------------

@router.get("/orders")
def get_orders(auth=Depends(require_admin)):
    """
    SUPER_ADMIN → all orders
    ADMIN → only their shop orders
    """

    if auth["role"] == "SUPER_ADMIN":
        query = text("""
            SELECT *
            FROM orders
            ORDER BY created_at DESC
        """)
        params = {}

    else:  # ADMIN
        query = text("""
            SELECT *
            FROM orders
            WHERE shop_id = :shop_id
            ORDER BY created_at DESC
        """)
        params = {"shop_id": auth["shop_id"]}

    with engine.connect() as connection:
        result = connection.execute(query, params)
        return [dict(row._mapping) for row in result]


@router.get("/orders/status/{status}")
def orders_by_status(status: str, auth=Depends(require_admin)):
    status = status.upper()

    if status not in ["PENDING", "IN_PROGRESS", "COMPLETED", "DELIVERED"]:
        raise HTTPException(400, "Invalid status")

    if auth["role"] == "SUPER_ADMIN":
        query = text("""
            SELECT *
            FROM orders
            WHERE status = :status
            ORDER BY created_at DESC
        """)
        params = {"status": status}

    else:
        query = text("""
            SELECT *
            FROM orders
            WHERE status = :status AND shop_id = :shop_id
            ORDER BY created_at DESC
        """)
        params = {
            "status": status,
            "shop_id": auth["shop_id"]
        }

    with engine.connect() as connection:
        result = connection.execute(query, params)
        return [dict(row._mapping) for row in result]


# -------------------- ANALYTICS (DAILY / WEEKLY / MONTHLY) --------------------

def analytics_query(group_by: str):
    return f"""
        SELECT
            {group_by} AS period,
            COUNT(*) AS total_orders,
            SUM(estimated_cost) AS total_revenue
        FROM orders
        WHERE status IN ('COMPLETED', 'DELIVERED')
        {{shop_filter}}
        GROUP BY period
        ORDER BY period DESC
    """


@router.get("/analytics/{range}")
def analytics(range: str, auth=Depends(require_admin)):
    range = range.lower()

    if range == "daily":
        group_by = "DATE(created_at)"
    elif range == "weekly":
        group_by = "DATE_TRUNC('week', created_at)"
    elif range == "monthly":
        group_by = "DATE_TRUNC('month', created_at)"
    else:
        raise HTTPException(400, "Range must be daily, weekly, or monthly")

    if auth["role"] == "SUPER_ADMIN":
        query = text(
            analytics_query(group_by).replace("{shop_filter}", "")
        )
        params = {}

    else:
        query = text(
            analytics_query(group_by).replace(
                "{shop_filter}", "AND shop_id = :shop_id"
            )
        )
        params = {"shop_id": auth["shop_id"]}

    with engine.connect() as connection:
        result = connection.execute(query, params)
        return {
            "range": range,
            "shop_id": auth["shop_id"],
            "data": [dict(row._mapping) for row in result]
        }
