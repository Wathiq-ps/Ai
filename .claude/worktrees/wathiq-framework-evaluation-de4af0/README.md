# Wathiq (وثيق)

**منصّة الذكاء القانوني العقاري**
*An AI-powered LegalTech × PropTech platform for the real-estate contract lifecycle*

Wathiq digitizes the full real-estate transaction loop — listing, search, AI-drafted contracts, licensed-lawyer review, electronic signature, payment, and post-signature follow-up — inside one multi-tenant platform, with contract generation grounded exclusively in an ingested local-law knowledge base.

> This README is derived from the project's Software Requirements Specification, **`wathiq_SRS_V05.pdf`** (Version 5.0, July 2026). The SRS is the authoritative source for scope and behavior; refer to it for full detail.

---

## Overview

Wathiq connects every party in a real-estate transaction — property owner, broker, tenant/buyer, licensed lawyer, and platform admin — through five cooperating layers:

| Layer | Technology (proposed) | Responsibility |
|---|---|---|
| **Mobile Apps** | Flutter (single codebase, Android & iOS) | Search, listing, requests, contract tracking, signatures, notifications |
| **Web Dashboards** | Admin / Owner / Lawyer dashboards | User & content management, analytics, reporting, oversight |
| **Backend Services** | Laravel (PHP), RESTful API | Business logic, users, properties, contracts, requests, wallets, subscriptions, payment-gateway & AI-engine integration |
| **AI Legal Engine** | Independent microservice — AI Agent (LangGraph/LangChain) over an LLM, using RAG | Contract drafting, clause/risk analysis, legal-conflict and missing-clause detection, report generation |
| **Data & External Services** | PostgreSQL, a vector database (Qdrant/ChromaDB) for RAG, cloud storage, payment gateways, email/SMS/push | Core data, legal-knowledge retrieval, archiving, notifications, payments |

The AI engine runs as a decoupled microservice reachable over REST, so it can be updated or retrained independently of the rest of the platform. Contracts it drafts are never final — every contract remains a **legal draft** until a licensed lawyer reviews and approves it; final legal responsibility stays with the lawyer.

### In scope (Phase 1 / MVP)
- Account & identity management, email verification, role-based accounts
- Identity and property-ownership verification (documents reviewed by admin before listing)
- Property lifecycle management (add, edit, archive, pause/reactivate) with search & filtering
- Purchase/rental request workflow (submit, accept, reject, cancel, track status)
- AI-drafted contracts analyzed against a local-law knowledge base, routed to a lawyer for review and approval
- Electronic signature and final contract versioning
- Core electronic payment, contract execution, and QR-based handover confirmation
- Email notifications
- Basic admin console (users, lawyers, geographic areas, verification review)
- Palestinian law as the first supported legal knowledge base

### Planned for later phases
- **Growth Release** — broker management & delegation, secured wallet sharing, advanced digital wallet & payouts, automatic commission splitting, internal messaging, dispute management, an expanded analytics dashboard, and broader role/permission administration
- **Maturity Release** — detailed reporting (properties, users, finance, AI usage), AI-assisted property comparison, legal-text translation and comparison against local legislation, law-version management, wallet withdrawal, and bulk notifications
- **Beyond current scope** — support for additional countries' laws, integration with government property-ownership registries, integration with insurance providers

---

## Core Modules

The SRS organizes functional requirements into 13 modules:

| # | Module | Highlights |
|---|---|---|
| 1 | User Management & Authentication | Registration, login, logout, JWT access/refresh tokens, password recovery, email verification, profile management, account deletion |
| 2 | Identity & Ownership Verification | ID/passport upload, property-ownership document upload, admin review & approval, verification notifications |
| 3 | Property Management | Add/edit/delete listings, media upload (with automatic compression), property status lifecycle, broker delegation, archiving |
| 4 | Search & Discovery | Search by name/city/area, filters (price, type, area, rooms, bathrooms, sale/rent, location), sorting, favorites, side-by-side comparison |
| 5 | Requests & Offers | Purchase/rental requests, accept/reject/cancel, status tracking |
| 6 | AI-Powered Legal Contract Management | AI contract drafting via RAG, jurisdiction-aware local-law selection, clause completeness/conflict/risk analysis, legal risk scoring, missing-clause detection, conflict detection, amendment suggestions, lawyer review & approval, version/audit history |
| 7 | E-Signature & Financial Execution | Send-to-sign, electronic signature, signature-completion checks, final contract versioning, e-payment, digital-wallet management, platform/broker commission calculation, fund transfer, QR-code handover confirmation, refunds |
| 8 | Notification System | Multi-channel notification delivery, channel preferences, notification history |
| 9 | Conversation System | In-platform messaging between parties, message status, attachments, archiving |
| 10 | Reports & Analytics | Dashboards, property/financial/user/AI-usage reports, export |
| 11 | Legal Content Management | Legal knowledge-source management, knowledge-base updates & re-indexing, law-version management, source verification |
| 12 | System Administration | User management, roles & permissions, system settings, admin audit log, lawyer-account management, geographic-area management, verification-request review, contract-template management |
| 13 | Dispute Management | Dispute creation, evidence upload, review, closure, administrative oversight |

---

## AI-Powered Contract Lifecycle

A contract moves through a well-defined state machine, from draft to closure:

`Draft` → `Under AI Review` → `Pending Lawyer Review` → (`Requires Modification` ⇄ lawyer edits) → `Approved` → `Awaiting Signatures` → `Fully Signed` → `Awaiting Payment` → `Active` → `Completed` (or `Cancelled` / `Expired`)

**High-level flow:**
1. Owner registers and verifies identity.
2. Owner uploads ownership documents; admin reviews and approves them.
3. Owner publishes the property once approved.
4. A beneficiary finds the property via search/filters and submits a purchase or rental request.
5. The owner or delegated broker accepts or rejects the request.
6. On acceptance, the AI Legal Engine drafts the contract, applying the applicable local law (via RAG over the legal knowledge base).
7. The system analyzes the draft — legal-risk score, proposed amendments, and any items reused from prior contracts.
8. The contract is routed to a licensed lawyer for review and approval.
9. Once approved, all parties (owner, beneficiary, lawyer) sign electronically.
10. The beneficiary pays the contract value through the payment gateway; funds are held per platform policy until handover is confirmed.
11. On physical handover, the beneficiary scans a system-generated QR code to confirm receipt.
12. QR confirmation finalizes fund release (splitting commission to the platform and broker, where applicable) and moves the contract to **Completed**.

The **Legal Risk Score** (0–100) is calculated for every analyzed contract: `0–20` very low, `21–40` low, `41–60` medium, `61–80` high, `81–100` critical.

---

## User Roles & Permissions

| Role | Summary |
|---|---|
| **System Administrator** | Full platform authority — user/lawyer/broker management, identity & ownership verification, publish approval, subscriptions, commissions, financial-operations monitoring, legal-content and local-law management, system reporting, backups |
| **Property Owner** | Verified individual/entity that lists property; manages listings, pricing, media, requests, broker delegation, contract signing, wallet, PDF downloads, financial reports |
| **Real Estate Broker** | Acts on an owner's behalf, only for properties explicitly delegated to them; cannot alter ownership data, approve contracts, or transfer funds; delegation is revocable at any time |
| **Beneficiary** (Buyer / Tenant) | Verified individual searching, comparing, and requesting properties; signs contracts, pays electronically, confirms handover via QR |
| **Licensed Lawyer** | Reviews AI-drafted contracts, edits clauses, accepts/rejects AI suggestions, gives final legal approval, signs electronically; cannot edit property data, manage wallets, delete contracts, or change user data |

**Permissions matrix (excerpt):**

| Capability | Admin | Owner | Broker | Beneficiary | Lawyer |
|---|:---:|:---:|:---:|:---:|:---:|
| User management | ✔ | ✘ | ✘ | ✘ | ✘ |
| Identity / ownership verification | ✔ | ✘ | ✘ | ✘ | ✘ |
| Add / edit property | ✘ | ✔ | ✔ (if delegated) | ✘ | ✘ |
| Delete property | ✔ | ✔ | ✘ | ✘ | ✘ |
| Create contract | ✔ | ✔ | ✔ | ✔ | ✔ |
| Review / approve contract | ✘ | ✘ | ✘ | ✘ | ✔ |
| Electronic signature | ✘ | ✔ | ✘ | ✔ | ✔ |
| Electronic payment | ✘ | ✔ | ✘ | ✔ | ✘ |
| View reports | ✔ | ✔ | ✔ | ✘ | ✔ |

---

## Business Objectives

- Digitize the entire buy/rent real-estate cycle end to end
- Cut the time needed to draft real-estate contracts
- Reduce legal errors caused by manual drafting
- Provide smart legal assistance grounded in local law
- Bring owners, lawyers, and beneficiaries together on one unified platform
- Raise transparency and trust in real-estate transactions
- Streamline electronic payment and commission handling
- Build a platform architecture that can extend to support multiple countries' laws in the future

---

## Non-Functional Requirements

The SRS defines NFRs across the following categories — see the document for measurable targets:

Performance (response time, search, page load, concurrency) · Scalability · Reliability/Availability · Security · Privacy & multi-tenant data isolation · Compliance · Usability · Accessibility · Maintainability · Monitoring & logging (audit log) · Backup & disaster recovery · AI output quality

Key constraints called out explicitly in the SRS:
- All contracts must comply with the local laws of the selected jurisdiction.
- No contract may be approved without a licensed lawyer's review.
- Funds may not be transferred until all required approvals are complete.
- Each tenant company's data must be fully isolated from every other tenant's.
- Every operation must be recorded in an audit log.
- All financial operations must be traceable.
- The system must support Arabic and English.
- The system must run on modern mobile devices and web browsers.

---

## Technology Stack

| Layer | Proposed Technology |
|---|---|
| Mobile | Flutter |
| Backend | Laravel / PHP |
| Database | PostgreSQL |
| AI Agent orchestration | LangGraph / LangChain |
| Large Language Model | Microsoft Copilot (replaceable) |
| Retrieval system | RAG (Retrieval-Augmented Generation) |
| Vector database | Qdrant or ChromaDB |
| Authentication | JWT + Refresh Token |
| API | RESTful API |
| Payments | Local & international payment gateways |

---

## Repository Structure

```
.
├── AI/          # AI Legal Engine (RAG-based contract drafting & analysis microservice)
├── Back-end/    # Laravel backend services & REST API
├── Front/       # Web dashboards (Admin / Owner / Lawyer)
├── Mobile/      # Flutter mobile applications
└── wathiq_SRS_V05.pdf   # Software Requirements Specification (source of truth)
```

Each directory currently tracks its component in isolation; consult the SRS for the module breakdown each one is expected to implement.

---

## Glossary

| Term | Definition |
|---|---|
| **SRS** | Software Requirements Specification document |
| **Multi-Tenant** | Architecture that fully isolates each company's data within a single shared system |
| **PropTech** | Technology used in the real-estate sector to improve property management, sale, and rental |
| **LegalTech** | Technology used to deliver and improve legal services |
| **AI Agent** | A smart agent using an LLM and external tools to execute varied legal tasks |
| **LLM** | Large Language Model — responsible for natural-language understanding and generation |
| **RAG** | Retrieval-Augmented Generation — combines retrieval from a knowledge base with LLM-based answer generation |
| **OCR** | Optical Character Recognition — used to digitize legacy paper contracts |
| **Digital Signature** | Electronic signature used to authorize contracts and verify signatory identity |
| **QR Code** | Quick-response code used to confirm property handover and start contract execution |
| **Audit Log** | A time-stamped log of all system operations, kept for traceability and review |
| **Wallet** | A digital balance used to manage payments and funds within the platform |
| **Legal Risk Score** | A numeric indicator (0–100) expressing a contract's level of legal risk |
| **Escrow** | An intermediary account holding funds until signature and handover conditions are met |
| **SaaS** | Software as a Service, delivered via recurring subscription |
| **B2B** | Business-to-business model targeting companies and real-estate offices |

---

## References

The SRS is built against:
- IEEE Std 830 — Software Requirements Specification
- ISO/IEC/IEEE 29148 — Requirements Engineering
- OWASP Application Security Verification Standard (ASVS)
- RESTful API Design Guidelines
- OAuth 2.0 Authorization Framework
- JSON Web Token (JWT)
- OpenAPI Specification
- The local real-estate laws of the country/countries the system operates in
- Applicable electronic-signature and e-payment regulations

---

## Assumptions & Dependencies

- Stable internet connectivity is required for the app to function.
- A certified electronic payment gateway is available.
- A qualified electronic-signature service is available.
- The local legal knowledge base is kept up to date on a periodic basis.
- Licensed lawyers cooperate in reviewing contracts.
- End users have devices capable of running the applications.
- Email and SMS delivery services are available.

---

## Document Reference

- **Document**: Software Requirements Specification (SRS) — Wathiq
- **Version**: 5.0
- **Created / Last updated**: July 2026
- **System type**: MVP
- **Domain**: LegalTech × PropTech × Artificial Intelligence

See [`wathiq_SRS_V05.pdf`](wathiq_SRS_V05.pdf) for the complete specification, including all functional requirements (FR-1.1 – FR-13.8), use cases (UC-001 – UC-134), business rules, and non-functional requirement targets.
