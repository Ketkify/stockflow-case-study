from flask import Blueprint, request, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..db import db
from ..models import Product, Inventory, Warehouse
from ..utils.money import as_money

bp = Blueprint("products", __name__)

@bp.post("/api/products")
def create_product():
    payload = request.get_json(silent=True) or {}

    name = (payload.get("name") or "").strip()
    sku = (payload.get("sku") or "").strip()
    price_raw = payload.get("price")
    initial_quantity = payload.get("initial_quantity", 0)
    warehouse_id = payload.get("warehouse_id")  # optional

    # ---- validation ----
    errors = {}
    if not name:
        errors["name"] = "required"
    if not sku:
        errors["sku"] = "required"
    try:
        price = as_money(price_raw)
    except Exception:
        errors["price"] = "invalid_decimal"
    try:
        initial_quantity = int(initial_quantity)
        if initial_quantity < 0:
            raise ValueError()
    except Exception:
        errors["initial_quantity"] = "must_be_non_negative_integer"

    if errors:
        return jsonify({"errors": errors}), 400

    # If warehouse_id provided, verify it exists
    if warehouse_id is not None:
        wh = db.session.execute(
            select(Warehouse.id).where(Warehouse.id == warehouse_id)
        ).scalar_one_or_none()
        if wh is None:
            return jsonify({"error": "warehouse_not_found"}), 404

    try:
        # ---- create product ----
        product = Product(name=name, sku=sku, price=price)
        db.session.add(product)
        db.session.flush()  # populate product.id

        # ---- optional initial inventory (idempotent "set") ----
        if warehouse_id is not None:
            inv = db.session.execute(
                select(Inventory).where(
                    Inventory.product_id == product.id,
                    Inventory.warehouse_id == warehouse_id
                )
            ).scalar_one_or_none()

            if inv:
                inv.quantity = initial_quantity
            else:
                inv = Inventory(
                    product_id=product.id,
                    warehouse_id=warehouse_id,
                    quantity=initial_quantity
                )
                db.session.add(inv)

        db.session.commit()
        return jsonify({"message": "Product created", "product_id": product.id}), 201

    except IntegrityError:
        db.session.rollback()
        # Most likely a SKU uniqueness violation
        return jsonify({"error": "sku_already_exists"}), 409

    except Exception as e:
        db.session.rollback()
        # Fallback: surface a clear message in dev; keep generic in prod if you prefer
        return jsonify({"error": "internal_error", "detail": str(e)}), 500
