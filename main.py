from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from fastapi import Request

from database import engine, Base, SessionLocal
from model import Lead
import model

from schemas import LeadCreate

from twilio_router import router as twilio_router
from voice_session import router as voice_router


app = FastAPI()

# Create database tables
Base.metadata.create_all(bind=engine)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(twilio_router)
app.include_router(voice_router)


@app.get("/")
def home():
    return {
        "message": "Backend Running 🚀"
    }


@app.get("/dashboard")
def dashboard():

    db = SessionLocal()

    total_calls = db.query(Lead).count()

    booked_jobs = db.query(
        Lead
    ).filter(
        Lead.status == "booked"
    ).count()

    callbacks = db.query(
        Lead
    ).filter(
        Lead.status == "callback"
    ).count()

    revenue = db.query(
        func.sum(Lead.estimated_value)
    ).scalar() or 0

    db.close()

    return {
        "revenue": revenue,
        "answered_calls": total_calls,
        "jobs_booked": booked_jobs,
        "callbacks": callbacks
    }


@app.post("/leads")
def create_lead(lead: LeadCreate):

    db = SessionLocal()

    new_lead = Lead(
        customer_name=lead.customer_name,
        phone_number=lead.phone_number,
        issue=lead.issue,
        status=lead.status,
        appointment_time=lead.appointment_time,
        estimated_value=lead.estimated_value
    )

    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    db.close()

    return {
        "message": "Lead saved successfully",
        "lead_id": new_lead.id
    }


@app.get("/leads")
def get_leads():

    db = SessionLocal()

    leads = db.query(Lead).all()

    db.close()

    return [
        {
            "id": lead.id,
            "customer_name": lead.customer_name,
            "phone_number": lead.phone_number,
            "issue": lead.issue,
            "status": lead.status,
            "appointment_time": lead.appointment_time,
            "estimated_value": lead.estimated_value,
        }
        for lead in leads
    ]

@app.post("/vapi/create-lead")
async def vapi_create_lead(request: Request):
    body = await request.json()
    print("VAPI SE AAYA DATA:", body)  # debug ke liye

    tool_call = body["message"]["toolCalls"][0]
    args = tool_call["function"]["arguments"]

    db = SessionLocal()
    new_lead = Lead(
        customer_name=args.get("customer_name"),
        phone_number=args.get("phone_number"),
        issue=args.get("issue"),
        status=args.get("status", "new"),
        appointment_time=args.get("appointment_time"),
        estimated_value=args.get("estimated_value"),
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    db.close()

    return {
        "results": [
            {
                "toolCallId": tool_call["id"],
                "result": f"Lead saved successfully with id {new_lead.id}"
            }
        ]
    }