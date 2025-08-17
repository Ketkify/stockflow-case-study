from flask import Flask
from .db import db
from . import config
from .models import *  # noqa
from .routes.products import bp as products_bp
from .routes.alerts import alerts_bp

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    print(f"[stockflow] Using DB: {app.config['SQLALCHEMY_DATABASE_URI']}")  # <— LOG IT

    db.init_app(app)

    @app.get("/")
    def health():
        return {"status": "ok"}

    # quick state probe
    @app.get("/__debug/state")
    def dbg_state():
        from sqlalchemy import select, func
        companies = db.session.execute(select(func.count(Company.id))).scalar_one()
        warehouses = db.session.execute(select(func.count(Warehouse.id))).scalar_one()
        inventory = db.session.execute(select(func.count(Inventory.product_id))).scalar_one()
        orders = db.session.execute(select(func.count(Order.id))).scalar_one()
        return {
            "db": app.config["SQLALCHEMY_DATABASE_URI"],
            "counts": {
                "companies": companies,
                "warehouses": warehouses,
                "inventory_rows": inventory,
                "orders": orders,
            }
        }

    app.register_blueprint(products_bp)
    app.register_blueprint(alerts_bp)

    with app.app_context():
        db.create_all()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=config.DEBUG, port=5000)
