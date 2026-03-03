from datetime import datetime
from flask import request
from .. import db
from ..models import AuditLog


class AuditService:
    """
    Central audit logging service.
    Every state-changing action in the system MUST call log_action().
    """

    # ── Defined action constants ──────────────────────────────────────────
    MERCHANT_FREEZE = "MERCHANT_FREEZE"
    MERCHANT_UNFREEZE = "MERCHANT_UNFREEZE"
    MERCHANT_RESTRICT = "MERCHANT_RESTRICT"
    MERCHANT_UNRESTRICT = "MERCHANT_UNRESTRICT"
    MERCHANT_STATUS_CHANGE = "MERCHANT_STATUS_CHANGE"
    MERCHANT_ASSIGN = "MERCHANT_ASSIGN"
    MERCHANT_CREATED = "MERCHANT_CREATED"
    MERCHANT_UPDATED = "MERCHANT_UPDATED"
    BULK_JOB_CREATED = "BULK_JOB_CREATED"
    BULK_JOB_COMPLETED = "BULK_JOB_COMPLETED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_CREATED = "USER_CREATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"

    @staticmethod
    def log_action(
        action: str,
        actor_id: int,
        entity_type: str,
        entity_id: str,
        merchant_id: int = None,
        bulk_job_id: int = None,
        previous_state: dict = None,
        new_state: dict = None,
        metadata: dict = None,
        commit: bool = True,
    ) -> AuditLog:
        """
        Create an immutable audit log entry.

        Args:
            action:         Action constant (e.g., MERCHANT_FREEZE)
            actor_id:       User performing the action
            entity_type:    MERCHANT | USER | BULK_JOB
            entity_id:      String identifier of the affected entity
            merchant_id:    FK to merchant if applicable
            bulk_job_id:    FK to bulk job if action is part of bulk operation
            previous_state: Dict snapshot of state before change
            new_state:      Dict snapshot of state after change
            metadata:       Extra context (reason, notes, etc.)
            commit:         Whether to commit immediately (set False in bulk ops)
        """
        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            actor_id=actor_id,
            merchant_id=merchant_id,
            bulk_job_id=bulk_job_id,
            previous_state=previous_state,
            new_state=new_state,
            extra_data=metadata or {},
            ip_address=AuditService._get_ip(),
            user_agent=request.headers.get("User-Agent", "")[:500] if request else "",
            timestamp=datetime.utcnow(),
        )
        db.session.add(log)
        if commit:
            db.session.commit()
        return log

    @staticmethod
    def _get_ip() -> str:
        if not request:
            return "system"
        # Handle proxies (nginx, load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.remote_addr or "unknown"

    @staticmethod
    def get_merchant_history(merchant_id: int, limit: int = 50):
        """Return audit history for a specific merchant."""
        return (
            AuditLog.query
            .filter_by(merchant_id=merchant_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_actor_history(actor_id: int, limit: int = 50):
        """Return all actions taken by a specific user."""
        return (
            AuditLog.query
            .filter_by(actor_id=actor_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )
