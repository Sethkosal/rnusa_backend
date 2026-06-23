import os
import shutil
from typing import Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, init_db, Product, Category, QuoteRequest
from auth import authenticate_admin, create_access_token, get_current_admin

load_dotenv()

app = FastAPI(title="T-Shirt Business API")

# CORS — allow Next.js frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded product images
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.on_event("startup")
def startup():
    init_db()


# ─────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────

@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.order).all()


@app.get("/api/products")
def get_products(
    category: Optional[str] = None,
    featured: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.active == True)
    if category:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            query = query.filter(Product.category_id == cat.id)
    if featured is not None:
        query = query.filter(Product.featured == featured)
    products = query.order_by(Product.id.desc()).all()
    return [serialize_product(p) for p in products]


@app.get("/api/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.active == True
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(product)


class QuoteRequestIn(BaseModel):
    name: str
    company: Optional[str] = None
    phone: str
    email: Optional[str] = None
    product_interest: Optional[str] = None
    quantity: Optional[str] = None
    message: Optional[str] = None


@app.post("/api/quotes", status_code=201)
def submit_quote(data: QuoteRequestIn, db: Session = Depends(get_db)):
    quote = QuoteRequest(**data.dict())
    db.add(quote)
    db.commit()
    return {"status": "received", "message": "We'll contact you within a few hours."}


# ─────────────────────────────────────────
# ADMIN AUTH
# ─────────────────────────────────────────

@app.post("/api/admin/login")
def admin_login(form: OAuth2PasswordRequestForm = Depends()):
    if not authenticate_admin(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    token = create_access_token({"sub": form.username})
    return {"access_token": token, "token_type": "bearer"}


# ─────────────────────────────────────────
# ADMIN PRODUCT ROUTES
# ─────────────────────────────────────────

@app.get("/api/admin/products")
def admin_get_products(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    products = db.query(Product).order_by(Product.id.desc()).all()
    return [serialize_product(p) for p in products]


@app.post("/api/admin/products", status_code=201)
async def admin_create_product(
    name_en: str = Form(...),
    name_km: str = Form(...),
    description_en: str = Form(...),
    description_km: str = Form(...),
    category_id: int = Form(...),
    tags: Optional[str] = Form(None),
    featured: bool = Form(False),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    image_filename = None
    if image and image.filename:
        image_filename = save_upload(image)

    product = Product(
        name_en=name_en,
        name_km=name_km,
        description_en=description_en,
        description_km=description_km,
        category_id=category_id,
        tags=tags,
        featured=featured,
        image=image_filename,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return serialize_product(product)


@app.put("/api/admin/products/{product_id}")
async def admin_update_product(
    product_id: int,
    name_en: str = Form(...),
    name_km: str = Form(...),
    description_en: str = Form(...),
    description_km: str = Form(...),
    category_id: int = Form(...),
    tags: Optional[str] = Form(None),
    featured: bool = Form(False),
    active: bool = Form(True),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.name_en = name_en
    product.name_km = name_km
    product.description_en = description_en
    product.description_km = description_km
    product.category_id = category_id
    product.tags = tags
    product.featured = featured
    product.active = active

    if image and image.filename:
        # Delete old image if exists
        if product.image:
            old_path = os.path.join(UPLOAD_DIR, product.image)
            if os.path.exists(old_path):
                os.remove(old_path)
        product.image = save_upload(image)

    db.commit()
    db.refresh(product)
    return serialize_product(product)


@app.delete("/api/admin/products/{product_id}")
def admin_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    # Soft delete
    product.active = False
    db.commit()
    return {"status": "deleted"}


# ─────────────────────────────────────────
# ADMIN QUOTE ROUTES
# ─────────────────────────────────────────

@app.get("/api/admin/quotes")
def admin_get_quotes(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    quotes = db.query(QuoteRequest).order_by(QuoteRequest.created_at.desc()).all()
    return quotes


@app.put("/api/admin/quotes/{quote_id}/read")
def admin_mark_quote_read(
    quote_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    quote = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Not found")
    quote.read = True
    db.commit()
    return {"status": "updated"}


# ─────────────────────────────────────────
# ADMIN CATEGORY ROUTES
# ─────────────────────────────────────────

@app.get("/api/admin/categories")
def admin_get_categories(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_admin)
):
    return db.query(Category).order_by(Category.order).all()


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def save_upload(file: UploadFile) -> str:
    import uuid
    ext = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return filename


def serialize_product(p: Product) -> dict:
    return {
        "id": p.id,
        "name_en": p.name_en,
        "name_km": p.name_km,
        "description_en": p.description_en,
        "description_km": p.description_km,
        "category_id": p.category_id,
        "category": {"id": p.category.id, "name_en": p.category.name_en, "name_km": p.category.name_km, "slug": p.category.slug} if p.category else None,
        "image": p.image,
        "image_url": f"/api/uploads/{p.image}" if p.image else None,
        "tags": p.tags.split(",") if p.tags else [],
        "featured": p.featured,
        "active": p.active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
