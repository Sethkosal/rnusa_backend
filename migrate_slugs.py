"""
One-time migration: adds the slug column and populates slugs
for all existing products that don't have one yet.
Safe to run multiple times (idempotent).
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from database import engine, SessionLocal, Product


def _base_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def make_unique_slug(base: str, existing: set) -> str:
    slug = base
    counter = 2
    while slug in existing:
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def main():
    # 1. Add slug column if it doesn't exist yet
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(products)"))]
        if 'slug' not in cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN slug TEXT"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_products_slug ON products (slug)"))
            conn.commit()
            print("✓ Added slug column to products table")
        else:
            print("✓ slug column already exists")

    # 2. Populate slugs for products that don't have one
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        existing_slugs = {p.slug for p in products if p.slug}
        updated = 0

        for p in products:
            if p.slug:
                continue
            base = _base_slug(p.name_en)
            slug = make_unique_slug(base, existing_slugs)
            existing_slugs.add(slug)
            p.slug = slug
            updated += 1
            print(f"  {p.id}: '{p.name_en}' → '{slug}'")

        db.commit()
        print(f"\n✓ Populated slugs for {updated} product(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
