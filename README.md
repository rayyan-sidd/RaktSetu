# RaktSetu (रक्तसेतु)

> **"Bridging the gap between need and help."**

RaktSetu is an open-source, AI-powered blood discovery and voluntary donor coordination platform developed for a hackathon. The platform addresses critical delays during medical emergencies by aggregating reported blood bank stock with explicit source attribution, while coordinating consented voluntary donors through a privacy-preserving and human-moderated workflow.

---

## ⚠️ Important Medical & Ethical Disclaimers

> [!CAUTION]
> **RaktSetu is a technical prototype and an informational coordination platform. It is NOT a certified medical dispatch system or emergency medical service.**

1. **Not a Medical Service**: RaktSetu does not provide medical advice, diagnosis, or treatment. It does not replace emergency medical response services or official hospital blood transfusion protocols.
2. **Demo & Reported Data**: Any sample or synthetic records are strictly labeled as **Demo Data**. Unverified or scraped stock reports must never be misconstrued as physically guaranteed blood units.
3. **Source Attribution & Freshness**: Every reported stock item must clearly display its data source (e.g., eRaktKosh, direct portal, or demo registry), retrieval timestamp, and verification status (`Reported (Unverified)` vs `Hospital Confirmed`).
4. **Mandatory Verification**: Patients, families, and caregivers must directly contact and verify actual blood unit availability and cross-matching with the respective blood bank or treating medical team before traveling.
5. **Donor Privacy & Voluntary Consent**: Donor participation is completely voluntary. Private donor contact information is never publicly published, exposed, or sold. Notifications are routed through privacy-conscious relay channels (such as authenticated Telegram bots) with explicit opt-in consent and human moderation.
6. **Backend-Validated AI**: AI agent outputs (e.g., query triage or location extraction) are advisory only, strictly validated by deterministic backend code, and must never independently assess medical eligibility or donor suitability.

---

## Target Scope

- **Initial Cities**: Delhi (National Capital Region) and Lucknow (Uttar Pradesh).
- **Primary Beneficiaries**: Patients, families, emergency caregivers, voluntary blood donors, and blood bank coordinators.

---

## Planned Features

- **Blood Bank Discovery**: Proximity-based search for licensed blood banks, blood storage centers, and transfusion facilities in Delhi and Lucknow. *(Planned)*
- **Source-Attributed Inventory**: Transparent stock reporting displaying data origins, last-updated timestamps, and clear verification badges. *(Planned)*
- **Voluntary Donor Coordination**: ABO/Rh-compatible matching for urgent requests connecting to opted-in voluntary donors. *(Planned)*
- **Privacy-Preserving Contact Relay**: Consent-driven alert dispatch via Telegram Bot API without exposing donor phone numbers. *(Planned)*
- **Human Moderation Queue**: Administrative review checkpoint for high-urgency or sensitive blood requests before donor notification broadcasts. *(Planned)*
- **Intelligent Triage Agent**: Reusable open-source AI assistant utilizing Gemma 4 (with deterministic rule-based fallbacks) for structured emergency query parsing. *(Planned)*
- **Modular Data Connectors**: Configurable TinyFish data retrieval worker designed to operate strictly within prototype credit limits ($35 budget cap). *(Planned)*

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Web Frontend (Vite + React)     |
                      |   TypeScript + Tailwind CSS + Lucide  |
                      +-------------------+-------------------+
                                          | REST API
                                          v
                      +---------------------------------------+
                      |        FastAPI Backend (Python)       |
                      |  - ABO/Rh Medical Compatibility Engine |
                      |  - Source & Freshness Attribution     |
                      |  - Donor Privacy & Relay Controller   |
                      |  - Human Moderation Gatekeeper        |
                      +-----+-------------------+-------+-----+
                            |                   |       |
            +---------------+                   |       +---------------+
            v                                   v                       v
+-----------------------+           +-----------------------+   +-------------------+
|     SQLite Local DB   |           |  AI Agent (Gemma 4 /  |   | Telegram Bot API  |
| (Dev/Prototype Stage) |           |  Rule-Based Fallback) |   | (Donor Alerts &   |
+-----------------------+           +-----------------------+   |  Coordination)    |
                                                |               +-------------------+
                                                v
                                    +-----------------------+
                                    |  Modular Data Client  |
                                    | (TinyFish Connector)  |
                                    +-----------------------+
```

### Technology Decisions

- **Frontend**: React 18/19, TypeScript, Vite, Tailwind CSS.
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLModel / SQLAlchemy.
- **Database**: SQLite for local-first zero-cost development; modular design allows seamless migration to PostgreSQL.
- **Messaging**: Telegram Bot API for donor notifications and moderator review.
- **AI Agent**: Gemma 4 (local inference or API) with a 100% deterministic rule-based fallback parser.
- **Data Retrieval**: Modular TinyFish client with caching, strict rate-limiting, and budget guardrails.

---

## Zero-Cost & Local-First Philosophy

RaktSetu is architected to be developed, tested, and demonstrated entirely on a local development workstation without mandatory paid cloud subscriptions, proprietary APIs, or database hosting costs.

---

## Project Status & Development Roadmap

- [x] **Step 1A: Repository Foundation** (Git, .gitignore, README, MIT License, Skeleton)
- [x] **Step 1B: Backend Scaffolding & Healthcheck** (FastAPI app, Pydantic schemas, healthcheck endpoint, automated tests)
- [x] **Step 1C: Frontend Scaffolding** (Vite + React + TypeScript + Tailwind CSS v4)
- [x] **Step 2A: Blood Bank Discovery API** (SQLAlchemy 2.x, SQLite, idempotent synthetic seeder, discovery endpoint)
- [ ] **Step 2B: Medical Compatibility Engine** (Deterministic ABO/Rh logic, compatibility unit tests)
- [ ] **Step 3: Blood Bank Freshness & External Connectors** (Source attribution, TinyFish worker client)
- [ ] **Step 4: Voluntary Donor Matching & Privacy Relay** (Consent flow, Telegram bot dispatch)
- [ ] **Step 5: AI Triage Agent** (Gemma 4 integration + deterministic fallback)
- [ ] **Step 6: Unified UI Dashboard** (Emergency search, live freshness indicators, donor portal)
- [ ] **Step 7: Verification, Documentation & Open-Source Release**

---

## Local Backend Setup & Testing

### 1. Environment & Dependencies Setup
Create the virtual environment and install backend dependencies:
```bash
# Create virtual environment
python -m venv .venv

# Install dependencies (Windows PowerShell)
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### 2. Seed Synthetic Demonstration Database
Populate the local SQLite database (`data/raktsetu.db`) with fictional demo records:
```bash
.\.venv\Scripts\python.exe -m backend.app.seed_demo
```
> [!NOTE]
> **Synthetic Dataset Notice:** All demo records are strictly fictional demonstration data covering Delhi and Lucknow. Stock numbers are illustrative snapshot records, not real-time hospital inventory or a guarantee of physical blood availability.
> The seeding script is **idempotent**: running it again will safely skip without overwriting or duplicating records.

### 3. Run Automated Tests
```bash
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```

### 4. Start Local Development Server
```bash
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative Redoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 5. Blood Bank Discovery API Examples

Discovery queries return an envelope with `items`, `count` (number of matching blood banks), and `data_notice`:

- **All blood banks (Delhi & Lucknow)**:
  ```http
  GET /api/blood-banks
  ```
- **Filter by city**:
  ```http
  GET /api/blood-banks?city=Delhi
  GET /api/blood-banks?city=Lucknow
  ```
- **Filter by blood group**:
  ```http
  GET /api/blood-banks?blood_group=O-
  GET /api/blood-banks?blood_group=A%2B
  ```
- **Combined city and blood group query**:
  ```http
  GET /api/blood-banks?city=Delhi&blood_group=O-
  ```

Example JSON Response:
```json
{
  "items": [
    {
      "id": 1,
      "name": "Demo Central Transfusion Facility",
      "city": "Delhi",
      "locality": "Connaught Place (Central Delhi)",
      "stock_reports": [
        {
          "id": 8,
          "blood_bank_id": 1,
          "blood_group": "O-",
          "units_reported": 5,
          "source_name": "Synthetic demo dataset",
          "data_timestamp": "2026-10-15T12:00:00Z",
          "verification_status": "demo"
        }
      ]
    }
  ],
  "count": 1,
  "data_notice": "All records are synthetic demonstration data and do not reflect real-time hospital inventory or guaranteed physical blood availability."
}
```


---

## Local Frontend Setup & Development

### 1. Installation
Navigate to the `frontend/` directory and install npm packages:
```bash
cd frontend
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
The local development server runs at `http://localhost:5173/`.

### 3. Build for Production
```bash
npm run build
```
Production assets are generated in `frontend/dist/`.

---

## License

This project is licensed under the [MIT License](LICENSE).
