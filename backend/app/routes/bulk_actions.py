from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..models import BulkActionJob
from ..middleware.rbac import require_permission, get_current_user
from ..services.bulk_service import BulkActionService

bulk_bp = Blueprint("bulk", __name__)

@bulk_bp.route("/actions", methods=["POST"])
@jwt_required()
@require_permission("bulk:execute")
def create_and_execute():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    action_type = data.get("action_type", "").upper()
    merchant_ids = data.get("merchant_ids", [])
    params = data.get("params", {})
    user = get_current_user()
    if not isinstance(merchant_ids, list) or not merchant_ids:
        return jsonify({"error": "merchant_ids must be a non-empty list"}), 400
    try:
        job = BulkActionService.create_job(
            action_type=action_type,
            merchant_ids=merchant_ids,
            actor_id=user.id,
            params=params,
        )
        job = BulkActionService.execute_job(job.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal error", "detail": str(e)}), 500
    status_code = 200 if job.status == "COMPLETED" else 207
    return jsonify({
        "data": job.to_dict(),
        "message": f"Bulk job {job.job_reference} {job.status.lower()}",
    }), status_code

@bulk_bp.route("/jobs", methods=["GET"])
@jwt_required()
@require_permission("bulk:read")
def list_jobs():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    status = request.args.get("status")
    query = BulkActionJob.query
    if status:
        query = query.filter_by(status=status.upper())
    pagination = query.order_by(BulkActionJob.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "data": [j.to_dict() for j in pagination.items],
        "pagination": {
            "page": pagination.page,
            "total": pagination.total,
            "pages": pagination.pages,
        }
    }), 200

@bulk_bp.route("/jobs/<int:job_id>", methods=["GET"])
@jwt_required()
@require_permission("bulk:read")
def get_job(job_id):
    job = BulkActionJob.query.get_or_404(job_id)
    return jsonify({"data": job.to_dict()}), 200

@bulk_bp.route("/validate", methods=["POST"])
@jwt_required()
@require_permission("bulk:execute")
def validate_bulk():
    data = request.get_json() or {}
    merchant_ids = data.get("merchant_ids", [])
    action_type = data.get("action_type", "").upper()
    if not merchant_ids:
        return jsonify({"valid": False, "error": "No merchant IDs provided"}), 400
    from ..models import Merchant
    existing = Merchant.query.filter(Merchant.id.in_(merchant_ids)).all()
    found_ids = {m.id for m in existing}
    missing = list(set(merchant_ids) - found_ids)
    return jsonify({
        "valid": len(missing) == 0,
        "action_type": action_type,
        "total_requested": len(merchant_ids),
        "found": len(found_ids),
        "missing_ids": missing,
        "preview": [
            {"id": m.id, "merchant_id": m.merchant_id,
             "business_name": m.business_name,
             "current_status": m.risk_status,
             "is_frozen": m.is_frozen}
            for m in existing[:10]
        ]
    }), 200