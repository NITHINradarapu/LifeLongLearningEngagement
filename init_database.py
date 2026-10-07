from app import app, init_db, DB_PATH
with app.app_context():
    init_db()
print(f"learninglearning.db is ready: {DB_PATH}")
