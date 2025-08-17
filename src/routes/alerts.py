from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import select, func
from ..db import db
from ..models import (
    Warehouse, Product, ProductType, Inventory,
    ProductThreshold, Order, OrderLine, Supplier, ProductSupplier
)

alerts_bp = Blueprint("alerts", __name__)

def _ads(company_id: int, product_id: int, warehouse_id: int, since_dt, lookback_days: int) -> float:
    # orders in window for company
    ro = (
        select(Order.id)
        .where(
            Order.company_id == company_id,
            Order.created_at >= since_dt,
            Order.status.in_(["shipped", "completed"]),
        )
    ).subquery()

    total = db.session.execute(
        select(func.coalesce(func.sum(OrderLine.qty), 0.0))
        .where(
            OrderLine.order_id.in_(select(ro.c.id)),
            OrderLine.product_id == product_id,
            OrderLine.warehouse_id == warehouse_id,
        )
    ).scalar_one()

    try:
        total = float(total)
    except Exception:
        total = 0.0

    return total / max(lookback_days, 1)


def _threshold(company_id: int, product: Product, warehouse_id: int) -> float:
    # per-warehouse override
    t_wh = db.session.execute(
        select(ProductThreshold.threshold)
        .where(
            ProductThreshold.company_id == company_id,
            ProductThreshold.product_id == product.id,
            ProductThreshold.warehouse_id == warehouse_id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if t_wh is not None:
        return float(t_wh)

    # product-level override
    t_prod = db.session.execute(
        select(ProductThreshold.threshold)
        .where(
            ProductThreshold.company_id == company_id,
            ProductThreshold.product_id == product.id,
            ProductThreshold.warehouse_id.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()
    if t_prod is not None:
        return float(t_prod)

    # product type default
    if product.product_type_id:
        t_def = db.session.execute(
            select(ProductType.default_low_stock_threshold)
            .where(ProductType.id == product.product_type_id)
            .limit(1)
        ).scalar_one_or_none()
        if t_def is not None:
            return float(t_def)

    return 0.0


def _best_supplier(company_id: int, product_id: int):
    # preferred first, shortest lead time
    pref = db.session.execute(
        select(ProductSupplier.supplier_id)
        .where(
            ProductSupplier.company_id == company_id,
            ProductSupplier.product_id == product_id,
            ProductSupplier.preferred.is_(True),
        )
        .order_by(ProductSupplier.lead_time_days.asc(), ProductSupplier.supplier_id.asc())
        .limit(1)
    ).scalar_one_or_none()

    sid = pref
    if sid is None:
        sid = db.session.execute(
            select(ProductSupplier.supplier_id)
            .where(
                ProductSupplier.company_id == company_id,
                ProductSupplier.product_id == product_id,
            )
            .order_by(ProductSupplier.lead_time_days.asc(), ProductSupplier.supplier_id.asc())
            .limit(1)
        ).scalar_one_or_none()

    return db.session.get(Supplier, sid) if sid is not None else None


@alerts_bp.get("/api/companies/<int:company_id>/alerts/low-stock")
def low_stock_alerts(company_id: int):
    lookback_days = int(request.args.get("lookback_days", 30))
    limit = int(request.args.get("limit", 100))
    target_warehouse = request.args.get("warehouse_id")
    debug = request.args.get("debug") == "1"

    try:
        target_warehouse = int(target_warehouse) if target_warehouse is not None else None
    except ValueError:
        return jsonify({"error": "invalid_warehouse_id"}), 400

    since = datetime.utcnow() - timedelta(days=lookback_days)

    # inventory of this company (optional warehouse filter)
    inv_q = (
        select(Inventory.product_id, Inventory.warehouse_id, Inventory.quantity)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(Warehouse.company_id == company_id)
    )
    if target_warehouse:
        inv_q = inv_q.where(Inventory.warehouse_id == target_warehouse)

    inv_rows = db.session.execute(inv_q).all()

    # prefetch
    product_ids = {pid for (pid, _, _) in inv_rows}
    warehouse_ids = {wid for (_, wid, _) in inv_rows}
    products = {
        p.id: p for p in db.session.execute(select(Product).where(Product.id.in_(product_ids))).scalars().all()
    }
    warehouses = {
        w.id: w for w in db.session.execute(select(Warehouse).where(Warehouse.id.in_(warehouse_ids))).scalars().all()
    }

    alerts = []
    dbg = []

    for (pid, wid, qty) in inv_rows:
        p = products.get(pid)
        w = warehouses.get(wid)
        if not p or not w:
            continue

        try:
            stock = float(qty)
        except Exception:
            stock = 0.0

        ads = _ads(company_id, pid, wid, since, lookback_days)
        thr = _threshold(company_id, p, wid)

        reason = []
        if ads <= 0:
            reason.append("no_recent_sales")
        if thr <= 0:
            reason.append("zero_threshold")
        if stock >= thr:
            reason.append("stock_not_below_threshold")

        keep = (ads > 0) and (thr > 0) and (stock < thr)

        if debug:
            dbg.append({
                "sku": p.sku,
                "product_id": pid,
                "warehouse_id": wid,
                "warehouse_name": w.name,
                "stock": stock,
                "threshold": thr,
                "ads": ads,
                "decision": "keep" if keep else "skip",
                "reason_if_skip": reason
            })

        if not keep:
            continue

        sup = _best_supplier(company_id, pid)
        supplier = None if sup is None else {
            "id": sup.id, "name": sup.name, "contact_email": sup.contact_email
        }

        alerts.append({
            "product_id": p.id,
            "product_name": p.name,
            "sku": p.sku,
            "warehouse_id": w.id,
            "warehouse_name": w.name,
            "current_stock": stock,
            "threshold": thr,
            "days_until_stockout": (stock / ads) if ads > 0 else None,
            "supplier": supplier
        })

        if len(alerts) >= limit:
            break

    alerts.sort(key=lambda a: (a["current_stock"] - a["threshold"]))
    if len(alerts) > limit:
        alerts = alerts[:limit]

    resp = {"alerts": alerts, "total_alerts": len(alerts)}
    if debug:
        resp["debug"] = dbg
    return jsonify(resp), 200
