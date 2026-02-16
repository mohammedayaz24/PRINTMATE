from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.database import engine
from app.dependencies.admin_auth import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


# =====================================================
# GET ALL ORDERS
# =====================================================

@router.get("/orders")
def get_orders(auth=Depends(require_admin)):

    base_query = """
        SELECT
            o.*,

            -- Student Info
            u.username AS full_name,
            u.roll_no AS roll_no,

            -- Print Options
            po.page_ranges,
            po.color_mode,
            po.side_mode,
            po.orientation,
            po.binding,
            po.copies,

            -- Latest Document
            doc.original_filename AS document_name,
            doc.file_url AS document_url

        FROM orders o

        LEFT JOIN users u
            ON u.id = o.student_id

        LEFT JOIN print_options po
            ON po.order_id = o.id

        LEFT JOIN LATERAL (
            SELECT od.original_filename, od.file_url
            FROM order_documents od
            WHERE od.order_id = o.id
            ORDER BY od.uploaded_at DESC
            LIMIT 1
        ) doc ON TRUE
    """

    if auth["role"] == "SUPER_ADMIN":
        query = text(base_query + " ORDER BY o.created_at DESC")
        params = {}
    else:
        query = text(base_query + """
            WHERE o.shop_id = :shop_id
            ORDER BY o.created_at DESC
        """)
        params = {"shop_id": auth["shop_id"]}

    with engine.connect() as connection:
        result = connection.execute(query, params)
        return [dict(row._mapping) for row in result]


# =====================================================
# FILTER BY STATUS
# =====================================================

@router.get("/orders/status/{status}")
def orders_by_status(status: str, auth=Depends(require_admin)):

    status = status.upper()

    if status not in ["PENDING", "IN_PROGRESS", "COMPLETED", "DELIVERED", "CANCELLED"]:
        raise HTTPException(400, "Invalid status")

    base_query = """
        SELECT
            o.*,

            u.username AS full_name,
            u.roll_no AS roll_no,

            po.page_ranges,
            po.color_mode,
            po.side_mode,
            po.orientation,
            po.binding,
            po.copies,

            doc.original_filename AS document_name,
            doc.file_url AS document_url

        FROM orders o

        LEFT JOIN users u
            ON u.id = o.student_id

        LEFT JOIN print_options po
            ON po.order_id = o.id

        LEFT JOIN LATERAL (
            SELECT od.original_filename, od.file_url
            FROM order_documents od
            WHERE od.order_id = o.id
            ORDER BY od.uploaded_at DESC
            LIMIT 1
        ) doc ON TRUE

        WHERE o.status = :status
    """

    if auth["role"] == "SUPER_ADMIN":
        query = text(base_query + " ORDER BY o.created_at DESC")
        params = {"status": status}
    else:
        query = text(base_query + """
            AND o.shop_id = :shop_id
            ORDER BY o.created_at DESC
        """)
        params = {"status": status, "shop_id": auth["shop_id"]}

    with engine.connect() as connection:
        result = connection.execute(query, params)
        return [dict(row._mapping) for row in result]


# =====================================================
# ANALYTICS
# =====================================================

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
                "{shop_filter}",
                "AND shop_id = :shop_id"
            )
        )
        params = {"shop_id": auth["shop_id"]}

    with engine.connect() as connection:
        result = connection.execute(query, params)

        return {
            "range": range,
            "shop_id": auth.get("shop_id"),
            "data": [dict(row._mapping) for row in result]
        }

@router.get("/orders/{order_id}")
def get_single_order(order_id: str, auth=Depends(require_admin)):

    base_query = """
        SELECT
            o.*,
            u.username AS student_name,
            u.roll_no AS student_roll_no,
            po.page_ranges,
            po.color_mode,
            po.side_mode,
            po.orientation,
            po.binding,
            po.copies,
            doc.original_filename AS document_name,
            doc.file_url AS document_url
        FROM orders o
        LEFT JOIN users u ON u.id = o.student_id
        LEFT JOIN print_options po ON po.order_id = o.id
        LEFT JOIN LATERAL (
            SELECT od.original_filename, od.file_url
            FROM order_documents od
            WHERE od.order_id = o.id
            ORDER BY od.uploaded_at DESC
            LIMIT 1
        ) doc ON TRUE
        WHERE o.id = :order_id
    """

    if auth["role"] != "SUPER_ADMIN":
        base_query += " AND o.shop_id = :shop_id"

    query = text(base_query)

    params = {"order_id": order_id}
    if auth["role"] != "SUPER_ADMIN":
        params["shop_id"] = auth["shop_id"]

    with engine.connect() as connection:
        result = connection.execute(query, params).fetchone()

        if not result:
            raise HTTPException(404, "Order not found")

        return dict(result._mapping)
