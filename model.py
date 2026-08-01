# === Add this to model.py ===
# This replaces the single-tenant BusinessSettings idea with a proper
# multi-tenant structure: every Lead and every Settings row belongs to a Company.

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # This is the secret that goes in the company's Vapi webhook URL.
    # It lets Vapi send leads to the right company WITHOUT needing a login.
    api_key = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex)

    created_at = Column(DateTime, default=datetime.utcnow)

    leads = relationship("Lead", back_populates="company")
    settings = relationship("BusinessSettings", back_populates="company", uselist=False)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    customer_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    issue = Column(String, nullable=True)
    urgency = Column(String, default="normal")
    status = Column(String, default="new")
    appointment_time = Column(String, nullable=True)
    estimated_value = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="leads")


class BusinessSettings(Base):
    __tablename__ = "business_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True)

    company_name = Column(String, default="")
    owner_name = Column(String, default="")
    business_phone = Column(String, default="")
    forward_number = Column(String, default="")
    business_email = Column(String, default="")
    working_hours = Column(String, default="9:00 AM – 6:00 PM")
    greeting_script = Column(
        Text,
        default="Hello! Thank you for calling. How can I help you today?",
    )

    company = relationship("Company", back_populates="settings")