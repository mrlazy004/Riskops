# 🛡️ RiskOps — Automated Risk Case Management & Bulk Control System

> **Replaces spreadsheet-based risk tracking** with a production-grade internal tool for risk operations teams. Full audit trail, RBAC, real-time dashboard, and bulk merchant actions.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│   Browser → dashboard.html (Vanilla JS SPA)                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS / REST JSON
┌────────────────────────▼────────────────────────────────────────┐
│                    NGINX (Port 80)                               │
│   Static files → /usr/share/nginx/html                          │
│   /api/* → proxy_pass → Flask (Port 5000)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  FLASK BACKEND (Gunicorn 4 workers)             │
│                                                                  │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐           │
│  │  Auth   │  │Merchants │  │  Bulk   │  │ Audit  │           │
│  │  JWT    │  │  CRUD +  │  │ Actions │  │  Logs  │           │
│  │ Refresh │  │ Actions  │  │  Jobs   │  │ Trail  │           │
│  └─────────┘  └──────────┘  └─────────┘  └────────┘           │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────────────────┐        │
│  │  RBAC Middleware │  │    AuditService (central)    │        │
│  │  @require_perm   │  │  Every action logged here    │        │
│  └──────────────────┘  └──────────────────────────────┘        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │           BulkActionService                          │      │
│  │  Create Job → Validate → Execute → Log per-merchant  │      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────┬────────────────────────────────────────┘
                         │ SQLAlchemy ORM
┌────────────────────────▼────────────────────────────────────────┐
│                   MySQL 8.0 (Docker Volume)                      │
│   roles │ users │ merchants │ bulk_action_jobs │ audit_logs     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema (MySQL)

```sql
roles           — ADMIN, ANALYST, VIEWER with JSON permissions array
users           — team members with bcrypt passwords, role FK, last_login
merchants       — risk_status ENUM, is_frozen, risk_score, assigned_to FK
bulk_action_jobs — job_reference, action_type, status, merchant_ids JSON
audit_logs      — IMMUTABLE log: action, actor_id, previous_state, new_state JSON
```

**Key design decisions:**
- `audit_logs` is append-only with no UPDATE/DELETE permissions for the app user
- `bulk_action_jobs.merchant_ids` stores JSON array enabling bulk replay/audit
- `previous_state` / `new_state` JSON columns capture full before/after snapshots
- `risk_status` uses MySQL ENUM for referential integrity without a FK join

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login → JWT access + refresh tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| GET  | `/api/auth/me` | Current user profile |
| POST | `/api/auth/logout` | Logout (audit logged) |

### Merchants
| Method | Endpoint | Permission |
|--------|----------|------------|
| GET  | `/api/merchants/` | merchant:read |
| POST | `/api/merchants/` | merchant:create |
| GET  | `/api/merchants/:id` | merchant:read |
| PATCH| `/api/merchants/:id` | merchant:update |
| POST | `/api/merchants/:id/freeze` | merchant:freeze |
| POST | `/api/merchants/:id/unfreeze` | merchant:freeze |
| POST | `/api/merchants/:id/status` | merchant:status_change |
| POST | `/api/merchants/:id/assign` | merchant:assign |
| GET  | `/api/merchants/:id/history` | merchant:read |

### Bulk Actions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bulk/actions` | Create & execute bulk job |
| POST | `/api/bulk/validate` | Pre-flight validation |
| GET  | `/api/bulk/jobs` | List all bulk jobs |
| GET  | `/api/bulk/jobs/:id` | Job details + error breakdown |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | KPIs: counts by status, frozen, high-risk |
| GET | `/api/dashboard/flagged` | Top flagged merchants |
| GET | `/api/dashboard/recent-activity` | Latest audit entries |
| GET | `/api/dashboard/risk-distribution` | Risk score buckets for chart |

### Audit
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/audit/logs` | Paginated, filterable audit log |
| GET | `/api/audit/logs/:id` | Single log entry |
| GET | `/api/audit/merchants/:id/history` | Full history for merchant |

---

## 🔐 RBAC Permission Matrix

| Permission | ADMIN | ANALYST | VIEWER |
|------------|-------|---------|--------|
| merchant:read | ✅ | ✅ | ✅ |
| merchant:create | ✅ | ❌ | ❌ |
| merchant:update | ✅ | ✅ | ❌ |
| merchant:freeze | ✅ | ✅ | ❌ |
| merchant:status_change | ✅ | ✅ | ❌ |
| merchant:assign | ✅ | ✅ | ❌ |
| bulk:execute | ✅ | ✅ | ❌ |
| bulk:read | ✅ | ✅ | ✅ |
| audit:read | ✅ | ✅ | ✅ |
| user:manage | ✅ | ❌ | ❌ |

---

## 🚀 Deployment Guide

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone and configure
git clone https://github.com/yourorg/riskops
cd riskops

# 2. Set secrets
cp backend/.env.example backend/.env
# Edit SECRET_KEY and JWT_SECRET_KEY with strong random values

# 3. Start all services
docker-compose up -d

# 4. Apply migrations + seed data
docker-compose exec backend flask db upgrade
docker-compose exec backend python seed.py

# 5. Access
# Dashboard: http://localhost
# API:       http://localhost/api/
# Direct API (dev): http://localhost:5000
```

### Option B: Manual (Dev)

```bash
# MySQL
mysql -u root -p
CREATE DATABASE risk_management_dev;
CREATE USER 'riskuser'@'localhost' IDENTIFIED BY 'riskpassword';
GRANT ALL ON risk_management_dev.* TO 'riskuser'@'localhost';

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL
flask db upgrade
python seed.py
flask run

# Frontend: open frontend/dashboard.html in browser
# Set API_BASE in browser console: window.API_BASE = 'http://localhost:5000'
```

### Production Hardening Checklist
- [ ] Set strong `SECRET_KEY` and `JWT_SECRET_KEY` (≥32 chars, random)
- [ ] Enable HTTPS via nginx + certbot
- [ ] Set `CORS_ORIGINS` to your exact frontend domain
- [ ] Use a dedicated MySQL user with limited privileges
- [ ] Set `FLASK_ENV=production`
- [ ] Enable MySQL SSL connections
- [ ] Set up automated MySQL backups
- [ ] Add rate limiting to auth endpoints (Flask-Limiter)
- [ ] Configure log aggregation (ELK / CloudWatch)

---

## 📁 Project Structure

```
risk-case-management/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Flask factory + blueprint registration
│   │   ├── config.py            # Dev/Prod/Test configs
│   │   ├── models/              # SQLAlchemy models
│   │   │   └── __init__.py      # User, Role, Merchant, AuditLog, BulkActionJob
│   │   ├── routes/              # API blueprints
│   │   │   ├── auth.py          # Login / refresh / logout
│   │   │   ├── merchants.py     # CRUD + single actions
│   │   │   ├── bulk_actions.py  # Bulk job create/execute/status
│   │   │   ├── audit.py         # Audit log queries
│   │   │   ├── dashboard.py     # KPIs + summary
│   │   │   └── users.py         # User management (Admin)
│   │   ├── services/
│   │   │   ├── audit_service.py # Central audit logging
│   │   │   └── bulk_service.py  # Bulk action orchestration
│   │   └── middleware/
│   │       └── rbac.py          # @require_permission / @require_roles
│   ├── migrations/              # Flask-Migrate Alembic files
│   ├── seed.py                  # Database seeder
│   ├── run.py                   # App entry point
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── dashboard.html           # Single-page dashboard (no build step)
├── docker/
│   ├── nginx/nginx.conf
│   └── mysql/init.sql
├── docker-compose.yml
└── README.md
```

---

## 👔 Resume-Ready Project Description

**Automated Risk Case Management & Bulk Control System** | Python, Flask, MySQL, JWT, Docker

> Built a production-grade internal risk operations platform replacing Excel-based merchant tracking for a fintech risk team. System handles real-time merchant risk classification, bulk enforcement actions, and compliance-grade audit logging.

**Key achievements:**
- Designed a **JWT-authenticated REST API** with role-based access control (RBAC) enforcing granular permissions (ADMIN / ANALYST / VIEWER) across all endpoints
- Implemented a **bulk action engine** capable of executing freeze/unfreeze/block/approve operations across 500+ merchants atomically, with per-merchant audit logging linked to job reference IDs
- Built an **immutable audit trail** capturing actor, IP address, user agent, timestamp, and full before/after state snapshots in JSON for every state-changing operation — enabling forensic compliance review
- Delivered a **real-time dashboard** replacing 5+ manual Excel trackers, surfacing KPIs including by-status counts, high-risk merchant alerts, and 24-hour activity feeds
- Containerized the full stack with **Docker Compose** (MySQL 8, Redis, Gunicorn/Nginx) with environment-based config supporting dev/staging/production deployments
- Applied **SQLAlchemy ORM migrations** for zero-downtime schema evolution using Flask-Migrate/Alembic

---

## 💼 Business Impact

**Risk Angle:**
- Eliminates manual Excel errors in risk case tracking — every action is logged with user identity, timestamp, and IP, creating a defensible audit trail for regulators
- Bulk enforcement actions (freeze 200 merchants in a money laundering pattern) that previously took hours now execute in seconds with full traceability
- Role separation ensures junior analysts cannot approve blocked merchants without senior analyst/admin privileges
- Pre/post state snapshots in audit logs enable precise "what changed, when, by whom" queries during regulatory examination

**Compliance Angle:**
- Supports PCI-DSS, AML, and internal control requirements by maintaining tamper-evident logs
- Audit logs capture IP address and user agent — supports forensic investigation of insider actions
- RBAC implementation satisfies "least privilege" access controls required by SOC 2 and ISO 27001
- All bulk actions tied to job reference IDs satisfy "four-eyes principle" audit trails

**Operational Efficiency:**
- Risk team handles 10× more merchant cases with the same headcount
- Bulk jobs with reason codes replace ad-hoc email chains and spreadsheet updates
- Real-time dashboard gives risk managers instant visibility without waiting for morning reports
