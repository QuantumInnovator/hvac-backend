# test_lead_save.py
#
# Tests lead extraction + database saving WITHOUT needing a real call.
# Uses a fake sample conversation to simulate what a finished call
# would look like.

from ai_agents import extract_lead_info
from database import SessionLocal
from model import Lead


# Fake conversation, as if a real call already happened
sample_conversation = [
    {"role": "user", "text": "Hello, my name is Ahmed."},
    {"role": "model", "text": "Hi Ahmed! Thanks for calling. What's the best "
                               "phone number to reach you at, and what HVAC "
                               "issue are you having?"},
    {"role": "user", "text": "My number is 0300-1234567. My AC is not "
                              "cooling properly, it's been like this for "
                              "two days."},
    {"role": "model", "text": "I'm sorry to hear that. What's your address "
                               "so we can send a technician?"},
    {"role": "user", "text": "123 Main Street, Karachi. Can someone come "
                              "tomorrow at 3pm?"},
    {"role": "model", "text": "Yes, we can schedule that. Thanks Ahmed, "
                               "we'll see you tomorrow at 3pm."},
]


def main():

    print("🔍 Extracting lead info from sample conversation...")

    lead_data = extract_lead_info(sample_conversation)

    if not lead_data:
        print("❌ Extraction failed - check the error above.")
        return

    print("✅ Extracted data:")
    print(lead_data)

    db = SessionLocal()

    try:

        new_lead = Lead(
            customer_name=lead_data.get("customer_name") or "Unknown",
            phone_number=lead_data.get("phone_number") or "Unknown",
            address=lead_data.get("address"),
            issue=lead_data.get("issue") or "Not specified",
            urgency=lead_data.get("urgency") or "normal",
            status="new",
            appointment_time=lead_data.get("appointment_time"),
            estimated_value=0,
            notes=lead_data.get("notes"),
        )

        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)

        print(f"💾 Lead saved successfully! id={new_lead.id}")
        print("   Now check http://127.0.0.1:8000/leads in your browser.")

    except Exception as e:
        print("❌ Database save error:", e)

    finally:
        db.close()


if __name__ == "__main__":
    main()