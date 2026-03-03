import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Role, User, Merchant
from datetime import datetime, timedelta
import random

ROLES = [
    {
        "name": "ADMIN",
        "description": "Full system access",
        "permissions": [
            "merchant:read", "merchant:create", "merchant:update",
            "merchant:freeze", "merchant:status_change", "merchant:assign",
            "bulk:execute", "bulk:read", "audit:read", "user:manage",
        ],
    },
    {
        "name": "ANALYST",
        "description": "Risk analyst",
        "permissions": [
            "merchant:read", "merchant:update",
            "merchant:freeze", "merchant:status_change", "merchant:assign",
            "bulk:execute", "bulk:read", "audit:read",
        ],
    },
    {
        "name": "VIEWER",
        "description": "Read-only access",
        "permissions": [
            "merchant:read", "bulk:read", "audit:read",
        ],
    },
]

SAMPLE_MERCHANTS = [
    {"business_name": "FastPay Solutions Ltd", "country": "GBR", "risk_score": 85, "risk_status": "BLOCKED", "is_frozen": True, "flagged_reason": "Chargeback ratio exceeded 2%"},
    {"business_name": "QuickShop Online", "country": "USA", "risk_score": 62, "risk_status": "REVIEW", "is_frozen": False, "flagged_reason": "Unusual transaction velocity"},
    {"business_name": "TrustMart Retail", "country": "DEU", "risk_score": 15, "risk_status": "APPROVED", "is_frozen": False, "flagged_reason": None},
    {"business_name": "NovaPay Gateway", "country": "SNG", "risk_score": 91, "risk_status": "BLOCKED", "is_frozen": True, "flagged_reason": "Suspected money laundering"},
    {"business_name": "SafeBuy Ecommerce", "country": "AUS", "risk_score": 28, "risk_status": "APPROVED", "is_frozen": False, "flagged_reason": None},
    {"business_name": "GlobalTrade Co", "country": "CAN", "risk_score": 74, "risk_status": "REVIEW", "is_frozen": False, "flagged_reason": "High-risk MCC code"},
    {"business_name": "MicroPay Fintech", "country": "NGA", "risk_score": 88, "risk_status": "BLOCKED", "is_frozen": True, "flagged_reason": "Sanctioned region exposure"},
    {"business_name": "ShopNow Platform", "country": "IND", "risk_score": 45, "risk_status": "REVIEW", "is_frozen": False, "flagged_reason": "Pending KYC verification"},
    {"business_name": "ClearPay Ltd", "country": "GBR", "risk_score": 10, "risk_status": "APPROVED", "is_frozen": False, "flagged_reason": None},
    {"business_name": "ZeroRisk Payments", "country": "USA", "risk_score": 5, "risk_status": "APPROVED", "is_frozen": False, "flagged_reason": None},
    {"business_name": "FraudAlert Services", "country": "ZAF", "risk_score": 79, "risk_status": "REVIEW", "is_frozen": True, "flagged_reason": "Duplicate account detected"},
    {"business_name": "EasyMoney Transfer", "country": "PAK", "risk_score": 95, "risk_status": "BLOCKED", "is_frozen": True, "flagged_reason": "PEP connection identified"},
    {"business_name": "OpenCart Marketplace", "country": "BRA", "risk_score": 55, "risk_status": "REVIEW", "is_frozen": False, "flagged_reason": "Volume spike 400%"},
    {"business_name": "LoyalPay Corp", "country": "FRA", "risk_score": 22, "risk_status": "APPROVED", "is_frozen": False, "flagged_reason": None},
    {"business_name": "UltraStore Digital", "country": "MEX", "risk_score": 67, "risk_status": "REVIEW", "is_frozen": False, "flagged_reason": "First-party fraud signals"},
]

BUSINESS_TYPES = ["E-commerce", "Retail", "SaaS", "Marketplace", "Financial Services"]
MCC_CODES = ["5411", "5812", "7372", "5999", "4814", "7995"]

def seed():
    app = create_app("development")
    with app.app_context():
        print("Seeding database...")
        role_map = {}
        for role_data in ROLES:
            existing = Role.query.filter_by(name=role_data["name"]).first()
            if not existing:
                role = Role(**role_data)
                db.session.add(role)
                db.session.flush()
                role_map[role_data["name"]] = role
                print(f"  Role created: {role_data['name']}")
            else:
                role_map[role_data["name"]] = existing
        db.session.commit()

        users_data = [
            {"email": "admin@riskops.io", "username": "admin", "full_name": "System Administrator", "password": "Admin@123!", "role": "ADMIN"},
            {"email": "analyst@riskops.io", "username": "analyst1", "full_name": "Jane Analyst", "password": "Analyst@123!", "role": "ANALYST"},
            {"email": "viewer@riskops.io", "username": "viewer1", "full_name": "Bob Viewer", "password": "Viewer@123!", "role": "VIEWER"},
        ]
        for ud in users_data:
            if not User.query.filter_by(email=ud["email"]).first():
                u = User(
                    email=ud["email"],
                    username=ud["username"],
                    full_name=ud["full_name"],
                    role_id=role_map[ud["role"]].id,
                )
                u.set_password(ud["password"])
                db.session.add(u)
                print(f"  User created: {ud['email']}")
        db.session.commit()

        for i, m_data in enumerate(SAMPLE_MERCHANTS):
            mid = f"MRC{str(i+1).zfill(5)}"
            if not Merchant.query.filter_by(merchant_id=mid).first():
                m = Merchant(
                    merchant_id=mid,
                    business_name=m_data["business_name"],
                    legal_name=m_data["business_name"] + " (Legal)",
                    email=f"contact@merchant{i+1}.com",
                    phone=f"+1-555-{random.randint(1000,9999)}",
                    country=m_data["country"],
                    business_type=random.choice(BUSINESS_TYPES),
                    mcc_code=random.choice(MCC_CODES),
                    monthly_volume=round(random.uniform(10000, 2000000), 2),
                    risk_score=m_data["risk_score"],
                    risk_status=m_data["risk_status"],
                    is_frozen=m_data["is_frozen"],
                    flagged_reason=m_data.get("flagged_reason"),
                    flagged_at=datetime.utcnow() - timedelta(days=random.randint(1,30)) if m_data.get("flagged_reason") else None,
                )
                db.session.add(m)
        db.session.commit()
        print(f"\nDone! {len(SAMPLE_MERCHANTS)} merchants seeded.")
        print("\nCredentials:")
        print("  Admin:   admin@riskops.io / Admin@123!")
        print("  Analyst: analyst@riskops.io / Analyst@123!")
        print("  Viewer:  viewer@riskops.io / Viewer@123!")

if __name__ == "__main__":
    seed()