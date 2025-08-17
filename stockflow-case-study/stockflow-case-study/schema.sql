-- Companies and Warehouses
CREATE TABLE companies (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE warehouses (
  id            BIGSERIAL PRIMARY KEY,
  company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  location      TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_warehouses_company ON warehouses(company_id);

-- Product taxonomy and products
CREATE TABLE product_types (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  -- business rule: low stock threshold varies by product type
  default_low_stock_threshold INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE products (
  id            BIGSERIAL PRIMARY KEY,
  sku           TEXT NOT NULL UNIQUE,                    -- unique across platform
  name          TEXT NOT NULL,
  product_type_id BIGINT REFERENCES product_types(id),
  price         NUMERIC(12,2) NOT NULL CHECK (price >= 0),
  is_bundle     BOOLEAN NOT NULL DEFAULT FALSE,          -- for bundles
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Bundles: a bundle product composed of other products (no cycles enforced by app)
CREATE TABLE product_bundles (
  bundle_product_id   BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  component_product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
  component_qty       NUMERIC(12,4) NOT NULL CHECK (component_qty > 0),
  PRIMARY KEY (bundle_product_id, component_product_id)
);

-- Inventory per warehouse
CREATE TABLE inventory (
  product_id    BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  warehouse_id  BIGINT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
  quantity      NUMERIC(16,4) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  PRIMARY KEY (product_id, warehouse_id)
);

-- Track inventory level changes (events/ledger)
CREATE TYPE inventory_reason AS ENUM ('SALE','PURCHASE','ADJUSTMENT','TRANSFER_OUT','TRANSFER_IN','RETURN');

CREATE TABLE inventory_transactions (
  id            BIGSERIAL PRIMARY KEY,
  product_id    BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  warehouse_id  BIGINT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
  qty_delta     NUMERIC(16,4) NOT NULL,                 -- can be negative
  reason        inventory_reason NOT NULL,
  ref_type      TEXT,                                   -- e.g., 'order','po','rma'
  ref_id        TEXT,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_inv_txn_product_wh_time ON inventory_transactions(product_id, warehouse_id, occurred_at DESC);

-- Suppliers and mapping to companies/products
CREATE TABLE suppliers (
  id            BIGSERIAL PRIMARY KEY,
  name          TEXT NOT NULL,
  contact_email TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A supplier provides products to a specific company (prices/lead time can differ per company)
CREATE TABLE product_suppliers (
  supplier_id   BIGINT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
  company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  product_id    BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  supplier_sku  TEXT,
  lead_time_days INTEGER NOT NULL DEFAULT 7 CHECK (lead_time_days >= 0),
  preferred     BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (supplier_id, company_id, product_id)
);
CREATE INDEX idx_prod_sup_company_prod ON product_suppliers(company_id, product_id);

-- Company/product thresholds (override product type default)
CREATE TABLE product_thresholds (
  company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  product_id    BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  -- optional per-warehouse override
  warehouse_id  BIGINT REFERENCES warehouses(id) ON DELETE CASCADE,
  threshold     INTEGER NOT NULL CHECK (threshold >= 0),
  PRIMARY KEY (company_id, product_id, warehouse_id)
);

-- Minimal sales model for "recent activity"
CREATE TABLE orders (
  id            BIGSERIAL PRIMARY KEY,
  company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  status        TEXT NOT NULL,                          -- 'placed','shipped','completed'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_orders_company_time ON orders(company_id, created_at DESC);

CREATE TABLE order_lines (
  id            BIGSERIAL PRIMARY KEY,
  order_id      BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id    BIGINT NOT NULL REFERENCES products(id),
  warehouse_id  BIGINT NOT NULL REFERENCES warehouses(id),
  qty           NUMERIC(16,4) NOT NULL CHECK (qty > 0)
);
CREATE INDEX idx_ol_company_prod_wh ON order_lines(product_id, warehouse_id);
