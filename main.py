import os
import hashlib
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from database import db, create_document, get_documents
from schemas import UserAuth, BlogPost, ContactMessage

app = FastAPI(title="SaaS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "SaaS Backend Running"}


# ----- Auth (simple demo: register + login storing hash) -----
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    message: str
    email: EmailStr
    name: Optional[str] = None


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@app.post("/api/auth/register", response_model=AuthResponse)
async def register_user(payload: RegisterRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    email = payload.email.lower()
    existing = list(db["userauth"].find({"email": email}))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = UserAuth(name=payload.name, email=email, password_hash=_hash_password(payload.password))
    _id = create_document("userauth", user_doc)
    return {"message": "Registered successfully", "email": email, "name": payload.name}


@app.post("/api/auth/login", response_model=AuthResponse)
async def login_user(payload: LoginRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    email = payload.email.lower()
    user = db["userauth"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("password_hash") != _hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful", "email": email, "name": user.get("name")}


# ----- Blog -----
class BlogCreateRequest(BaseModel):
    title: str
    slug: str
    excerpt: str
    content: str
    tags: List[str] = []


@app.post("/api/blog", response_model=dict)
async def create_blog(payload: BlogCreateRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    exists = db["blogpost"].find_one({"slug": payload.slug})
    if exists:
        raise HTTPException(status_code=400, detail="Slug already exists")

    post = BlogPost(**payload.model_dump())
    _id = create_document("blogpost", post)
    return {"message": "Post created", "id": _id}


@app.get("/api/blog", response_model=List[dict])
async def list_blogs(limit: int = 10):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = get_documents("blogpost", {}, limit)
    # Convert ObjectId
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
    return docs


@app.get("/api/blog/{slug}")
async def get_blog(slug: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    d = db["blogpost"].find_one({"slug": slug})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    d["id"] = str(d.pop("_id", ""))
    return d


# ----- Contact -----
class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str
    subject: Optional[str] = None


@app.post("/api/contact")
async def submit_contact(payload: ContactRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    msg = ContactMessage(**payload.model_dump())
    _id = create_document("contactmessage", msg)
    return {"message": "Message received", "id": _id}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db as _db
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = _db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
