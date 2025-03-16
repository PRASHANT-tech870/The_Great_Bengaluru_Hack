from app import create_app, db
from app.models.user import User

def init_database():
    app = create_app()
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        print("Database tables created successfully!")

if __name__ == "__main__":
    init_database() 