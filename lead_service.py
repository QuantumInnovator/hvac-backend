from model import Lead

def save_lead(db, data):
    lead = Lead(**data)

    db.add(lead)

    db.commit()

    db.refresh(lead)

    return lead