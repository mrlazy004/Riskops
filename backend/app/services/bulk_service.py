import uuid
from datetime import datetime
from .. import db
from ..models import Merchant, BulkActionJob
from .audit_service import AuditService


ALLOWED_BULK_ACTIONS = {
    "FREEZE", "UNFREEZE", "RESTRICT", "UNRESTRICT",
    "SET_REVIEW", "SET_APPROVED", "SET_BLOCKED", "ASSIGN"
}


class BulkActionService:
    """
    Handles atomic bulk operations across multiple merchants.
    Each individual merchant action is logged independently in audit trail.
    """

    @staticmethod
    def create_job(action_type: str, merchant_ids: list, actor_id: int, params: dict = None) -> BulkActionJob:
        """Validate and register a new bulk action job."""
        if action_type not in ALLOWED_BULK_ACTIONS:
            raise ValueError(f"Invalid action type: {action_type}")

        if not merchant_ids:
            raise ValueError("merchant_ids cannot be empty")

        if len(merchant_ids) > 500:
            raise ValueError("Bulk action limited to 500 merchants per job")

        # Validate all merchant IDs exist
        existing = {m.id for m in Merchant.query.filter(Merchant.id.in_(merchant_ids)).all()}
        invalid = set(merchant_ids) - existing
        if invalid:
            raise ValueError(f"Merchant IDs not found: {list(invalid)}")

        job = BulkActionJob(
            job_reference=f"BULK-{uuid.uuid4().hex[:10].upper()}",
            action_type=action_type,
            status="PENDING",
            initiated_by=actor_id,
            total_merchants=len(merchant_ids),
            merchant_ids=merchant_ids,
            action_params=params or {},
        )
        db.session.add(job)
        db.session.commit()

        AuditService.log_action(
            action=AuditService.BULK_JOB_CREATED,
            actor_id=actor_id,
            entity_type="BULK_JOB",
            entity_id=job.job_reference,
            bulk_job_id=job.id,
            new_state={"action_type": action_type, "total_merchants": len(merchant_ids)},
        )

        return job

    @staticmethod
    def execute_job(job_id: int) -> BulkActionJob:
        """
        Synchronously execute a bulk job.
        In production, offload to Celery worker for large batches.
        """
        job = BulkActionJob.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status not in ("PENDING",):
            raise ValueError(f"Job {job_id} already in status: {job.status}")

        job.status = "PROCESSING"
        job.started_at = datetime.utcnow()
        db.session.commit()

        merchants = Merchant.query.filter(Merchant.id.in_(job.merchant_ids)).all()
        merchant_map = {m.id: m for m in merchants}

        errors = {}

        for merchant_id in job.merchant_ids:
            merchant = merchant_map.get(merchant_id)
            if not merchant:
                errors[str(merchant_id)] = "Merchant not found"
                job.failure_count += 1
                job.processed_count += 1
                continue

            try:
                prev = BulkActionService._get_state_snapshot(merchant)
                BulkActionService._apply_action(merchant, job.action_type, job.action_params)
                new = BulkActionService._get_state_snapshot(merchant)

                # Per-merchant audit log (bulk_job_id links them all together)
                AuditService.log_action(
                    action=f"BULK_{job.action_type}",
                    actor_id=job.initiated_by,
                    entity_type="MERCHANT",
                    entity_id=merchant.merchant_id,
                    merchant_id=merchant.id,
                    bulk_job_id=job.id,
                    previous_state=prev,
                    new_state=new,
                    metadata={"job_reference": job.job_reference, **job.action_params},
                    commit=False,
                )

                job.success_count += 1
            except Exception as exc:
                db.session.rollback()
                errors[str(merchant_id)] = str(exc)
                job.failure_count += 1

            job.processed_count += 1

        # Final job state
        if job.failure_count == 0:
            job.status = "COMPLETED"
        elif job.success_count == 0:
            job.status = "FAILED"
        else:
            job.status = "PARTIAL"

        job.error_details = errors
        job.completed_at = datetime.utcnow()
        db.session.commit()

        AuditService.log_action(
            action=AuditService.BULK_JOB_COMPLETED,
            actor_id=job.initiated_by,
            entity_type="BULK_JOB",
            entity_id=job.job_reference,
            bulk_job_id=job.id,
            new_state={
                "status": job.status,
                "success": job.success_count,
                "failures": job.failure_count,
            },
        )

        return job

    @staticmethod
    def _apply_action(merchant: Merchant, action: str, params: dict):
        """Apply a single action to one merchant."""
        reason = params.get("reason", "")

        if action == "FREEZE":
            merchant.is_frozen = True
        elif action == "UNFREEZE":
            merchant.is_frozen = False
        elif action == "RESTRICT":
            merchant.is_restricted = True
            merchant.restriction_reason = reason
        elif action == "UNRESTRICT":
            merchant.is_restricted = False
            merchant.restriction_reason = None
        elif action == "SET_REVIEW":
            merchant.risk_status = "REVIEW"
        elif action == "SET_APPROVED":
            merchant.risk_status = "APPROVED"
            merchant.is_frozen = False  # auto-unfreeze on approval
        elif action == "SET_BLOCKED":
            merchant.risk_status = "BLOCKED"
            merchant.is_frozen = True   # auto-freeze on block
        elif action == "ASSIGN":
            assign_to = params.get("assign_to")
            if not assign_to:
                raise ValueError("assign_to user ID required for ASSIGN action")
            merchant.assigned_to = assign_to
        else:
            raise ValueError(f"Unknown action: {action}")

        merchant.updated_at = datetime.utcnow()
        db.session.add(merchant)

    @staticmethod
    def _get_state_snapshot(merchant: Merchant) -> dict:
        return {
            "risk_status": merchant.risk_status,
            "is_frozen": merchant.is_frozen,
            "is_restricted": merchant.is_restricted,
            "restriction_reason": merchant.restriction_reason,
            "assigned_to": merchant.assigned_to,
        }
