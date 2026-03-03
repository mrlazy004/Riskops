from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from ..models import User


def require_permission(*permissions):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({"error": "User not found or inactive"}), 403
            if not any(user.has_permission(p) for p in permissions):
                return jsonify({"error": "Insufficient permissions", "code": "FORBIDDEN"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({"error": "User not found or inactive"}), 403
            if user.role.name not in roles:
                return jsonify({"error": "Role not authorized", "code": "FORBIDDEN"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user():
    user_id = int(get_jwt_identity())
    return User.query.get(user_id)