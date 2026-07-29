from pydantic import BaseModel


class LeadCreate(BaseModel):

    customer_name: str

    phone_number: str

    address: str | None = None

    issue: str

    urgency: str = "normal"

    status: str = "new"

    appointment_time: str | None = None

    estimated_value: int = 0

    notes: str | None = None