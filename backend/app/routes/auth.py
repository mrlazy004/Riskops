from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from .. import db
from ..models import User
from ..services.audit_service import AuditService

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Account is deactivated."}), 403
    user.last_login = datetime.utcnow()
    db.session.commit()
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    AuditService.log_action(
        action=AuditService.USER_LOGIN,
        actor_id=user.id,
        entity_type="USER",
        entity_id=str(user.id),
        metadata={"email": user.email},
    )
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    }), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({"error": "User not found or inactive"}), 403
    access_token = create_access_token(identity=str(user_id))
    return jsonify({"access_token": access_token}), 200

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()}), 200

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    user_id = int(get_jwt_identity())
    AuditService.log_action(
        action=AuditService.USER_LOGOUT,
        actor_id=user_id,
        entity_type="USER",
        entity_id=str(user_id),
    )
    return jsonify({"message": "Logged out successfully"}), 200