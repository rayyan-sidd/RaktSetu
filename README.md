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

## Current Implementation & Core Features

### ✅ Implemented
- **Interactive Blood Bank Discovery Console**: Responsive React 19 + TypeScript interface styled with Tailwind CSS, Lucide icons, and a custom 3D Canvas visual scene. Supports instant filtering by City (`Delhi`, `Lucknow`, `All Cities`) and ABO/Rh Blood Group (`A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`, `All`).
- **Real Data by Default**: Discovery results prioritize and display real, source-reported facilities by default. Synthetic demonstration records are excluded from default results.
- **Controlled Demo Data Toggle**: An "Include demo data" toggle allows users to optionally append demo data when needed. When enabled, real records always precede demo records, and the displayed facility counter synchronizes strictly with the visible list.
- **Source Attribution & Freshness Intelligence**: Clear visual provenance badges (`e-RaktKosh Feed` vs `Synthetic Demo`), explicit distinction between hospital update time and RaktSetu retrieval time, automated stale record warnings (>24h), and live badge unverified disclaimer notices.
- **Fail-Safe e-RaktKosh Ingestion Pipeline**: Modular CLI pipeline (`python -m backend.app.ingest_eraktkosh`) featuring:
  - HTML table extraction and normalization for Ministry of Health and Family Welfare (MoHFW) e-RaktKosh portal responses.
  - Strict PII/contact stripping and redaction across all phone and address formats.
  - IST portal timestamp parsing to standardized UTC ISO 8601 strings.
  - Deterministic composite facility slugging eliminating identity collisions across similarly named hospitals.
  - Fail-safe transactional reconciliation: omitted facilities never trigger accidental inventory deletion; explicit unavailable observations are strictly scoped; zero-quantity reports are never artificially invented.
  - Dry-run verification mode by default (`--apply` required for database writes).
- **Guarded Versioned Schema Migration (v2)**: Component-aware stock tracking (`Whole Blood`, `Packed Red Blood Cells`, etc.), source tracking, isolation, and backward compatibility.
- **Live Imported Dataset**: Successfully ingested and verified live Whole Blood inventory for Delhi and Lucknow (155 external facilities, 46 stock reports).

### ⏳ Upcoming Roadmap Features
- **Medical Compatibility Engine (Step 4)**: Deterministic ABO/Rh red cell and plasma compatibility logic with unit-tested cross-match validation.
- **Voluntary Donor Coordination & Privacy Relay (Step 5)**: Consent-driven alert dispatch via Telegram Bot API without exposing donor contact details.
- **Human Moderation Queue**: Administrative review checkpoint for urgent or sensitive requests prior to donor notification broadcasts.
- **Intelligent Triage Agent (Step 6)**: Gemma 4 integration with a 100% deterministic rule-based fallback parser for emergency query understanding.

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
                      |  - Blood Bank Discovery Engine        |
                      |  - Source & Freshness Attribution     |
                      |  - ABO/Rh Medical Compatibility       |
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
            ^                                   |               +-------------------+
            | Ingestion CLI                     v
+-----------------------+           +-----------------------+
|  e-RaktKosh Pipeline  |<----------| MoHFW External Portal |
| (Parser + Normalizer) |           |   (Public Stock Feed) |
+-----------------------+           +-----------------------+
```

### Technology Decisions

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Three.js / Canvas 3D.
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite.
- **Database**: SQLite for local-first zero-cost development; versioned schema migrations enable modular evolution.
- **Messaging**: Telegram Bot API for donor notifications and moderator review *(Planned)*.
- **AI Agent**: Gemma 4 (local inference or API) with a 100% deterministic rule-based fallback parser *(Planned)*.
- **Data Ingestion**: Fail-safe e-RaktKosh client with rate-limiting, strict HTML sanitizer, and non-destructive reconciliation.

---

## Zero-Cost & Local-First Philosophy

RaktSetu is architected to be developed, tested, and demonstrated entirely on a local development workstation without mandatory paid cloud subscriptions, proprietary APIs, or database hosting costs.

---

## Project Status & Development Roadmap

- [x] **Step 1A: Repository Foundation** (Git, .gitignore, README, MIT License, Project Architecture)
- [x] **Step 1B: Backend Scaffolding & Healthcheck** (FastAPI app, Pydantic schemas, health endpoint, automated pytest suite)
- [x] **Step 1C: Frontend Scaffolding & Visual Canvas** (Vite + React 19 + TypeScript + Tailwind CSS, 3D Droplet Scene)
- [x] **Step 2A: Blood Bank Discovery API** (SQLAlchemy 2.x, SQLite, idempotent synthetic seeder, discovery endpoint)
- [x] **Step 3: e-RaktKosh Data Ingestion Pipeline & Real Data Prioritization**
  - [x] **Step 3A–3F: Source Ingestion Engine**: e-RaktKosh client, HTML table parser, contact redaction, IST->UTC timestamp conversion.
  - [x] **Step 3G–3H: Schema Migration (v2)**: Guarded migration with component-aware schema, source tracking, and isolation.
  - [x] **Step 3I: Deterministic Facility Identity**: Slug generator and composite key resolution preventing hospital collisions.
  - [x] **Step 3J: Mixed-Source Discovery**: API envelope & frontend types supporting both external feeds and demo datasets.
  - [x] **Step 3K–3M: Safety Audits & Reconciliation Hardening**: Non-destructive reconciliation, scoped unavailability, and multi-city dry runs.
  - [x] **Step 3N: First Controlled Import**: Successful import of Delhi & Lucknow Whole Blood inventory (155 facilities, 46 stock reports).
  - [x] **Step 3O–3P: Real Data by Default**: Frontend discovery displays real e-RaktKosh data by default, with "Include demo data" toggle, stale warnings (>24h), and synchronized visible counts.
- [ ] **Step 4: Medical Compatibility Engine** (Deterministic ABO/Rh logic, compatibility unit tests)
- [ ] **Step 5: Voluntary Donor Matching & Privacy Relay** (Opt-in consent flow, Telegram bot dispatch)
- [ ] **Step 6: AI Triage Agent** (Gemma 4 integration + deterministic rule-based fallback)
- [ ] **Step 7: Unified Emergency Coordination Dashboard & Release**

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

### 3. e-RaktKosh External Data Ingestion CLI
Run read-only dry runs or apply live imports of e-RaktKosh Whole Blood data:
```bash
# Safe dry-run for Delhi (no database changes)
.\.venv\Scripts\python.exe -m backend.app.ingest_eraktkosh --city Delhi

# Safe dry-run for Lucknow
.\.venv\Scripts\python.exe -m backend.app.ingest_eraktkosh --city Lucknow

# Safe dry-run across all target cities
.\.venv\Scripts\python.exe -m backend.app.ingest_eraktkosh --city all

# Controlled import applying changes to local SQLite database
.\.venv\Scripts\python.exe -m backend.app.ingest_eraktkosh --city all --apply
```
> [!TIP]
> Ingestion defaults to **dry-run mode** unless `--apply` is explicitly passed. Reconciliation is strictly fail-safe: facilities missing from a source snapshot are never removed from the database.

### 4. Run Automated Backend Tests
```bash
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```
All 184 tests pass across parser, normalizer, identity slugging, ingestion, migration, safety invariants, and discovery endpoints.

### 5. Start Local Development Server
```bash
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative Redoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 6. Blood Bank Discovery API Examples

Discovery queries return an envelope with `items`, `count` (number of matching blood banks), `data_notice`, and snapshot `data_timestamp`:

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
  GET /api/blood-banks?blood_group=O%2B
  ```
- **Combined city and blood group query**:
  ```http
  GET /api/blood-banks?city=Delhi&blood_group=O%2B
  ```

Example JSON Response (Mixed / Source-Reported):
```json
{
  "items": [
    {
      "id": 10,
      "name": "AIIMS Main Blood Bank",
      "city": "Delhi",
      "locality": "Ansari Nagar",
      "category": "Government",
      "source_name": "e-RaktKosh (MoHFW)",
      "source_type": "external_source",
      "source_facility_id": "eraktkosh:delhi:aiims-main-blood-bank",
      "stock_reports": [
        {
          "id": 142,
          "blood_bank_id": 10,
          "blood_group": "O+",
          "blood_component": "Whole Blood",
          "units_reported": 18,
          "source_name": "e-RaktKosh (MoHFW)",
          "verification_status": "reported_unverified",
          "source_reported_timestamp": "2026-10-16T05:30:00Z",
          "retrieval_timestamp": "2026-10-16T06:00:00Z",
          "data_timestamp": "2026-10-16T06:00:00Z"
        }
      ]
    }
  ],
  "count": 1,
  "data_notice": "Official source-reported e-RaktKosh snapshots (MoHFW). External inventory is source-reported, may be stale, and does not guarantee real-time physical blood availability. Always verify directly with the blood bank.",
  "data_timestamp": "2026-10-16T06:00:00Z"
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

### 2. Run Automated Frontend Tests
Execute the native unit test suite (25 tests covering URL building, response contracts, freshness/stale detection, and demo data filtering):
```bash
npm test
```

### 3. Start Development Server
```bash
npm run dev
```
The local development server runs at [http://localhost:5173/](http://localhost:5173/) with automatic proxying to the FastAPI backend (`http://127.0.0.1:8000`).

### 4. Build for Production
```bash
npm run build
```
Production assets are compiled and validated with TypeScript in `frontend/dist/`.

---

## License

This project is licensed under the [MIT License](LICENSE).
