import asyncio
# pyrefly: ignore [missing-import]
from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE tickets ADD COLUMN ai_summary TEXT;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN ai_first_fix JSON;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN ai_similar_tickets JSON;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN last_ai_updated_at TIMESTAMP WITH TIME ZONE;"))
            print("Successfully added AI columns to tickets table.")
        except Exception as e:
            print(f"Migration error (columns might already exist): {e}")

if __name__ == "__main__":
    migrate()
