from app import app, db

with app.app_context():
    try:
        # Drop all tables
        db.drop_all()
        print("All tables dropped")
        # Create all tables

        db.create_all()
        print("Database initialized successfully.")

    except Exception as e:
        print(f"Error initializing database: {e}")
