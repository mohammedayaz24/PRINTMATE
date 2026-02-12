from fastapi import APIRouter, UploadFile, File
from sqlalchemy import text
from app.database import engine
import shutil
import uuid

router = APIRouter()

# ===============================
# SET PAYMENT METHOD
# ===============================
@router.patch("/student/payment/set-method/{order_id}")
def set_payment_method(order_id: str, method: str):

    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE orders
            SET payment_method = :method,
                payment_status = 'PENDING'
            WHERE id = :id
        """), {
            "method": method,
            "id": order_id
        })

    return {"message": "Payment method saved"}


# ===============================
# GENERATE UPI LINK
# ===============================
@router.get("/student/payment/upi/{order_id}")
def generate_upi(order_id: str):

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT total_amount FROM orders WHERE id = :id
        """), {"id": order_id})

        amount = result.scalar()

    upi_link = f"upi://pay?pa=printmate@upi&pn=PrintMate&am={amount}&cu=INR&tn=Order{order_id}"

    return {"upi_link": upi_link}


# ===============================
# UPLOAD PAYMENT SCREENSHOT
# ===============================
@router.post("/student/payment/upload/{order_id}")
async def upload_payment_proof(order_id: str, file: UploadFile = File(...)):

    unique_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = f"app/uploads/{unique_name}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE orders
            SET payment_proof = :proof,
                payment_status = 'PAYMENT_PENDING_VERIFICATION'
            WHERE id = :id
        """), {
            "proof": unique_name,
            "id": order_id
        })

    return {"message": "Payment proof uploaded"}


# ===============================
# ADMIN APPROVE
# ===============================
@router.patch("/admin/payment/approve/{order_id}")
def approve_payment(order_id: str):

    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE orders
            SET payment_status = 'PAID'
            WHERE id = :id
        """), {"id": order_id})

    return {"message": "Payment Approved"}


# ===============================
# ADMIN REJECT
# ===============================
@router.patch("/admin/payment/reject/{order_id}")
def reject_payment(order_id: str):

    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE orders
            SET payment_status = 'PAYMENT_FAILED'
            WHERE id = :id
        """), {"id": order_id})

    return {"message": "Payment Rejected"}
