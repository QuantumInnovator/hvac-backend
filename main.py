from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import os
from database import Base, engine
from model import Lead, Company, BusinessSettings

from twilio_router import router as twilio_router
from voice_session import router as voice_router

from auth import (
    hash_password, verify_password, create_access_token,
    get_db, get_current_company,
)


app = FastAPI()
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change-this-admin-secret")

# Create database tables (only creates tables that don't exist yet —
# does NOT add new columns to existing tables)
Base.metadata.create_all(bind=engine)

# =============================================================================
# NEW — lightweight auto-migration. Base.metadata.create_all() above does not
# add new columns to tables that already exist, so if the 'email' column is
# missing on the existing 'leads' table (created before this change), add it
# here automatically on startup. Safe to leave in permanently — it just does
# nothing once the column already exists.
# =============================================================================
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE leads ADD COLUMN email VARCHAR"))
        conn.commit()
    except Exception:
        pass  # column already exists — nothing to do

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(twilio_router)
app.include_router(voice_router)


@app.get("/")
def home():
    return {"message": "Backend Running 🚀"}


# === Pydantic schemas ===

class CompanySignup(BaseModel):
    name: str
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class SettingsUpdate(BaseModel):
    company_name: str
    owner_name: str
    business_phone: str
    forward_number: str
    business_email: str
    working_hours: str
    greeting_script: str


# === SIGNUP ===

@app.post("/signup", response_model=Token)
def signup(data: CompanySignup, db: Session = Depends(get_db)):
    existing = db.query(Company).filter(Company.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    company = Company(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    settings = BusinessSettings(company_id=company.id, company_name=data.name)
    db.add(settings)
    db.commit()

    token = create_access_token({"company_id": company.id})
    return {"access_token": token, "token_type": "bearer"}


# === LOGIN ===

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.email == form_data.username).first()

    if not company or not verify_password(form_data.password, company.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({"company_id": company.id})
    return {"access_token": token, "token_type": "bearer"}


# === Get the logged-in company's own info ===

@app.get("/me")
def get_me(current_company: Company = Depends(get_current_company)):
    return {
        "id": current_company.id,
        "name": current_company.name,
        "email": current_company.email,
        "api_key": current_company.api_key,
        "webhook_url": f"/vapi/create-lead/{current_company.api_key}",
    }


# === COMPANY-SCOPED LEADS ===

@app.get("/leads")
def get_leads(current_company: Company = Depends(get_current_company), db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.company_id == current_company.id).all()
    return [
        {
            "id": lead.id,
            "customer_name": lead.customer_name,
            "phone_number": lead.phone_number,
            "email": lead.email,
            "issue": lead.issue,
            "status": lead.status,
            "appointment_time": lead.appointment_time,
            "estimated_value": lead.estimated_value,
        }
        for lead in leads
    ]


@app.get("/dashboard")
def dashboard(current_company: Company = Depends(get_current_company), db: Session = Depends(get_db)):
    q = db.query(Lead).filter(Lead.company_id == current_company.id)

    total_calls = q.count()
    booked_jobs = q.filter(Lead.status == "booked").count()
    callbacks = q.filter(Lead.status == "callback").count()
    revenue = (
        db.query(func.sum(Lead.estimated_value))
        .filter(Lead.company_id == current_company.id)
        .scalar()
        or 0
    )

    return {
        "revenue": revenue,
        "answered_calls": total_calls,
        "jobs_booked": booked_jobs,
        "callbacks": callbacks,
    }


# === COMPANY-SCOPED SETTINGS ===

@app.get("/settings")
def get_settings(current_company: Company = Depends(get_current_company), db: Session = Depends(get_db)):
    settings = db.query(BusinessSettings).filter(
        BusinessSettings.company_id == current_company.id
    ).first()

    if not settings:
        settings = BusinessSettings(company_id=current_company.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "company_name": settings.company_name,
        "owner_name": settings.owner_name,
        "business_phone": settings.business_phone,
        "forward_number": settings.forward_number,
        "business_email": settings.business_email,
        "working_hours": settings.working_hours,
        "greeting_script": settings.greeting_script,
    }


@app.post("/settings")
def update_settings(
    data: SettingsUpdate,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    settings = db.query(BusinessSettings).filter(
        BusinessSettings.company_id == current_company.id
    ).first()

    if not settings:
        settings = BusinessSettings(company_id=current_company.id)
        db.add(settings)

    for field, value in data.dict().items():
        setattr(settings, field, value)

    db.commit()
    return {"message": "Settings saved successfully"}


# === PUBLIC WEBHOOK for Vapi (no login needed, api_key identifies the company) ===

@app.post("/vapi/create-lead/{api_key}")
async def vapi_create_lead(api_key: str, request: Request, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.api_key == api_key).first()
    if not company:
        raise HTTPException(status_code=404, detail="Invalid webhook URL")

    body = await request.json()
    tool_call = body["message"]["toolCalls"][0]
    args = tool_call["function"]["arguments"]

    new_lead = Lead(
        company_id=company.id,
        customer_name=args.get("customer_name"),
        phone_number=args.get("phone_number"),
        email=args.get("email"),
        issue=args.get("issue"),
        status=args.get("status", "new"),
        appointment_time=args.get("appointment_time"),
        estimated_value=args.get("estimated_value", 0),
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    return {
        "results": [
            {
                "toolCallId": tool_call["id"],
                "result": f"Lead saved successfully with id {new_lead.id}",
            }
        ]
    }


@app.get("/admin/companies")
def list_all_companies(secret: str, db: Session = Depends(get_db)):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    companies = db.query(Company).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "webhook_url": f"https://hvac-backend-production-c861.up.railway.app/vapi/create-lead/{c.api_key}",
            "created_at": c.created_at,
        }
        for c in companies
    ]