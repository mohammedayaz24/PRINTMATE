from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/shops", tags=["Shops"])


@router.get("/")
def get_shops():
    query = text("""
        SELECT
            s.id,
            s.name,
            s.is_active,
            s.accepting_orders,
            s.avg_print_time_per_page,
            COALESCE(SUM(o.pages_count), 0) AS total_pages_in_queue
        FROM shops s
        LEFT JOIN orders o
            ON s.id = o.shop_id
            AND o.status = 'pending'
        WHERE s.is_active = true
        GROUP BY s.id
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        shops = []

        for row in result:
            data = dict(row._mapping)
            data["estimated_time_minutes"] = (
                data["total_pages_in_queue"]
                * data["avg_print_time_per_page"]
            )
            shops.append(data)

    return shops
