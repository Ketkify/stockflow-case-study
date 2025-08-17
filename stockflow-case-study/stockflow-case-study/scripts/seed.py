import os
import sys
from flask import Flask

# Allow "python -m scripts.seed" from repo root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app import create_app
from src.db import db
from src.seeds import seed_core, wipe_all

def main():
    app: Flask = create_app()
    with app.app_context():
        action = (os.getenv("SEED_ACTION") or "reset").lower()
        if action == "reset":
            print("Wiping all tables…")
            wipe_all()
        print("Seeding core data…")
        info = seed_core()
        print("Done. Context:")
        print(info)

if __name__ == "__main__":
    main()
