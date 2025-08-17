# Stockflow Case Study (Backend Engineering Intern)

A small Flask + SQLAlchemy service that models products, inventory, suppliers, and low-stock alerts. The repo contains:

- **Part 1**: Fix and harden `POST /api/products`  
- **Part 2**: A clean relational schema with constraints (`schema.sql`)  
- **Part 3**: `GET /api/companies/{id}/alerts/low-stock` that flags items below threshold (with supplier + days-to-stockout)

---

## Project Structure
```
stockflow-case-study/
├─ README.md
├─ requirements.txt
├─ schema.sql
├─ scripts/
│ ├─ seed.py # dev seeding
│ └─ peek.py # prints inventory, thresholds, ADS for sanity
├─ src/
│ ├─ app.py
│ ├─ config.py
│ ├─ db.py
│ ├─ models.py
│ ├─ seeds.py
│ └─ routes/
│ ├─ products.py 
│ └─ alerts.py
└─ tests/
├─ conftest.py
├─ test_products.py
└─ test_alerts.py
```



##  Tech

- Python 3.12+
- Flask 3, Flask-SQLAlchemy 3, SQLAlchemy 2
- SQLite (dev/test) or Postgres (optional)
- Pytest

---

##  Quick Start (SQLite)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Force SQLite (absolute path inside repo for consistency)
export USE_SQLITE=1

# Start once to create tables
python -m src.app  # Ctrl+C once it's running

# Seed demo data (company, warehouses, products, orders, thresholds, suppliers)
SEED_ACTION=reset python -m scripts.seed

# Run the API
python -m src.app
```

Health & state:
```
curl -s http://127.0.0.1:5000/ | jq
curl -s http://127.0.0.1:5000/__debug/state | jq
```

## Postgres (optional)
```
export DATABASE_URL="postgresql://postgres:password@localhost:5432/stockflow"
unset USE_SQLITE
SEED_ACTION=reset python -m scripts.seed
python -m src.app
```

## Environment Variables
- USE_SQLITE=1 — use repo-local SQLite db

- DATABASE_URL — full SQLAlchemy URL (overrides USE_SQLITE)

- SEED_ACTION=reset — wipe + reseed

- FLASK_DEBUG=1 — enable debug mode

## Tests
```
pytest -q
```
Covers:

- Product creation (201, 400, 404, 409)

- Low-stock alerts, with filters & debug

## Endpoints

**Health**

- GET / → {"status":"ok"}

- GET /__debug/state

POST /api/products 

```
{
  "name": "Widget A",
  "sku": "WID-001",
  "price": "12.50",
  "warehouse_id": 1,
  "initial_quantity": 10
}
```
Responses

- 201 product created

- 400 bad payload

- 404 warehouse not found

- 409 SKU exists

`GET /api/companies/{id}/alerts/low-stock`

Query params:

- lookback_days=30

- warehouse_id=... optional

- debug=1 optional

Response:
```
{
  "alerts": [
    {
      "product_id": 1,
      "sku": "WID-001",
      "warehouse_name": "Main Warehouse",
      "current_stock": 5,
      "threshold": 18,
      "days_until_stockout": 9.3,
      "supplier": {"id":1,"name":"Supplier Corp"}
    }
  ],
  "total_alerts": 1
}
```

##  Data Model

See `schema.sql`:

- Companies, warehouses  
- Products & product types  
- Inventory with constraints  
- Threshold overrides  
- Suppliers with lead times  
- Orders + order_lines for sales history  

---

##  Part 1 Fixes

- Validation, error codes  
- SKU uniqueness surfaced  
- Safe transaction handling (`flush+commit`)  
- Idempotent inventory set  
- Warehouse existence check  

---

##  Part 3 Alerts Logic

- Compute average daily sales from recent orders  
- Pick threshold: warehouse override > product override > type default > 0  
- If stock < threshold and ADS > 0 → include in alerts  
- Attach best supplier (preferred, else shortest lead time)  

---

##  Dev Helpers

- `scripts/seed.py` → reset + load demo data  
- `scripts/peek.py` → print inventory, thresholds, ADS  
- `GET /__debug/state` → counts + db url  


##  Requirements
```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
SQLAlchemy==2.0.25
psycopg2-binary==2.9.9
pytest
```


