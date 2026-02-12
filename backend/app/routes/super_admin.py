from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])

# --------------------------------------
# 1️⃣ GET ALL SHOPS
# --------------------------------------
@router.get("/shops")
def get_all_shops(role: str = Header(..., alias="X-ROLE")):

    if role.strip().upper() != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Access denied")

    with engine.connect() as connection:
        shops = connection.execute(
            text("""
                SELECT id, accepting_orders, avg_print_time_per_page
                FROM shops
                ORDER BY id
            """)
        ).mappings().all()

    return shops


# --------------------------------------
# 2️⃣ TOGGLE SHOP STATUS
# --------------------------------------
@router.patch("/shops/{shop_id}/toggle")
def toggle_shop(shop_id: str, role: str = Header(..., alias="X-ROLE")):

    if role.strip().upper() != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Access denied")

    with engine.connect() as connection:
        shop = connection.execute(
            text("SELECT accepting_orders FROM shops WHERE id = :id"),
            {"id": shop_id}
        ).fetchone()

        if not shop:
            raise HTTPException(404, "Shop not found")

        new_status = not shop.accepting_orders

        updated = connection.execute(
            text("""
                UPDATE shops
                SET accepting_orders = :status
                WHERE id = :id
                RETURNING id, accepting_orders
            """),
            {"id": shop_id, "status": new_status}
        ).fetchone()

        connection.commit()

    return dict(updated._mapping)


# --------------------------------------
# 3️⃣ VIEW ALL ORDERS (SYSTEM-WIDE)
# --------------------------------------
@router.get("/orders")
def get_all_orders(role: str = Header(..., alias="X-ROLE")):

    if role.strip().upper() != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Access denied")

    with engine.connect() as connection:
        orders = connection.execute(
            text("""
                SELECT id, student_id, shop_id, status, payment_status, created_at
                FROM orders
                ORDER BY created_at DESC
            """)
        ).mappings().all()

    return orders


@router.post("/shops")
def create_shop(
    payload: dict,
    role: str = Header(..., alias="X-ROLE")
):
    if role.upper() != "SUPER_ADMIN":
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:
        result = connection.execute(
            text("""
                INSERT INTO shops (
                    id,
                    accepting_orders,
                    avg_print_time_per_page
                )
                VALUES (
                    gen_random_uuid(),
                    true,
                    :avg_time
                )
                RETURNING *
            """),
            {"avg_time": payload.get("avg_print_time_per_page", 5)}
        ).fetchone()

        connection.commit()

    return dict(result._mapping)

@router.delete("/shops/{shop_id}")
def delete_shop(
    shop_id: str,
    role: str = Header(..., alias="X-ROLE")
):
    if role.upper() != "SUPER_ADMIN":
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:
        connection.execute(
            text("DELETE FROM shops WHERE id = :id"),
            {"id": shop_id}
        )
        connection.commit()

    return {"detail": "Shop deleted"}


@router.get("/analytics/shop/{shop_id}")
def shop_analytics(
    shop_id: str,
    role: str = Header(..., alias="X-ROLE")
):
    if role.upper() != "SUPER_ADMIN":
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:
        stats = connection.execute(
            text("""
                SELECT
                    COUNT(*) AS total_orders,
                    COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
                    COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled,
                    SUM(final_cost) AS revenue
                FROM orders
                WHERE shop_id = :id
            """),
            {"id": shop_id}
        ).fetchone()

    return dict(stats._mapping)


@router.get("/analytics/system")
def system_analytics(
    role: str = Header(..., alias="X-ROLE")
):
    if role.upper() != "SUPER_ADMIN":
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:
        stats = connection.execute(
            text("""
                SELECT
                    COUNT(*) AS total_orders,
                    COUNT(*) FILTER (WHERE payment_status = 'PAID') AS paid_orders,
                    SUM(final_cost) AS total_revenue
                FROM orders
            """)
        ).fetchone()

    return dict(stats._mapping)


@router.get("/admins")
def get_admins(role: str = Header(..., alias="X-ROLE")):
    if role.upper() != "SUPER_ADMIN":
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:
        admins = connection.execute(
            text("""
                SELECT id, role
                FROM users
                WHERE role IN ('ADMIN', 'SUPER_ADMIN')
            """)
        ).mappings().all()

    return admins


@router.patch("/admins/{admin_id}/suspend")
def suspend_admin(
    admin_id: str,
    role: str = Header(..., alias="X-ROLE")
):
    if role.upper() != "SUPER_ADMIN":
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:
        connection.execute(
            text("""
                UPDATE users
                SET role = 'SUSPENDED'
                WHERE id = :id
            """),
            {"id": admin_id}
        )
        connection.commit()

    return {"detail": "Admin suspended"}
