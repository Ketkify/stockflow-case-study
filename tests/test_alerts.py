from datetime import datetime, timedelta
from decimal import Decimal

def _seed_for_alerts(db_session):
    """
    Create:
      - Company + 2 warehouses
      - Product types + products
      - Inventory (low stock in Main WH for WID-001 and GAD-001)
      - Thresholds: per-warehouse (WID-001=18 @Main), product-level (GAD-001=8)
      - Suppliers + product_suppliers (preferred → shortest lead)
      - Orders (completed/shipped) within 30d to generate ADS
    """
    from src.models import (
        Company, Warehouse, ProductType, Product, Inventory,
        ProductThreshold, Supplier, ProductSupplier,
        Order, OrderLine
    )

    now = datetime.utcnow()

    c = Company(name="Acme Inc")
    db_session.add(c); db_session.flush()
    main = Warehouse(company_id=c.id, name="Main Warehouse", location="NYC")
    aux  = Warehouse(company_id=c.id, name="Aux Warehouse", location="NJ")
    db_session.add_all([main, aux]); db_session.flush()

    widgets = ProductType(name="Widgets", default_low_stock_threshold=20)
    gadgets = ProductType(name="Gadgets", default_low_stock_threshold=10)
    db_session.add_all([widgets, gadgets]); db_session.flush()

    wid1 = Product(sku="WID-001", name="Widget A", product_type_id=widgets.id, price=Decimal("12.50"))
    wid2 = Product(sku="WID-002", name="Widget B", product_type_id=widgets.id, price=Decimal("9.99"))
    gad1 = Product(sku="GAD-001", name="Gadget X", product_type_id=gadgets.id, price=Decimal("19.90"))
    db_session.add_all([wid1, wid2, gad1]); db_session.flush()

    db_session.add_all([
        Inventory(product_id=wid1.id, warehouse_id=main.id, quantity=Decimal("5")),
        Inventory(product_id=wid1.id, warehouse_id=aux.id,  quantity=Decimal("50")),
        Inventory(product_id=wid2.id, warehouse_id=main.id, quantity=Decimal("25")),
        Inventory(product_id=gad1.id, warehouse_id=main.id, quantity=Decimal("2")),
    ])

    # thresholds
    db_session.add(ProductThreshold(company_id=c.id, product_id=wid1.id, warehouse_id=main.id, threshold=18))
    db_session.add(ProductThreshold(company_id=c.id, product_id=gad1.id, warehouse_id=None, threshold=8))

    # suppliers
    sup1 = Supplier(name="Supplier Corp", contact_email="orders@supplier.com")
    sup2 = Supplier(name="Fast Supply", contact_email="hello@fastsupply.com")
    db_session.add_all([sup1, sup2]); db_session.flush()

    db_session.add_all([
        ProductSupplier(supplier_id=sup1.id, company_id=c.id, product_id=wid1.id, preferred=True, lead_time_days=7),
        ProductSupplier(supplier_id=sup1.id, company_id=c.id, product_id=wid2.id, preferred=False, lead_time_days=10),
        ProductSupplier(supplier_id=sup2.id, company_id=c.id, product_id=wid1.id, preferred=False, lead_time_days=5),
        ProductSupplier(supplier_id=sup2.id, company_id=c.id, product_id=gad1.id, preferred=True, lead_time_days=4),
    ])

    # recent orders (within 30 days)
    o1 = Order(company_id=c.id, status="completed", created_at=now - timedelta(days=3))
    o2 = Order(company_id=c.id, status="shipped",   created_at=now - timedelta(days=8))
    db_session.add_all([o1, o2]); db_session.flush()

    db_session.add_all([
        OrderLine(order_id=o1.id, product_id=wid1.id, warehouse_id=main.id, qty=Decimal("10")),
        OrderLine(order_id=o2.id, product_id=wid1.id, warehouse_id=main.id, qty=Decimal("6")),
        OrderLine(order_id=o1.id, product_id=wid2.id, warehouse_id=main.id, qty=Decimal("3")),
        OrderLine(order_id=o2.id, product_id=gad1.id, warehouse_id=main.id, qty=Decimal("2")),
    ])

    db_session.commit()
    return c.id, main.id, aux.id, {"wid1": wid1.id, "wid2": wid2.id, "gad1": gad1.id}


def test_low_stock_alerts_happy_path(client, db_session):
    company_id, main_id, _, _ = _seed_for_alerts(db_session)

    r = client.get(f"/api/companies/{company_id}/alerts/low-stock?lookback_days=30")
    assert r.status_code == 200
    body = r.get_json()
    assert "alerts" in body and isinstance(body["alerts"], list)
    assert body["total_alerts"] >= 1

    # Verify essential fields exist on first alert
    first = body["alerts"][0]
    for key in ("product_id", "product_name", "sku", "warehouse_id",
                "warehouse_name", "current_stock", "threshold"):
        assert key in first

    # Check that WID-001 @ Main is present and below threshold
    has_wid1_main = any(
        a["sku"] == "WID-001" and a["warehouse_id"] == main_id and a["current_stock"] < a["threshold"]
        for a in body["alerts"]
    )
    assert has_wid1_main


def test_low_stock_alerts_filters_by_warehouse(client, db_session):
    company_id, main_id, aux_id, _ = _seed_for_alerts(db_session)

    # Only main warehouse
    r1 = client.get(f"/api/companies/{company_id}/alerts/low-stock?lookback_days=30&warehouse_id={main_id}")
    assert r1.status_code == 200
    for a in r1.get_json()["alerts"]:
        assert a["warehouse_id"] == main_id

    # Only aux warehouse -> likely 0 alerts (aux has plenty + no sales)
    r2 = client.get(f"/api/companies/{company_id}/alerts/low-stock?lookback_days=30&warehouse_id={aux_id}")
    assert r2.status_code == 200
    assert r2.get_json()["total_alerts"] == 0
