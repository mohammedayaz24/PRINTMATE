from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from sqlalchemy import text
from typing import Optional
from io import BytesIO
from PIL import Image

from app.database import engine
from app.services.pricing import calculate_price

router = APIRouter(prefix="/student", tags=["Student"])

# =====================================================
# 1️⃣ STUDENT DASHBOARD
# =====================================================
@router.get("/dashboard")
def student_dashboard(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
            COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') AS in_progress,
            COUNT(*) FILTER (WHERE status IN ('COMPLETED','DELIVERED')) AS completed,
            COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled,
            COUNT(*) FILTER (WHERE payment_status = 'PAID') AS paid,
            COUNT(*) FILTER (WHERE payment_status = 'UNPAID') AS unpaid
        FROM orders
        WHERE student_id = :student_id
    """)

    with engine.connect() as connection:
        stats = connection.execute(query, {"student_id": student_id}).fetchone()

    return dict(stats._mapping)


# =====================================================
# 2️⃣ ORDER LISTS (STATIC ROUTES FIRST)
# =====================================================
@router.get("/orders/cancelled")
def student_cancelled_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT *
                FROM orders
                WHERE student_id = :student_id
                  AND status = 'CANCELLED'
                ORDER BY created_at DESC
            """),
            {"student_id": student_id}
        ).mappings().all()

    return rows


@router.get("/orders/pending")
def student_pending_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT *
                FROM orders
                WHERE student_id = :student_id
                  AND status = 'PENDING'
                ORDER BY created_at DESC
            """),
            {"student_id": student_id}
        ).mappings().all()

    return rows


@router.get("/orders/in-progress")
def student_in_progress_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT *
                FROM orders
                WHERE student_id = :student_id
                  AND status = 'IN_PROGRESS'
                ORDER BY created_at ASC
            """),
            {"student_id": student_id}
        ).mappings().all()

    return rows


@router.get("/orders/completed")
def student_completed_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT *
                FROM orders
                WHERE student_id = :student_id
                  AND status IN ('COMPLETED','DELIVERED')
                ORDER BY created_at DESC
            """),
            {"student_id": student_id}
        ).mappings().all()

    return rows


@router.get("/orders")
def student_all_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT *
                FROM orders
                WHERE student_id = :student_id
                ORDER BY created_at DESC
            """),
            {"student_id": student_id}
        ).mappings().all()

    return rows


# =====================================================
# 3️⃣ CANCEL ORDER
# =====================================================
@router.patch("/orders/{order_id}/cancel")
def cancel_order(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT status
                FROM orders
                WHERE id = :id
                  AND student_id = :student_id
            """),
            {"id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        if order.status != "PENDING":
            raise HTTPException(
                400,
                "Order cannot be cancelled after printing starts"
            )

        updated = connection.execute(
            text("""
                UPDATE orders
                SET status = 'CANCELLED'
                WHERE id = :id
                RETURNING id, status
            """),
            {"id": order_id}
        ).fetchone()

        connection.commit()

    return dict(updated._mapping)


# =====================================================
# 4️⃣ UPLOAD DOCUMENT (MOCK STORAGE)
# =====================================================
@router.post("/orders/{order_id}/upload")
async def upload_document(
    order_id: str,
    file: UploadFile = File(...),
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    ALLOWED_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg"
    }

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Unsupported file type")

    # Convert image → PDF
    if file.content_type.startswith("image/"):
        image = Image.open(file.file)
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PDF")
        buffer.seek(0)
        _ = buffer.read()
    else:
        _ = await file.read()

    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT status
                FROM orders
                WHERE id = :id
                  AND student_id = :student_id
            """),
            {"id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(403, "Order not found or not yours")

        if order.status != "PENDING":
            raise HTTPException(400, "Upload allowed only in PENDING state")

        # Mock storage URL (kept per MVP requirement).
        file_url = f"https://mock-storage/printmate/{order_id}/{file.filename}"

        doc = connection.execute(
            text("""
                INSERT INTO order_documents (
                    order_id, file_url, original_filename
                )
                VALUES (:order_id, :url, :name)
                RETURNING id
            """),
            {
                "order_id": order_id,
                "url": file_url,
                "name": file.filename
            }
        ).fetchone()

        connection.commit()

    return {
        "order_id": order_id,
        "document_id": doc.id,
        "file_url": file_url
    }


# =====================================================
# 5️⃣ PRINT OPTIONS (SET + GET)
# =====================================================
@router.post("/orders/{order_id}/print-options")
def set_print_options(
    order_id: str,
    payload: dict,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT status, total_pages, payment_status
                FROM orders
                WHERE id = :id
                  AND student_id = :student_id
            """),
            {"id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(403, "Order not found")

        if order.payment_status == "PAID":
            raise HTTPException(400, "Print options locked after payment")

        if order.status != "PENDING":
            raise HTTPException(400, "Only editable in PENDING state")

        result = connection.execute(
            text("""
                INSERT INTO print_options (
                    order_id, page_ranges, color_mode,
                    side_mode, orientation, binding, copies
                )
                VALUES (
                    :order_id, :page_ranges, :color_mode,
                    :side_mode, :orientation, :binding, :copies
                )
                ON CONFLICT (order_id)
                DO UPDATE SET
                    page_ranges = EXCLUDED.page_ranges,
                    color_mode = EXCLUDED.color_mode,
                    side_mode = EXCLUDED.side_mode,
                    orientation = EXCLUDED.orientation,
                    binding = EXCLUDED.binding,
                    copies = EXCLUDED.copies,
                    updated_at = NOW()
                RETURNING *
            """),
            {"order_id": order_id, **payload}
        ).fetchone()

        price = calculate_price(
            total_pages=order.total_pages,
            color_mode=payload["color_mode"],
            side_mode=payload["side_mode"],
            copies=payload["copies"],
            binding=payload["binding"]
        )

        connection.execute(
            text("""
                UPDATE orders
                SET estimated_cost = :price
                WHERE id = :id
            """),
            {"price": price, "id": order_id}
        )

        connection.commit()

    return {
        "print_options": dict(result._mapping),
        "estimated_cost": price
    }


@router.get("/orders/{order_id}/print-options")
def get_print_options(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        row = connection.execute(
            text("""
                SELECT po.*
                FROM print_options po
                JOIN orders o ON o.id = po.order_id
                WHERE po.order_id = :id
                  AND o.student_id = :student_id
            """),
            {"id": order_id, "student_id": student_id}
        ).fetchone()

    if not row:
        raise HTTPException(404, "Print options not found")

    return dict(row._mapping)


# =====================================================
# 6️⃣ SINGLE ORDER DETAIL (LAST ROUTE)
# =====================================================
@router.get("/orders/{order_id}")
def get_student_order_detail(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:

        order = connection.execute(
            text("""
                SELECT *
                FROM orders
                WHERE id = :id
                  AND student_id = :student_id
            """),
            {"id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(404, "Order not found")

        documents = connection.execute(
            text("""
                SELECT id, original_filename, file_url, uploaded_at
                FROM order_documents
                WHERE order_id = :id
            """),
            {"id": order_id}
        ).mappings().all()

        print_options = connection.execute(
            text("""
                SELECT *
                FROM print_options
                WHERE order_id = :id
            """),
            {"id": order_id}
        ).fetchone()

    return {
        "order": dict(order._mapping),
        "documents": documents,
        "print_options": dict(print_options._mapping) if print_options else None
    }
