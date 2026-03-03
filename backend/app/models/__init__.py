from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from .. import db


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship("User", back_populates="role")

    def has_permission(self, permission: str) -> bool:
        return permission in (self.permissions or [])

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
        }


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    role = db.relationship("Role", back_populates="users")
    audit_logs = db.relationship("AuditLog", back_populates="actor")
    bulk_jobs = db.relationship("BulkActionJob", back_populates="initiated_by_user")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission: str) -> bool:
        return self.role.has_permission(permission) if self.role else False

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role.to_dict() if self.role else None,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
        }


class Merchant(db.Model):
    __tablename__ = "merchants"
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    business_name = db.Column(db.String(200), nullable=False)
    legal_name = db.Column(db.String(200))
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    country = db.Column(db.String(3), nullable=False, index=True)
    business_type = db.Column(db.String(100))
    mcc_code = db.Column(db.String(10))
    monthly_volume = db.Column(db.Numeric(15, 2), default=0)
    risk_score = db.Column(db.Integer, default=0)
    risk_status = db.Column(
        db.Enum("REVIEW", "APPROVED", "BLOCKED", name="risk_status_enum"),
        default="REVIEW", nullable=False, index=True
    )
    is_frozen = db.Column(db.Boolean, default=False, index=True)
    is_restricted = db.Column(db.Boolean, default=False)
    restriction_reason = db.Column(db.String(500))
    flagged_at = db.Column(db.DateTime)
    flagged_reason = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_user = db.relationship("User", foreign_keys=[assigned_to])
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    audit_logs = db.relationship("AuditLog", back_populates="merchant")

    def to_dict(self):
        return {
            "id": self.id,
            "merchant_id": self.merchant_id,
            "business_name": self.business_name,
            "legal_name": self.legal_name,
            "email": self.email,
            "phone": self.phone,
            "country": self.country,
            "business_type": self.business_type,
            "mcc_code": self.mcc_code,
            "monthly_volume": float(self.monthly_volume or 0),
            "risk_score": self.risk_score,
            "risk_status": self.risk_status,
            "is_frozen": self.is_frozen,
            "is_restricted": self.is_restricted,
            "restriction_reason": self.restriction_reason,
            "flagged_at": self.flagged_at.isoformat() if self.flagged_at else None,
            "flagged_reason": self.flagged_reason,
            "assigned_to": self.assigned_to,
            "assigned_user": self.assigned_user.full_name if self.assigned_user else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.String(50), index=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=True, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    bulk_job_id = db.Column(db.Integer, db.ForeignKey("bulk_action_jobs.id"), nullable=True)
    previous_state = db.Column(db.JSON)
    new_state = db.Column(db.JSON)
    extra_data = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    merchant = db.relationship("Merchant", back_populates="audit_logs")
    actor = db.relationship("User", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "merchant_id": self.merchant_id,
            "merchant_name": self.merchant.business_name if self.merchant else None,
            "actor_id": self.actor_id,
            "actor_name": self.actor.full_name if self.actor else None,
            "actor_email": self.actor.email if self.actor else None,
            "bulk_job_id": self.bulk_job_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "metadata": self.extra_data,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat(),
        }


class BulkActionJob(db.Model):
    __tablename__ = "bulk_action_jobs"
    id = db.Column(db.Integer, primary_key=True)
    job_reference = db.Column(db.String(50), unique=True, nullable=False, index=True)
    action_type = db.Column(
        db.Enum("FREEZE", "UNFREEZE", "RESTRICT", "UNRESTRICT",
                "SET_REVIEW", "SET_APPROVED", "SET_BLOCKED", "ASSIGN",
                name="bulk_action_type_enum"),
        nullable=False
    )
    status = db.Column(
        db.Enum("PENDING", "PROCESSING", "COMPLETED", "PARTIAL", "FAILED",
                name="bulk_job_status_enum"),
        default="PENDING", nullable=False, index=True
    )
    initiated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    initiated_by_user = db.relationship("User", back_populates="bulk_jobs")
    total_merchants = db.Column(db.Integer, default=0)
    processed_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)
    merchant_ids = db.Column(db.JSON, nullable=False)
    action_params = db.Column(db.JSON)
    error_details = db.Column(db.JSON)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    audit_logs = db.relationship("AuditLog", backref="bulk_job")

    def to_dict(self):
        return {
            "id": self.id,
            "job_reference": self.job_reference,
            "action_type": self.action_type,
            "status": self.status,
            "initiated_by": self.initiated_by,
            "initiated_by_name": self.initiated_by_user.full_name if self.initiated_by_user else None,
            "total_merchants": self.total_merchants,
            "processed_count": self.processed_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "action_params": self.action_params,
            "error_details": self.error_details,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }