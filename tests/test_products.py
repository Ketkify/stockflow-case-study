from decimal import Decimal

def _seed_company_and_wh(db_session):
    from src.models import Company, Warehouse
    c = Company(name="Acme Inc")
    db_session.add(c)
    db_session.flush()
    w = Warehouse(company_id=c.id, name="Main Warehouse", location="NYC")
    db_session.add(w)
    db_session.commit()
    return c.id, w.id

def test_create_product_success(client, db_session):
    from src.models import Product, Inventory

    _, wh_id = _seed_company_and_wh(db_session)

    payload = {
        "name": "Widget A",
        "sku": "WID-001",
        "price": "12.50",
        "warehouse_id": wh_id,
        "initial_quantity": 10
    }
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201, resp.get_json()
    pid = resp.get_json()["product_id"]

    # verify in DB
    p = db_session.get(Product, pid)
    assert p is not None
    assert p.sku == "WID-001"
    assert str(p.price) in ("12.50", "12.5")  # allow repr differences

    inv = db_session.get(Inventory, {"product_id": pid, "warehouse_id": wh_id})
    assert inv is not None
    assert float(inv.quantity) == 10.0


def test_create_duplicate_sku_conflict(client, db_session):
    from src.models import Product
    _, wh_id = _seed_company_and_wh(db_session)

    # First create
    payload = {"name": "Widget A", "sku": "WID-001", "price": "12.50",
               "warehouse_id": wh_id, "initial_quantity": 5}
    r1 = client.post("/api/products", json=payload)
    assert r1.status_code == 201

    # Duplicate SKU
    r2 = client.post("/api/products", json={"name": "Dup", "sku": "WID-001", "price": "1.00"})
    assert r2.status_code == 409
    assert r2.get_json()["error"] == "sku_already_exists"


def test_create_product_bad_payload(client, db_session):
    # invalid price + invalid initial_quantity
    payload = {"name": "", "sku": "", "price": "abc", "initial_quantity": -1}
    r = client.post("/api/products", json=payload)
    assert r.status_code == 400
    body = r.get_json()
    # expect validation keys
    for key in ("name", "sku", "price", "initial_quantity"):
        assert key in body["errors"]


def test_create_with_unknown_warehouse(client, db_session):
    # warehouse_id doesn't exist -> 404
    payload = {"name": "X", "sku": "X-1", "price": "1.00", "warehouse_id": 999, "initial_quantity": 1}
    r = client.post("/api/products", json=payload)
    assert r.status_code == 404
    assert r.get_json()["error"] == "warehouse_not_found"
