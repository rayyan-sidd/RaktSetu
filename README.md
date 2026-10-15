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
- [ ] **Step 1B: Backend Scaffolding & Healthcheck** (FastAPI app, Pydantic models, tests)
- [ ] **Step 1C: Frontend Scaffolding** (Vite + React + TypeScript + Tailwind CSS)
- [ ] **Step 2: Core Data Models & Medical Compatibility Engine** (ABO/Rh logic, unit tests)
- [ ] **Step 3: Blood Bank Discovery & Freshness Engine** (Delhi & Lucknow seed data, TinyFish client)
- [ ] **Step 4: Voluntary Donor Matching & Privacy Relay** (Consent flow, Telegram bot dispatch)
- [ ] **Step 5: AI Triage Agent** (Gemma 4 integration + deterministic fallback)
- [ ] **Step 6: Unified UI Dashboard** (Emergency search, live freshness indicators, donor portal)
- [ ] **Step 7: Verification, Documentation & Open-Source Release**

---

## License

This project is licensed under the [MIT License](LICENSE).
