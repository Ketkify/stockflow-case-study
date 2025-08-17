from enum import Enum
from decimal import Decimal
from sqlalchemy import UniqueConstraint, CheckConstraint, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import NUMERIC
from .db import db

# Helpers to be portable across Postgres/SQLite
NUMERIC_MONEY = NUMERIC(12, 2)
NUMERIC_QTY   = NUMERIC(16, 4)

# ---------- Core ----------

class Company(db.Model):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[str] = mapped_column(server_default=func.now())
    warehouses: Mapped[list["Warehouse"]] = relationship(back_populates="company")


class Warehouse(db.Model):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(db.ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]
    location: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="warehouses")
    inventory_rows: Mapped[list["Inventory"]] = relationship(back_populates="warehouse")


class ProductType(db.Model):
    __tablename__ = "product_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    default_low_stock_threshold: Mapped[int] = mapped_column(default=0)


class Product(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    product_type_id: Mapped[int | None] = mapped_column(db.ForeignKey("product_types.id"))
    price: Mapped[Decimal] = mapped_column(NUMERIC_MONEY, default=Decimal("0.00"))
    is_bundle: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(server_default=func.now())

    product_type: Mapped[ProductType | None] = relationship()
    bundles_as_parent: Mapped[list["ProductBundle"]] = relationship(
        back_populates="bundle", foreign_keys="ProductBundle.bundle_product_id", cascade="all, delete-orphan"
    )
    bundles_as_component: Mapped[list["ProductBundle"]] = relationship(
        back_populates="component", foreign_keys="ProductBundle.component_product_id"
    )
    inventory_rows: Mapped[list["Inventory"]] = relationship(back_populates="product")


class ProductBundle(db.Model):
    __tablename__ = "product_bundles"
    bundle_product_id: Mapped[int] = mapped_column(
        db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    component_product_id: Mapped[int] = mapped_column(
        db.ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    component_qty: Mapped[Decimal] = mapped_column(NUMERIC_QTY)

    bundle: Mapped[Product] = relationship(foreign_keys=[bundle_product_id], back_populates="bundles_as_parent")
    component: Mapped[Product] = relationship(foreign_keys=[component_product_id], back_populates="bundles_as_component")


class Inventory(db.Model):
    __tablename__ = "inventory"
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(db.ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(NUMERIC_QTY, default=Decimal("0"))

    product: Mapped[Product] = relationship(back_populates="inventory_rows")
    warehouse: Mapped[Warehouse] = relationship(back_populates="inventory_rows")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_inventory_nonneg"),
    )


class InvReason(Enum):
    SALE = "SALE"
    PURCHASE = "PURCHASE"
    ADJUSTMENT = "ADJUSTMENT"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    RETURN = "RETURN"


class InventoryTransaction(db.Model):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[int] = mapped_column(db.ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    qty_delta: Mapped[Decimal] = mapped_column(NUMERIC_QTY)
    reason: Mapped[InvReason] = mapped_column(SAEnum(InvReason))
    ref_type: Mapped[str | None]
    ref_id: Mapped[str | None]
    occurred_at: Mapped[str] = mapped_column(server_default=func.now())

    product: Mapped[Product] = relationship()
    warehouse: Mapped[Warehouse] = relationship()


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    contact_email: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(server_default=func.now())


class ProductSupplier(db.Model):
    __tablename__ = "product_suppliers"
    supplier_id: Mapped[int] = mapped_column(db.ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[int] = mapped_column(db.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)

    supplier_sku: Mapped[str | None]
    lead_time_days: Mapped[int] = mapped_column(default=7)
    preferred: Mapped[bool] = mapped_column(default=False)

    supplier: Mapped[Supplier] = relationship()
    product: Mapped[Product] = relationship()
    company: Mapped[Company] = relationship()

    __table_args__ = (
        UniqueConstraint("supplier_id", "company_id", "product_id", name="uq_prod_sup"),
        CheckConstraint("lead_time_days >= 0", name="chk_lead_time_nonneg"),
    )


class ProductThreshold(db.Model):
    __tablename__ = "product_thresholds"
    company_id: Mapped[int] = mapped_column(db.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    # Optional per-warehouse override; when null, applies to all warehouses in company
    warehouse_id: Mapped[int | None] = mapped_column(db.ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True, nullable=True)
    threshold: Mapped[int] = mapped_column(default=0)

    company: Mapped[Company] = relationship()
    product: Mapped[Product] = relationship()
    warehouse: Mapped[Warehouse] = relationship()


# ---------- Minimal Orders for "recent sales" ----------

class Order(db.Model):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(db.ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    status: Mapped[str]  # 'placed','shipped','completed'
    created_at: Mapped[str] = mapped_column(server_default=func.now())

    company: Mapped[Company] = relationship()
    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order")


class OrderLine(db.Model):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(db.ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("products.id"), index=True)
    warehouse_id: Mapped[int] = mapped_column(db.ForeignKey("warehouses.id"), index=True)
    qty: Mapped[Decimal] = mapped_column(NUMERIC_QTY)

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()
    warehouse: Mapped[Warehouse] = relationship()

    __table_args__ = (
        CheckConstraint("qty > 0", name="chk_orderline_qty_pos"),
    )
