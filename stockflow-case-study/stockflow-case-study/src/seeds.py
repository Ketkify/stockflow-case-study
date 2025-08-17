from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select
from .db import db
from .models import (
    Company, Warehouse, ProductType, Product, Inventory,
    Supplier, ProductSupplier, ProductThreshold,
    Order, OrderLine
)

def get_or_create(model, defaults=None, **kwargs):
    """
    Robust get_or_create:
      - Uses no_autoflush so selecting doesn't flush half-built objects.
      - Flushes immediately after create so PKs are available for FKs.
    """
    with db.session.no_autoflush:
        row = db.session.execute(
            select(model).filter_by(**kwargs)
        ).scalar_one_or_none()

    if row:
        return row, False

    params = {**kwargs, **(defaults or {})}
    row = model(**params)
    db.session.add(row)
    db.session.flush()  # ensure PKs like company.id are available right away
    return row, True


def seed_core():
    """
    Creates:
    - Company 'Acme Inc' with 2 warehouses
    - ProductType 'Widgets' (default threshold=20) & 'Gadgets' (default=10)
    - Products: WID-001, WID-002, GAD-001
    - Inventory in two warehouses
    - Suppliers and product-supplier mappings
    - Threshold overrides (per-warehouse and product-level)
    - Recent orders/lines to generate ADS for alerts
    """
    # --- Company & Warehouses ---
    acme, _ = get_or_create(Company, name="Acme Inc")
    # acme.id is guaranteed populated due to db.session.flush() in get_or_create

    main_wh, _ = get_or_create(
        Warehouse, company_id=acme.id, name="Main Warehouse", defaults={"location": "NYC"}
    )
    aux_wh, _  = get_or_create(
        Warehouse, company_id=acme.id, name="Aux Warehouse", defaults={"location": "NJ"}
    )

    # --- Product Types ---
    widgets, _ = get_or_create(ProductType, name="Widgets",
                               defaults={"default_low_stock_threshold": 20})
    gadget_type, _ = get_or_create(ProductType, name="Gadgets",
                                   defaults={"default_low_stock_threshold": 10})

    # --- Products ---
    wid1, _ = get_or_create(
        Product, sku="WID-001",
        defaults={"name": "Widget A", "product_type_id": widgets.id, "price": Decimal("12.50")}
    )
    wid2, _ = get_or_create(
        Product, sku="WID-002",
        defaults={"name": "Widget B", "product_type_id": widgets.id, "price": Decimal("9.99")}
    )
    gad1, _ = get_or_create(
        Product, sku="GAD-001",
        defaults={"name": "Gadget X", "product_type_id": gadget_type.id, "price": Decimal("19.90")}
    )

    # --- Inventory ---
    inv_rows = [
        (wid1.id, main_wh.id, Decimal("5")),     # below threshold 18 (override) → alert
        (wid1.id, aux_wh.id,  Decimal("50")),    # plenty
        (wid2.id, main_wh.id, Decimal("25")),    # above threshold → no alert
        (gad1.id, main_wh.id, Decimal("2")),     # likely below threshold 8 (override)
    ]
    for pid, wid, qty in inv_rows:
        inv, created = get_or_create(
            Inventory, product_id=pid, warehouse_id=wid,
            defaults={"quantity": qty}
        )
        if not created:
            inv.quantity = qty  # idempotent "set"

    # --- Suppliers & Product-Supplier links ---
    sup, _  = get_or_create(Supplier, name="Supplier Corp",
                            defaults={"contact_email": "orders@supplier.com"})
    sup2, _ = get_or_create(Supplier, name="Fast Supply",
                            defaults={"contact_email": "hello@fastsupply.com"})

    links = [
        # supplier_id, company_id, product_id, preferred, lead_time_days
        (sup.id,  acme.id, wid1.id, True,  7),
        (sup.id,  acme.id, wid2.id, False, 10),
        (sup2.id, acme.id, wid1.id, False, 5),  # not preferred, but shorter lead time
        (sup2.id, acme.id, gad1.id, True,  4),
    ]
    for sid, cid, pid, preferred, ltd in links:
        get_or_create(
            ProductSupplier,
            supplier_id=sid, company_id=cid, product_id=pid,
            defaults={"preferred": preferred, "lead_time_days": ltd}
        )

    # --- Threshold Overrides ---
    # Per-warehouse override for WID-001 at Main WH
    get_or_create(
        ProductThreshold, company_id=acme.id, product_id=wid1.id, warehouse_id=main_wh.id,
        defaults={"threshold": 18}
    )
    # Product-level override for Gadget X across company
    get_or_create(
        ProductThreshold, company_id=acme.id, product_id=gad1.id, warehouse_id=None,
        defaults={"threshold": 8}
    )

    # --- Recent Orders to produce ADS ---
    now = datetime.utcnow()
    o1 = Order(company_id=acme.id, status="completed", created_at=now - timedelta(days=3))
    o2 = Order(company_id=acme.id, status="shipped",   created_at=now - timedelta(days=8))
    db.session.add_all([o1, o2])
    db.session.flush()

    lines = [
        # WID-001 sold from Main WH (so days_until_stockout can be computed)
        OrderLine(order_id=o1.id, product_id=wid1.id, warehouse_id=main_wh.id, qty=Decimal("10")),
        OrderLine(order_id=o2.id, product_id=wid1.id, warehouse_id=main_wh.id, qty=Decimal("6")),
        # WID-002 sold but stock above threshold → no alert
        OrderLine(order_id=o1.id, product_id=wid2.id, warehouse_id=main_wh.id, qty=Decimal("3")),
        # Gadget X sold; very low stock, threshold override = 8 → alert
        OrderLine(order_id=o2.id, product_id=gad1.id, warehouse_id=main_wh.id, qty=Decimal("2")),
    ]
    db.session.add_all(lines)

    db.session.commit()

    return {
        "company_id": acme.id,
        "main_warehouse_id": main_wh.id,
        "aux_warehouse_id": aux_wh.id,
        "products": {"WID-001": wid1.id, "WID-002": wid2.id, "GAD-001": gad1.id}
    }


def wipe_all():
    """Dev helper to clear all rows (order matters due to FKs)."""
    db.session.query(OrderLine).delete()
    db.session.query(Order).delete()
    db.session.query(ProductSupplier).delete()
    db.session.query(ProductThreshold).delete()
    db.session.query(Inventory).delete()
    db.session.query(Supplier).delete()
    db.session.query(Product).delete()
    db.session.query(ProductType).delete()
    db.session.query(Warehouse).delete()
    db.session.query(Company).delete()
    db.session.commit()
