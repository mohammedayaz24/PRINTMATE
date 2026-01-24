from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from sqlalchemy import text
from app.database import engine
from io import BytesIO
from PIL import Image
from app.services.pricing import calculate_price


router = APIRouter(prefix="/student", tags=["Student"])


# ===============================
# 1️⃣ Student Dashboard – All Orders
# ===============================
@router.get("/orders")
def get_student_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            id,
            shop_id,
            total_pages,
            estimated_cost,
            status,
            payment_status,
            estimated_ready_time,
            created_at
        FROM orders
        WHERE student_id = :student_id
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        result = connection.execute(query, {"student_id": student_id})
        orders = [dict(row._mapping) for row in result]

    return {
        "student_id": student_id,
        "orders": orders
    }


# ===============================
# 2️⃣ Single Order Detail (Student)
# ===============================
@router.get("/orders/{order_id}")
def get_student_order_detail(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT *
        FROM orders
        WHERE id = :order_id
          AND student_id = :student_id
    """)

    with engine.connect() as connection:
        order = connection.execute(query, {
            "order_id": order_id,
            "student_id": student_id
        }).fetchone()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return dict(order._mapping)


# ===============================
# 3️⃣ Student Order Tracking (LIVE)
# ===============================
@router.get("/orders/{order_id}/track")
def track_student_order(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            o.id,
            o.shop_id,
            o.status,
            o.total_pages,
            o.payment_status,
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
          AND o.student_id = :student_id
    """)

    with engine.connect() as connection:
        row = connection.execute(query, {
            "order_id": order_id,
            "student_id": student_id
        }).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_id": row.id,
        "shop_id": row.shop_id,
        "status": row.status,
        "payment_status": row.payment_status,
        "queue_position": row.queue_position,
        "total_pages": row.total_pages,
        "estimated_ready_time": row.estimated_ready_time,
        "created_at": row.created_at
    }


from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from sqlalchemy import text
from typing import Optional
from io import BytesIO
from PIL import Image
from app.database import engine

router = APIRouter(prefix="/student", tags=["Student"])


@router.post("/orders/{order_id}/upload")
async def upload_document(
    order_id: str,
    file: UploadFile = File(...),
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    ALLOWED_TYPES = {
        "application/pdf",
        "image/png",
        "image/jpeg",
    }

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type"
        )

    # ---------- READ & CONVERT ----------
    if file.content_type == "application/pdf":
        pdf_bytes = await file.read()

    elif file.content_type in ("image/png", "image/jpeg"):
        image = Image.open(file.file)
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PDF")
        buffer.seek(0)
        pdf_bytes = buffer.read()

    else:
        raise HTTPException(400, "Invalid file")

    with engine.connect() as connection:

        # 1️⃣ Validate order ownership
        order = connection.execute(
            text("""
                SELECT id
                FROM orders
                WHERE id = :order_id
                  AND student_id = :student_id
                  AND status = 'PENDING'
            """),
            {"order_id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(
                status_code=403,
                detail="Order not found, not yours, or already processed"
            )

        # 2️⃣ MOCK storage URL (replace later with S3/R2)
        file_url = f"https://mock-storage/printmate/{order_id}/{file.filename}"

        # 3️⃣ Save document record
        doc = connection.execute(
            text("""
                INSERT INTO order_documents (
                    order_id,
                    file_url,
                    original_filename
                )
                VALUES (
                    :order_id,
                    :file_url,
                    :filename
                )
                RETURNING id
            """),
            {
                "order_id": order_id,
                "file_url": file_url,
                "filename": file.filename
            }
        ).fetchone()

        connection.commit()

    return {
        "order_id": order_id,
        "document_id": doc.id,
        "stored_format": "PDF",
        "size_bytes": len(pdf_bytes),
        "file_url": file_url
    }



@router.post("/orders/{order_id}/print-options")
def set_print_options(
    order_id: str,
    payload: dict,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    """
    Payload example:
    {
      "page_ranges": "1-3,5,8-10",
      "color_mode": "BW",
      "side_mode": "DOUBLE",
      "orientation": "PORTRAIT",
      "binding": "SPIRAL",
      "copies": 2
    }
    """

    with engine.connect() as connection:

        # 1. Validate ownership & status
        order = connection.execute(
            text("""
                SELECT id, status, total_pages
                FROM orders
                WHERE id = :order_id
                  AND student_id = :student_id
            """),
            {"order_id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(403, "Order not found or not yours")
        
        if order.payment_status == "PAID":
            raise HTTPException(
            status_code=400,
            detail="Order already paid. Print options are locked."
        )

        if order.status != "PENDING":
            raise HTTPException(
            status_code=400,
            detail="Print options can only be set while order is PENDING"
    )



        if order.status != "PENDING":
            raise HTTPException(
                400, "Print options can only be set while order is PENDING"
            )

        # 2. Upsert print options
        result = connection.execute(
            text("""
                INSERT INTO print_options (
                    order_id,
                    page_ranges,
                    color_mode,
                    side_mode,
                    orientation,
                    binding,
                    copies
                )
                VALUES (
                    :order_id,
                    :page_ranges,
                    :color_mode,
                    :side_mode,
                    :orientation,
                    :binding,
                    :copies
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
            {
                "order_id": order_id,
                **payload
            }
        ).fetchone()

        # 3. 🔥 STEP 4.3 — RECALCULATE PRICE
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
                WHERE id = :order_id
            """),
            {
                "price": price,
                "order_id": order_id
            }
        )

        connection.commit()

    return {
        "order_id": order_id,
        "print_options": dict(result._mapping),
        "estimated_cost": price
    }


    return dict(result._mapping)

@router.get("/orders/{order_id}/print-options")
def get_print_options(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        options = connection.execute(
            text("""
                SELECT
                    page_ranges,
                    color_mode,
                    side_mode,
                    orientation,
                    binding,
                    copies,
                    updated_at
                FROM print_options
                WHERE order_id = :order_id
            """),
            {"order_id": order_id}
        ).fetchone()

    if not options:
        raise HTTPException(status_code=404, detail="Print options not found")

    return dict(options._mapping)



@router.get("/dashboard")
def student_dashboard(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
            COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') AS in_progress,
            COUNT(*) FILTER (WHERE status IN ('COMPLETED', 'DELIVERED')) AS completed,
            COUNT(*) FILTER (WHERE payment_status = 'PAID') AS paid,
            COUNT(*) FILTER (WHERE payment_status = 'UNPAID') AS unpaid
        FROM orders
        WHERE student_id = :student_id
    """)

    with engine.connect() as connection:
        stats = connection.execute(
            query, {"student_id": student_id}
        ).fetchone()

    return dict(stats._mapping)


@router.get("/orders")
def student_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            o.id,
            o.shop_id,
            s.name AS shop_name,
            o.status,
            o.payment_status,
            o.total_pages,
            o.estimated_cost,
            o.estimated_ready_time,
            o.created_at
        FROM orders o
        JOIN shops s ON s.id = o.shop_id
        WHERE o.student_id = :student_id
        ORDER BY o.created_at DESC
    """)

    with engine.connect() as connection:
        orders = connection.execute(
            query, {"student_id": student_id}
        ).mappings().all()

    return orders


@router.get("/orders/pending")
def student_pending_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT *
        FROM orders
        WHERE student_id = :student_id
          AND status = 'PENDING'
        ORDER BY created_at DESC
    """)

    with engine.connect() as connection:
        orders = connection.execute(
            query, {"student_id": student_id}
        ).mappings().all()

    return orders


@router.get("/orders/in-progress")
def student_in_progress_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            o.id,
            o.shop_id,
            s.name AS shop_name,
            o.status,
            o.payment_status,
            o.total_pages,
            o.estimated_cost,
            o.estimated_ready_time,
            o.created_at
        FROM orders o
        JOIN shops s ON s.id = o.shop_id
        WHERE o.student_id = :student_id
          AND o.status = 'IN_PROGRESS'
        ORDER BY o.created_at ASC
    """)

    with engine.connect() as connection:
        orders = connection.execute(
            query, {"student_id": student_id}
        ).mappings().all()

    return orders



@router.get("/orders/completed")
def student_completed_orders(
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    query = text("""
        SELECT
            o.id,
            o.shop_id,
            s.name AS shop_name,
            o.status,
            o.payment_status,
            o.total_pages,
            o.estimated_cost,
            o.created_at
        FROM orders o
        JOIN shops s ON s.id = o.shop_id
        WHERE o.student_id = :student_id
          AND o.status IN ('COMPLETED', 'DELIVERED')
        ORDER BY o.created_at DESC
    """)

    with engine.connect() as connection:
        orders = connection.execute(
            query, {"student_id": student_id}
        ).mappings().all()

    return orders


@router.post("/orders/{order_id}/print-options")
def save_print_options(
    order_id: str,
    payload: dict,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:

        # 1. Validate order
        order = connection.execute(
            text("""
                SELECT status
                FROM orders
                WHERE id = :order_id
                  AND student_id = :student_id
            """),
            {"order_id": order_id, "student_id": student_id}
        ).fetchone()

        if not order:
            raise HTTPException(403, "Order not found or not yours")

        if order.status != "PENDING":
            raise HTTPException(
                400, "Print options can only be edited while order is PENDING"
            )

        # 2. Upsert print options
        result = connection.execute(
            text("""
                INSERT INTO order_print_options (
                    order_id,
                    color_mode,
                    print_sides,
                    orientation,
                    page_range,
                    binding,
                    copies
                )
                VALUES (
                    :order_id,
                    :color_mode,
                    :print_sides,
                    :orientation,
                    :page_range,
                    :binding,
                    :copies
                )
                ON CONFLICT (order_id)
                DO UPDATE SET
                    color_mode = EXCLUDED.color_mode,
                    print_sides = EXCLUDED.print_sides,
                    orientation = EXCLUDED.orientation,
                    page_range = EXCLUDED.page_range,
                    binding = EXCLUDED.binding,
                    copies = EXCLUDED.copies,
                    updated_at = now()
                RETURNING *
            """),
            {
                "order_id": order_id,
                **payload
            }
        ).fetchone()

        connection.commit()

    return dict(result._mapping)


@router.get("/orders/{order_id}/print-options")
def get_print_options(
    order_id: str,
    student_id: str = Header(..., alias="X-STUDENT-ID")
):
    with engine.connect() as connection:
        options = connection.execute(
            text("""
                SELECT p.*
                FROM order_print_options p
                JOIN orders o ON o.id = p.order_id
                WHERE o.id = :order_id
                  AND o.student_id = :student_id
            """),
            {"order_id": order_id, "student_id": student_id}
        ).fetchone()

    if not options:
        raise HTTPException(404, "Print options not found")

    return dict(options._mapping)
