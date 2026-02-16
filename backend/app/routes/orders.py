from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional
from math import ceil

from app.database import engine

router = APIRouter(prefix="/orders", tags=["Orders"])


# =====================================================
# ORDER CREATION
# =====================================================
@router.post("/")
def create_order(
    order: dict,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):

    # Required fields from frontend
    required_fields = ["shop_id", "total_pages", "estimated_cost"]

    for field in required_fields:
        if field not in order:
            raise HTTPException(400, f"{field} is required")

    with engine.connect() as connection:

        # 1️⃣ Validate Student
        student = connection.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": student_id}
        ).fetchone()

        if not student:
            raise HTTPException(400, "Invalid student ID")

        # 2️⃣ Validate Shop
        shop = connection.execute(
            text("""
                SELECT accepting_orders, avg_print_time_per_page
                FROM shops
                WHERE id = :shop_id
            """),
            {"shop_id": order["shop_id"]}
        ).fetchone()

        if not shop:
            raise HTTPException(404, "Shop not found")

        if not shop.accepting_orders:
            raise HTTPException(400, "Shop not accepting orders")

        # 3️⃣ Calculate ETA
        queued_pages = connection.execute(
            text("""
                SELECT COALESCE(SUM(total_pages), 0)
                FROM orders
                WHERE shop_id = :shop_id
                  AND status IN ('PENDING', 'IN_PROGRESS')
            """),
            {"shop_id": order["shop_id"]}
        ).scalar()

        total_pages = int(order["total_pages"])

        eta = datetime.utcnow() + timedelta(
            seconds=(queued_pages + total_pages) * shop.avg_print_time_per_page
        )

        # 4️⃣ Insert Order
        result = connection.execute(
            text("""
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
                    :eta
                )
                RETURNING *
            """),
            {
                "student_id": student_id,
                "shop_id": order["shop_id"],
                "total_pages": total_pages,
                "estimated_cost": order["estimated_cost"],
                "eta": eta
            }
        ).fetchone()

        connection.commit()

    return dict(result._mapping)


# =====================================================
# STATUS TRANSITIONS
# =====================================================
VALID_TRANSITIONS = {
    "PENDING": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["COMPLETED"],
    "COMPLETED": ["DELIVERED"]
}


@router.patch("/{order_id}/status")
def update_order_status(
    order_id: str,
    payload: dict,
    role: str = Header(..., alias="X-ROLE"),
    shop_id: Optional[str] = Header(None, alias="X-SHOP-ID")
):

    role = role.strip().upper()
    new_status = payload.get("status")

    if not new_status:
        raise HTTPException(400, "Status required")

    if role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT status, shop_id, payment_status
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if role == "ADMIN" and shop_id != str(order.shop_id):
            raise HTTPException(403, "Not your shop order")

        if new_status not in VALID_TRANSITIONS.get(order.status, []):
            raise HTTPException(400, "Invalid status transition")

        if new_status == "DELIVERED" and order.payment_status != "PAID":
            raise HTTPException(400, "Must be PAID before delivery")

        updated = connection.execute(
            text("""
                UPDATE orders
                SET status = :status
                WHERE id = :id
                RETURNING id, status
            """),
            {"id": order_id, "status": new_status}
        ).fetchone()

        connection.commit()

    return dict(updated._mapping)


# =====================================================
# FINALIZE COST
# =====================================================
@router.post("/{order_id}/finalize-cost")
def finalize_cost(
    order_id: str,
    role: str = Header(..., alias="X-ROLE"),
    shop_id: Optional[str] = Header(None, alias="X-SHOP-ID")
):

    role = role.strip().upper()

    if role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT total_pages, shop_id, status, payment_status
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if role == "ADMIN" and shop_id != str(order.shop_id):
            raise HTTPException(403, "Not your shop order")

        if order.payment_status == "PAID":
            raise HTTPException(400, "Already paid")

        if order.status != "PENDING":
            raise HTTPException(400, "Must be PENDING")

        options = connection.execute(
            text("""
                SELECT color_mode, side_mode, binding, copies
                FROM print_options
                WHERE order_id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not options:
            raise HTTPException(400, "Print options missing")

        page_cost = 5 if options.color_mode == "COLOR" else 1
        binding_cost = 20 if options.binding == "SPIRAL" else 0

        effective_pages = (
            ceil(order.total_pages / 2)
            if options.side_mode == "DOUBLE"
            else order.total_pages
        )

        final_cost = effective_pages * page_cost * options.copies + binding_cost

        result = connection.execute(
            text("""
                UPDATE orders
                SET final_cost = :cost
                WHERE id = :id
                RETURNING id, final_cost
            """),
            {"id": order_id, "cost": final_cost}
        ).fetchone()

        connection.commit()

    return dict(result._mapping)


# =====================================================
# PAYMENT
# =====================================================
@router.patch("/{order_id}/pay")
def pay_order(
    order_id: str,
    payload: dict,
    role: str = Header(..., alias="X-ROLE"),
    shop_id: Optional[str] = Header(None, alias="X-SHOP-ID")
):

    role = role.strip().upper()
    payment_mode = payload.get("payment_mode")

    if payment_mode not in ("CASH", "UPI"):
        raise HTTPException(400, "Invalid payment mode")

    if role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(403, "Access denied")

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT shop_id, payment_status, final_cost
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if role == "ADMIN" and shop_id != str(order.shop_id):
            raise HTTPException(403, "Not your shop order")

        if order.final_cost is None:
            raise HTTPException(400, "Finalize cost first")

        if order.payment_status == "PAID":
            return {"detail": "Already paid"}

        connection.execute(
            text("""
                UPDATE orders
                SET payment_status = 'PAID',
                    payment_mode = :mode,
                    paid_at = NOW()
                WHERE id = :id
            """),
            {"id": order_id, "mode": payment_mode}
        )

        connection.execute(
            text("""
                INSERT INTO invoices (
                    order_id,
                    invoice_number,
                    subtotal,
                    tax,
                    total
                )
                VALUES (
                    :order_id,
                    :invoice,
                    :total,
                    0,
                    :total
                )
                ON CONFLICT (order_id) DO NOTHING
            """),
            {
                "order_id": order_id,
                "invoice": f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{order_id[:6]}",
                "total": order.final_cost
            }
        )

        connection.commit()

    return {"order_id": order_id, "status": "PAID"}
