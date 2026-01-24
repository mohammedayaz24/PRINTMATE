def calculate_price(
    total_pages: int,
    color_mode: str,
    side_mode: str,
    copies: int,
    binding: str
) -> int:
    """
    Returns total price in INR
    """

    # Base rates (can be moved to DB later)
    RATES = {
        ("BW", "SINGLE"): 1.0,
        ("BW", "DOUBLE"): 0.75,
        ("COLOR", "SINGLE"): 5.0,
        ("COLOR", "DOUBLE"): 4.0,
    }

    BINDING_COST = {
        "NONE": 0,
        "SOFT": 15,
        "SPIRAL": 30
    }

    per_page_cost = RATES[(color_mode, side_mode)]
    pages_cost = total_pages * per_page_cost * copies
    binding_cost = BINDING_COST.get(binding, 0)

    return int(pages_cost + binding_cost)
