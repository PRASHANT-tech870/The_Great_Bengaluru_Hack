from app import db
from app.models.user import User
from app.models.store import Reward, PointsTransaction, Redemption
from sqlalchemy import inspect

def init_db(app):
    with app.app_context():
        # Create tables only if they don't exist
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            # Only create tables if database is empty
            db.create_all()
            print("Database tables created.")
        else:
            print("Database tables already exist.") 