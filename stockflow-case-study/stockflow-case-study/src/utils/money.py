from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext

getcontext().prec = 28

def as_money(val) -> Decimal:
    """
    Parse value into Decimal with 2dp, raising ValueError if invalid.
    """
    try:
        d = Decimal(str(val))
        return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid price")
