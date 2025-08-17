# scripts/peek.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta
from sqlalchemy import select, func, cast, Numeric, and_
from src.app import create_app
from src.db import db
from src.models import Company, Warehouse, Product, ProductType, Inventory, ProductThreshold, Order, OrderLine

def main():
    app = create_app()
    with app.app_context():
        company_id = int(os.getenv("COMPANY_ID", "1"))
        lookback_days = int(os.getenv("LOOKBACK_DAYS", "30"))
        since = datetime.utcnow() - timedelta(days=lookback_days)

        print(f"Company {company_id}")
        c = db.session.get(Company, company_id)
        if not c:
            print("Company not found")
            return

        print("\nWarehouses:")
        for (wid, wname) in db.session.execute(
            select(Warehouse.id, Warehouse.name).where(Warehouse.company_id == company_id)
        ):
            print(f"  {wid}: {wname}")

        print("\nInventory:")
        q_inv = (
            select(
                Product.sku, Product.name, Warehouse.name, cast(Inventory.quantity, Numeric(18,6))
            )
            .join(Inventory, Inventory.product_id == Product.id)
            .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
            .where(Warehouse.company_id == company_id)
            .order_by(Product.sku, Warehouse.name)
        )
        for row in db.session.execute(q_inv):
            print(f"  {row[0]} | {row[1]} | {row[2]} | stock={row[3]}")

        print("\nThresholds (type defaults):")
        q_type = (
            select(Product.sku, ProductType.default_low_stock_threshold)
            .join(ProductType, Product.product_type_id == ProductType.id, isouter=True)
            .order_by(Product.sku)
        )
        for row in db.session.execute(q_type):
            print(f"  {row[0]} | type_thr={row[1]}")

        print("\nThreshold overrides:")
        q_thr = (
            select(Product.sku, ProductThreshold.warehouse_id, ProductThreshold.threshold)
            .join(Product, Product.id == ProductThreshold.product_id)
            .where(ProductThreshold.company_id == company_id)
            .order_by(Product.sku, ProductThreshold.warehouse_id)
        )
        for row in db.session.execute(q_thr):
            print(f"  {row[0]} | wh={row[1]} | thr={row[2]}")

        print("\nRecent orders & ADS (avg daily sales):")
        recent_orders_sq = (
            select(Order.id)
            .where(
                Order.company_id == company_id,
                Order.created_at >= since,
                Order.status.in_(["shipped", "completed"])
            )
        ).subquery()

        q_ads = (
            select(
                Product.sku, Warehouse.name,
                (cast(func.coalesce(func.sum(OrderLine.qty), 0), Numeric(18,6))/lookback_days).label("ads")
            )
            .join(Product, Product.id == OrderLine.product_id)
            .join(Warehouse, Warehouse.id == OrderLine.warehouse_id)
            .where(OrderLine.order_id.in_(select(recent_orders_sq.c.id)))
            .group_by(Product.sku, Warehouse.name)
            .order_by(Product.sku, Warehouse.name)
        )
        for row in db.session.execute(q_ads):
            print(f"  {row[0]} | {row[1]} | ads={row[2]}")

if __name__ == "__main__":
    main()
