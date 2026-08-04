# 🌀 HVAC Lead Recovery Backend

**Turn missed calls into booked jobs.**

This is the backend system powering an AI voice receptionist platform for HVAC companies. When a customer calls and nobody picks up — or an AI assistant handles the call — this backend captures the lead, stores it, and makes it instantly available on a live dashboard, so no job is ever lost to a missed call again.

Built as a **multi-tenant SaaS**: any number of HVAC companies can sign up, each with fully isolated data, their own AI voice assistant integration, and their own dashboard.

---

## ✨ What it does

- 🎙️ **Captures leads from AI voice calls** — integrates with [Vapi](https://vapi.ai) to receive structured lead data the moment a call ends
- 🏢 **Multi-tenant by design** — every company gets its own account, its own webhook, and its own isolated leads
- 📊 **Live dashboard data** — serves call stats, revenue recovered, and job status in real time
- 🔐 **Secure authentication** — JWT-based auth with hashed passwords (bcrypt)
- ⚙️ **Configurable business settings** — each company controls its own greeting script, working hours, and contact routing
- 🛠️ **Admin visibility** — a protected endpoint lets the platform owner see every company and its webhook URL

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| API Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Database ORM | [SQLAlchemy](https://www.sqlalchemy.org/) |
| Auth | JWT (`python-jose`) + `passlib[bcrypt]` |
| Server | Uvicorn |
| Voice AI | [Vapi](https://vapi.ai) |
| Telephony (optional) | Twilio |
| Hosting | [Railway](https://railway.app) |

---

## 🗂️ Project Structure

```
backend/
├── main.py            # FastAPI app, routes, CORS, router registration
├── auth.py            # Password hashing, JWT creation/verification, current-user dependency
├── model.py            # SQLAlchemy models: Company, Lead, BusinessSettings
├── schemas.py          # Pydantic request/response schemas
├── database.py         # DB engine + session setup
├── twilio_router.py    # Twilio-related endpoints
├── voice_session.py    # Voice session handling
├── ai_agents.py         # AI response / lead extraction logic
├── requirements.txt
└── .env                 # Local environment variables (not committed)
```

---

## 🔑 Core Concepts

### Multi-tenancy
Every signed-up company is a row in the `companies` table with a unique `api_key`. All leads and settings are scoped to `company_id`, so one company's data is never visible to another.

### The Webhook Pattern
Instead of requiring login credentials inside Vapi (which can't authenticate like a browser), each company gets a **unique, unguessable webhook URL**:

```
POST /vapi/create-lead/{api_key}
```

The `api_key` in the URL itself identifies which company the lead belongs to — no separate auth needed for Vapi to call it.

---

## 🚀 Getting Started (Local Development)

### 1. Clone and set up a virtual environment
```bash
git clone <this-repo>
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
Create a `.env` file:
```env
JWT_SECRET=your-long-random-secret
ADMIN_SECRET=your-admin-panel-secret
GEMINI_API_KEY=your-key-if-using-ai_agents
```

### 4. Run the server
```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs (Swagger UI).

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | — | Health check |
| `POST` | `/signup` | — | Create a new company account |
| `POST` | `/login` | — | Log in, returns JWT |
| `GET` | `/me` | 🔒 JWT | Get current company info + webhook URL |
| `GET` | `/leads` | 🔒 JWT | List this company's leads |
| `GET` | `/dashboard` | 🔒 JWT | Aggregate stats (revenue, calls, jobs booked) |
| `GET` | `/settings` | 🔒 JWT | Get business settings |
| `POST` | `/settings` | 🔒 JWT | Update business settings |
| `POST` | `/vapi/create-lead/{api_key}` | 🔑 API key in URL | Webhook — Vapi posts lead data here |
| `GET` | `/admin/companies?secret=...` | 🔑 Admin secret | List all companies (owner-only) |

---

## ☁️ Deployment (Railway)

1. Push this repo to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Set the start command:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. Add environment variables in Railway's **Variables** tab:
   - `JWT_SECRET`
   - `ADMIN_SECRET`
   - any other keys your integrations need
5. Generate a public domain under **Settings → Networking**

---

## 🖥️ Frontend

This backend pairs with a Next.js frontend (separate repo) that provides:
- Signup / Login
- A 3-step onboarding wizard (business info → webhook setup → confirmation)
- A live dashboard, calls list, and settings page per company
- An owner-only `/admin` panel to view all signed-up companies

---

## 🛣️ Roadmap Ideas

- [ ] Automatic Vapi assistant provisioning on signup (no manual dashboard setup)
- [ ] Twilio number auto-assignment per company
- [ ] Stripe billing integration
- [ ] Jobber / Housecall Pro / ServiceTitan sync
- [ ] SMS confirmation to customers after a booked call

---

## 📄 License

Private/proprietary — not for redistribution.
