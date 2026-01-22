from fastapi import Header, HTTPException
from typing import Optional

def require_admin(
    role: str = Header(..., alias="X-ROLE"),
    shop_id: Optional[str] = Header(None, alias="X-SHOP-ID"),
):
    if role == "SUPER_ADMIN":
        return {"role": role, "shop_id": None}

    if role == "ADMIN":
        if not shop_id:
            raise HTTPException(
                status_code=400,
                detail="X-SHOP-ID required for admin"
            )
        return {"role": role, "shop_id": shop_id}

    raise HTTPException(status_code=403, detail="Access denied")
