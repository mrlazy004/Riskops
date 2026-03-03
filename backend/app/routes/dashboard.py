from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, case
from datetime import datetime, timedelta
from .. import db
from ..models import Merchant, AuditLog, BulkActionJob
from ..middleware.rbac import require_permission

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/summary", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def summary():
    total = db.session.query(func.count(Merchant.id)).scalar()
    by_status = db.session.query(
        Merchant.risk_status, func.count(Merchant.id)
    ).group_by(Merchant.risk_status).all()
    frozen_count = db.session.query(func.count(Merchant.id)).filter(
        Merchant.is_frozen == True
    ).scalar()
    restricted_count = db.session.query(func.count(Merchant.id)).filter(
        Merchant.is_restricted == True
    ).scalar()
    high_risk = db.session.query(func.count(Merchant.id)).filter(
        Merchant.risk_score >= 75
    ).scalar()
    since = datetime.utcnow() - timedelta(hours=24)
    recent_actions = db.session.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= since
    ).scalar()
    bulk_stats = db.session.query(
        BulkActionJob.status, func.count(BulkActionJob.id)
    ).group_by(BulkActionJob.status).all()
    unassigned_review = db.session.query(func.count(Merchant.id)).filter(
        Merchant.risk_status == "REVIEW",
        Merchant.assigned_to == None
    ).scalar()
    return jsonify({
        "merchants": {
            "total": total,
            "by_status": {s: c for s, c in by_status},
            "frozen": frozen_count,
            "restricted": restricted_count,
            "high_risk": high_risk,
            "unassigned_review": unassigned_review,
        },
        "activity": {
            "actions_last_24h": recent_actions,
        },
        "bulk_jobs": {s: c for s, c in bulk_stats},
        "generated_at": datetime.utcnow().isoformat(),
    }), 200

@dashboard_bp.route("/flagged", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def flagged_merchants():
    merchants = (
        Merchant.query
        .filter(Merchant.risk_status.in_(["REVIEW", "BLOCKED"]))
        .order_by(Merchant.risk_score.desc())
        .limit(20)
        .all()
    )
    return jsonify({"data": [m.to_dict() for m in merchants]}), 200

@dashboard_bp.route("/recent-activity", methods=["GET"])
@jwt_required()
@require_permission("audit:read")
def recent_activity():
    logs = (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )
    return jsonify({"data": [l.to_dict() for l in logs]}), 200

@dashboard_bp.route("/risk-distribution", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def risk_distribution():
    buckets = db.session.query(
        case(
            (Merchant.risk_score < 25, "0-24"),
            (Merchant.risk_score < 50, "25-49"),
            (Merchant.risk_score < 75, "50-74"),
            else_="75-100"
        ).label("bucket"),
        func.count(Merchant.id).label("count")
    ).group_by("bucket").all()
    return jsonify({
        "data": [{"bucket": b, "count": c} for b, c in buckets]
    }), 200