
from fastapi import APIRouter, HTTPException, Header
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Query
from app.database import engine

router = APIRouter(prefix="/orders", tags=["Orders"])

# =====================================================
# GET ORDER DETAIL (ADMIN & STUDENT)
# =====================================================
@router.get("/detail/{order_id}")
def get_order_detail(order_id: str):
    with engine.connect() as connection:
        order = connection.execute(
            text("""
                SELECT 
                    o.*,
                    u.username AS student_name,
                    u.roll_no AS student_roll_no
                FROM orders o
                LEFT JOIN users u 
                    ON o.student_id = u.id
                WHERE o.id = :id
            """),
            {"id": order_id}
        ).mappings().first()
        print(order)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

    return order



# =====================================================
# ORDER CREATION
# =====================================================
@router.post("/")
def create_order(
    order: dict,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    required_fields = ["shop_id", "total_pages", "estimated_cost"]
    for field in required_fields:
        if field not in order:
            raise HTTPException(400, f"{field} is required")

    with engine.connect() as connection:
        # Validate Student
        student = connection.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": student_id}
        ).fetchone()
        if not student:
            raise HTTPException(400, "Invalid student ID")

        # Validate Shop
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

        # Calculate ETA
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

        # Insert Order
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

    return {"order_id": result.id, **dict(result._mapping)}

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
        print(order)

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
                SELECT id, shop_id, status, final_cost, estimated_cost
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if role == "ADMIN" and shop_id != str(order.shop_id):
            raise HTTPException(403, "Not your shop order")

        if order.status != "PENDING":
            raise HTTPException(400, "Order must be PENDING to finalize cost")

        if order.final_cost is not None:
            raise HTTPException(400, "Final cost already set")

        final_cost_value = order.estimated_cost if order.estimated_cost is not None else 0

        result = connection.execute(
            text("""
                UPDATE orders
                SET final_cost = :cost
                WHERE id = :id
                RETURNING *
            """),
            {"id": order_id, "cost": final_cost_value}
        ).fetchone()

        connection.commit()

    return dict(result._mapping)


## =====================================================
# PAYMENT (ADMIN DIRECT - CASH ONLY)
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

    if role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(403, "Access denied")

    if payment_mode not in ("CASH", "UPI"):
        raise HTTPException(400, "Invalid payment mode")

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT id, shop_id, payment_status, final_cost
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
            raise HTTPException(400, "Order already PAID")

        # 🔥 If UPI selected → DO NOT mark paid
        if payment_mode == "UPI":
            connection.execute(
                text("""
                    UPDATE orders
                    SET payment_mode = 'UPI',
                        payment_verification_status = 'PENDING'
                    WHERE id = :id
                """),
                {"id": order_id}
            )
            connection.commit()
            return {"message": "Waiting for UPI screenshot verification"}

        # ✅ CASH → direct paid
        updated = connection.execute(
            text("""
                UPDATE orders
                SET payment_status = 'PAID',
                    payment_mode = 'CASH',
                    paid_at = NOW()
                WHERE id = :id
                RETURNING *
            """),
            {"id": order_id}
        ).fetchone()

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
                "total": updated.final_cost
            }
        )

        connection.commit()

    return dict(updated._mapping)


#-----------------------------------------
#   UPI QR CODE GENERATION 
#-----------------------------------------

from urllib.parse import urlencode
from app.config import SHOP_UPI_ID, SHOP_NAME
@router.get("/{order_id}/upi-link")
def generate_upi_link(order_id: str):

    with engine.connect() as connection:
        order = connection.execute(
            text("""
                SELECT final_cost
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if order.final_cost is None:
            raise HTTPException(400, "Finalize cost first")

    params = {
        "pa": SHOP_UPI_ID,
        "pn": SHOP_NAME,
        "am": order.final_cost,
        "cu": "INR"
    }

    upi_url = "upi://pay?" + urlencode(params)

    return {
        "upi_link": upi_url,
        "amount": order.final_cost
    }

# =====================================================
# ADMIN VERIFY UPI PAYMENT
# =====================================================
@router.patch("/{order_id}/verify-upi")
def verify_upi_payment(
    order_id: str,
    payload: dict,
    role: str = Header(..., alias="X-ROLE"),
    shop_id: Optional[str] = Header(None, alias="X-SHOP-ID")
):

    role = role.strip().upper()
    decision = payload.get("decision")  # APPROVE or REJECT

    if role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(403, "Access denied")

    if decision not in ("APPROVE", "REJECT"):
        raise HTTPException(400, "Invalid decision")

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT id, shop_id, final_cost,
                       payment_verification_status
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if role == "ADMIN" and shop_id != str(order.shop_id):
            raise HTTPException(403, "Not your shop order")

        if decision == "REJECT":
            connection.execute(
                text("""
                    UPDATE orders
                    SET payment_verification_status = 'REJECTED'
                    WHERE id = :id
                """),
                {"id": order_id}
            )
            connection.commit()
            return {"message": "Payment rejected"}

        # APPROVE
        updated = connection.execute(
            text("""
                UPDATE orders
                SET payment_status = 'PAID',
                    payment_verification_status = 'VERIFIED',
                    paid_at = NOW()
                WHERE id = :id
                RETURNING *
            """),
            {"id": order_id}
        ).fetchone()

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
                "total": updated.final_cost
            }
        )

        connection.commit()

    return dict(updated._mapping)

@router.patch("/{order_id}/verify-payment")
def verify_payment(
    order_id: str,
    payload: dict,
    role: str = Header(..., alias="X-ROLE"),
    shop_id: Optional[str] = Header(None, alias="X-SHOP-ID")
):

    if role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(403, "Access denied")

    status = payload.get("status")  # APPROVED or REJECTED

    if status not in ("APPROVED", "REJECTED"):
        raise HTTPException(400, "Invalid status")

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT id, shop_id, final_cost
                FROM orders
                WHERE id = :id
            """),
            {"id": order_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        connection.execute(
            text("""
                UPDATE orders
                SET payment_verification_status = :status,
                    payment_status = CASE
                        WHEN :status = 'APPROVED' THEN 'PAID'
                        ELSE 'UNPAID'
                    END,
                    paid_at = CASE
                        WHEN :status = 'APPROVED' THEN NOW()
                        ELSE NULL
                    END
                WHERE id = :id
            """),
            {"id": order_id, "status": status}
        )

        connection.commit()

    return {"message": "Verification updated"}
