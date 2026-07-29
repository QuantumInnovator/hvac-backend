from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    customer_name = Column(String, nullable=False)

    phone_number = Column(String, nullable=False)

    address = Column(String, nullable=True)

    issue = Column(String, nullable=False)

    urgency = Column(String, default="normal")

    status = Column(String, default="new")

    appointment_time = Column(String, nullable=True)

    estimated_value = Column(Integer, default=0)

    notes = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)