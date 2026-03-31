from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        lead_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(leads)"))}
        if "company_id" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN company_id INTEGER"))
        if "status" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN status VARCHAR(40) DEFAULT 'new'"))
        if "assigned_price_eur" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN assigned_price_eur INTEGER"))
        if "rooms" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN rooms INTEGER"))
        if "distance_km" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN distance_km FLOAT"))
        if "express" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN express BOOLEAN DEFAULT 0"))
        if "message" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN message VARCHAR(5000)"))
        if "photo_name" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN photo_name VARCHAR(255)"))
        if "accepted_agb" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN accepted_agb BOOLEAN DEFAULT 0"))
        if "accepted_privacy" not in lead_columns:
            conn.execute(text("ALTER TABLE leads ADD COLUMN accepted_privacy BOOLEAN DEFAULT 0"))
        conn.execute(text("UPDATE leads SET status = 'new' WHERE status IS NULL OR status = ''"))
        conn.execute(text("UPDATE leads SET express = 0 WHERE express IS NULL"))
        conn.execute(text("UPDATE leads SET accepted_agb = 0 WHERE accepted_agb IS NULL"))
        conn.execute(text("UPDATE leads SET accepted_privacy = 0 WHERE accepted_privacy IS NULL"))

        company_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(companies)"))
        }
        if "last_assigned_at" not in company_columns:
            conn.execute(text("ALTER TABLE companies ADD COLUMN last_assigned_at DATETIME"))
        if "balance_eur" not in company_columns:
            conn.execute(text("ALTER TABLE companies ADD COLUMN balance_eur FLOAT DEFAULT 0"))
        if "api_key" not in company_columns:
            conn.execute(text("ALTER TABLE companies ADD COLUMN api_key VARCHAR(120)"))
        conn.execute(text("UPDATE companies SET balance_eur = 0 WHERE balance_eur IS NULL"))
