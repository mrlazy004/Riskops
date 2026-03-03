from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import desc
from ..models import AuditLog
from ..middleware.rbac import require_permission

audit_bp = Blueprint("audit", __name__)

@audit_bp.route("/logs", methods=["GET"])
@jwt_required()
@require_permission("audit:read")
def list_logs():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 30, type=int), 200)
    action = request.args.get("action")
    actor_id = request.args.get("actor_id", type=int)
    merchant_id = request.args.get("merchant_id", type=int)
    query = AuditLog.query
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if actor_id:
        query = query.filter_by(actor_id=actor_id)
    if merchant_id:
        query = query.filter_by(merchant_id=merchant_id)
    pagination = query.order_by(desc(AuditLog.timestamp)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "data": [log.to_dict() for log in pagination.items],
        "pagination": {
            "page": pagination.page,
            "total": pagination.total,
            "pages": pagination.pages,
        }
    }), 200

@audit_bp.route("/logs/<int:log_id>", methods=["GET"])
@jwt_required()
@require_permission("audit:read")
def get_log(log_id):
    log = AuditLog.query.get_or_404(log_id)
    return jsonify({"data": log.to_dict()}), 200

@audit_bp.route("/merchants/<int:merchant_id>/history", methods=["GET"])
@jwt_required()
@require_permission("audit:read")
def merchant_audit_history(merchant_id):
    limit = request.args.get("limit", 50, type=int)
    logs = (
        AuditLog.query
        .filter_by(merchant_id=merchant_id)
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
        .all()
    )
    return jsonify({"data": [l.to_dict() for l in logs]}), 200