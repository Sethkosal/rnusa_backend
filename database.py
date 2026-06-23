import os
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "tshirt.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name_en = Column(String, nullable=False)
    name_km = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    order = Column(Integer, default=0)
    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name_en = Column(String, nullable=False)
    name_km = Column(String, nullable=False)
    description_en = Column(Text, nullable=False)
    description_km = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    image = Column(String, nullable=True)        # main image filename
    images = Column(Text, nullable=True)          # comma-separated additional images
    tags = Column(String, nullable=True)          # comma-separated tags
    featured = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    category = relationship("Category", back_populates="products")


class QuoteRequest(Base):
    __tablename__ = "quote_requests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    company = Column(String, nullable=True)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    product_interest = Column(String, nullable=True)
    quantity = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Seed default categories if empty
    db = SessionLocal()
    if db.query(Category).count() == 0:
        categories = [
            Category(name_en="T-Shirts", name_km="អាវយឺត", slug="t-shirts", order=1),
            Category(name_en="Caps & Hats", name_km="មួក", slug="caps-hats", order=2),
            Category(name_en="Bags", name_km="កាបូប", slug="bags", order=3),
            Category(name_en="Jackets", name_km="អាវក្រៅ", slug="jackets", order=4),
            Category(name_en="Accessories", name_km="គ្រឿងបន្លាស់", slug="accessories", order=5),
        ]
        db.add_all(categories)
        db.commit()
    db.close()
