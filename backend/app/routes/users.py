from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from .. import db
from ..models import User, Role
from ..middleware.rbac import require_permission, require_roles, get_current_user
from ..services.audit_service import AuditService

users_bp = Blueprint("users", __name__)

@users_bp.route("/", methods=["GET"])
@jwt_required()
@require_roles("ADMIN")
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"data": [u.to_dict() for u in users]}), 200

@users_bp.route("/", methods=["POST"])
@jwt_required()
@require_roles("ADMIN")
def create_user():
    data = request.get_json() or {}
    actor = get_current_user()
    required = ["email", "username", "full_name", "password", "role_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing: {missing}"}), 400
    if User.query.filter_by(email=data["email"].lower()).first():
        return jsonify({"error": "Email already registered"}), 409
    role = Role.query.get(data["role_id"])
    if not role:
        return jsonify({"error": "Role not found"}), 404
    user = User(
        email=data["email"].strip().lower(),
        username=data["username"].strip(),
        full_name=data["full_name"].strip(),
        role_id=data["role_id"],
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()
    AuditService.log_action(
        action=AuditService.USER_CREATED,
        actor_id=actor.id,
        entity_type="USER",
        entity_id=str(user.id),
        new_state={"email": user.email, "role": role.name},
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": user.to_dict()}), 201

@users_bp.route("/<int:user_id>/deactivate", methods=["POST"])
@jwt_required()
@require_roles("ADMIN")
def deactivate_user(user_id):
    actor = get_current_user()
    user = User.query.get_or_404(user_id)
    if user.id == actor.id:
        return jsonify({"error": "Cannot deactivate yourself"}), 400
    user.is_active = False
    AuditService.log_action(
        action=AuditService.USER_DEACTIVATED,
        actor_id=actor.id,
        entity_type="USER",
        entity_id=str(user.id),
        new_state={"is_active": False},
        commit=False,
    )
    db.session.commit()
    return jsonify({"message": f"User {user.username} deactivated"}), 200

@users_bp.route("/<int:user_id>/role", methods=["PATCH"])
@jwt_required()
@require_roles("ADMIN")
def change_role(user_id):
    actor = get_current_user()
    data = request.get_json() or {}
    user = User.query.get_or_404(user_id)
    role = Role.query.get(data.get("role_id"))
    if not role:
        return jsonify({"error": "Role not found"}), 404
    prev_role = user.role.name
    user.role_id = role.id
    AuditService.log_action(
        action=AuditService.USER_ROLE_CHANGED,
        actor_id=actor.id,
        entity_type="USER",
        entity_id=str(user.id),
        previous_state={"role": prev_role},
        new_state={"role": role.name},
        commit=False,
    )
    db.session.commit()
    return jsonify({"data": user.to_dict()}), 200

@users_bp.route("/roles", methods=["GET"])
@jwt_required()
@require_permission("merchant:read")
def list_roles():
    roles = Role.query.all()
    return jsonify({"data": [r.to_dict() for r in roles]}), 200