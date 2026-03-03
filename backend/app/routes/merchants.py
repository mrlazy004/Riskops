from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import or_
from .. import db
from ..models import Merchant
from ..middleware.rbac import require_permission, get_current_user
from ..services.audit_service import AuditService

merchants_bp = Blueprint("merchants", __name__)

@merchants_bp.route("/", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def list_merchants():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", "").strip()
    risk_status = request.args.get("risk_status")
    is_frozen = request.args.get("is_frozen")
    country = request.args.get("country")
    sort_by = request.args.get("sort_by", "updated_at")
    sort_dir = request.args.get("sort_dir", "desc")
    query = Merchant.query
    if search:
        query = query.filter(
            or_(
                Merchant.business_name.ilike(f"%{search}%"),
                Merchant.merchant_id.ilike(f"%{search}%"),
                Merchant.email.ilike(f"%{search}%"),
            )
        )
    if risk_status:
        query = query.filter(Merchant.risk_status == risk_status.upper())
    if is_frozen is not None:
        query = query.filter(Merchant.is_frozen == (is_frozen.lower() == "true"))
    if country:
        query = query.filter(Merchant.country == country.upper())
    sort_col = getattr(Merchant, sort_by, Merchant.updated_at)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "data": [m.to_dict() for m in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    }), 200

@merchants_bp.route("/<int:merchant_pk>", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def get_merchant(merchant_pk):
    merchant = Merchant.query.get_or_404(merchant_pk)
    return jsonify({"data": merchant.to_dict()}), 200

@merchants_bp.route("/", methods=["POST"])
@jwt_required()
@require_permission("merchant:create")
def create_merchant():
    data = request.get_json()
    user = get_current_user()
    required = ["merchant_id", "business_name", "email", "country"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400
    if Merchant.query.filter_by(merchant_id=data["merchant_id"]).first():
        return jsonify({"error": "Merchant ID already exists"}), 409
    merchant = Merchant(
        merchant_id=data["merchant_id"],
        business_name=data["business_name"],
        legal_name=data.get("legal_name"),
        email=data["email"],
        phone=data.get("phone"),
        country=data["country"].upper(),
        business_type=data.get("business_type"),
        mcc_code=data.get("mcc_code"),
        monthly_volume=data.get("monthly_volume", 0),
        risk_score=data.get("risk_score", 0),
        risk_status=data.get("risk_status", "REVIEW"),
        flagged_reason=data.get("flagged_reason"),
        flagged_at=datetime.utcnow() if data.get("flagged_reason") else None,
    )
    db.session.add(merchant)
    db.session.flush()
    AuditService.log_action(
        action=AuditService.MERCHANT_CREATED,
        actor_id=user.id,
        entity_type="MERCHANT",
        entity_id=merchant.merchant_id,
        merchant_id=merchant.id,
        new_state=merchant.to_dict(),
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": merchant.to_dict(), "message": "Merchant created"}), 201

@merchants_bp.route("/<int:merchant_pk>", methods=["PATCH"])
@jwt_required()
@require_permission("merchant:update")
def update_merchant(merchant_pk):
    merchant = Merchant.query.get_or_404(merchant_pk)
    data = request.get_json()
    user = get_current_user()
    prev = merchant.to_dict()
    editable = [
        "business_name", "legal_name", "email", "phone",
        "country", "business_type", "mcc_code",
        "monthly_volume", "risk_score", "flagged_reason"
    ]
    for field in editable:
        if field in data:
            setattr(merchant, field, data[field])
    db.session.flush()
    AuditService.log_action(
        action=AuditService.MERCHANT_UPDATED,
        actor_id=user.id,
        entity_type="MERCHANT",
        entity_id=merchant.merchant_id,
        merchant_id=merchant.id,
        previous_state=prev,
        new_state=merchant.to_dict(),
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": merchant.to_dict()}), 200

@merchants_bp.route("/<int:merchant_pk>/freeze", methods=["POST"])
@jwt_required()
@require_permission("merchant:freeze")
def freeze_merchant(merchant_pk):
    return _toggle_freeze(merchant_pk, freeze=True)

@merchants_bp.route("/<int:merchant_pk>/unfreeze", methods=["POST"])
@jwt_required()
@require_permission("merchant:freeze")
def unfreeze_merchant(merchant_pk):
    return _toggle_freeze(merchant_pk, freeze=False)

def _toggle_freeze(merchant_pk, freeze: bool):
    merchant = Merchant.query.get_or_404(merchant_pk)
    user = get_current_user()
    data = request.get_json() or {}
    if merchant.is_frozen == freeze:
        state = "frozen" if freeze else "unfrozen"
        return jsonify({"message": f"Merchant is already {state}"}), 200
    prev = {"is_frozen": merchant.is_frozen}
    merchant.is_frozen = freeze
    new = {"is_frozen": merchant.is_frozen}
    action = AuditService.MERCHANT_FREEZE if freeze else AuditService.MERCHANT_UNFREEZE
    AuditService.log_action(
        action=action,
        actor_id=user.id,
        entity_type="MERCHANT",
        entity_id=merchant.merchant_id,
        merchant_id=merchant.id,
        previous_state=prev,
        new_state=new,
        metadata={"reason": data.get("reason", "")},
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": merchant.to_dict(), "message": "Done"}), 200

@merchants_bp.route("/<int:merchant_pk>/status", methods=["POST"])
@jwt_required()
@require_permission("merchant:status_change")
def change_status(merchant_pk):
    merchant = Merchant.query.get_or_404(merchant_pk)
    user = get_current_user()
    data = request.get_json() or {}
    new_status = data.get("risk_status", "").upper()
    if new_status not in ("REVIEW", "APPROVED", "BLOCKED"):
        return jsonify({"error": "Invalid risk_status"}), 400
    prev = {"risk_status": merchant.risk_status}
    merchant.risk_status = new_status
    if new_status == "BLOCKED":
        merchant.is_frozen = True
    elif new_status == "APPROVED":
        merchant.is_frozen = False
    AuditService.log_action(
        action=AuditService.MERCHANT_STATUS_CHANGE,
        actor_id=user.id,
        entity_type="MERCHANT",
        entity_id=merchant.merchant_id,
        merchant_id=merchant.id,
        previous_state=prev,
        new_state={"risk_status": new_status},
        metadata={"reason": data.get("reason", "")},
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": merchant.to_dict()}), 200

@merchants_bp.route("/<int:merchant_pk>/assign", methods=["POST"])
@jwt_required()
@require_permission("merchant:assign")
def assign_merchant(merchant_pk):
    merchant = Merchant.query.get_or_404(merchant_pk)
    user = get_current_user()
    data = request.get_json() or {}
    assign_to = data.get("assign_to")
    prev = {"assigned_to": merchant.assigned_to}
    merchant.assigned_to = assign_to
    AuditService.log_action(
        action=AuditService.MERCHANT_ASSIGN,
        actor_id=user.id,
        entity_type="MERCHANT",
        entity_id=merchant.merchant_id,
        merchant_id=merchant.id,
        previous_state=prev,
        new_state={"assigned_to": assign_to},
        metadata={"notes": data.get("notes", "")},
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": merchant.to_dict()}), 200

@merchants_bp.route("/<int:merchant_pk>/history", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def merchant_history(merchant_pk):
    merchant = Merchant.query.get_or_404(merchant_pk)
    logs = AuditService.get_merchant_history(merchant.id)
    return jsonify({"data": [l.to_dict() for l in logs]}), 200