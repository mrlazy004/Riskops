from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from .config import config

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

    from .routes.auth import auth_bp
    from .routes.merchants import merchants_bp
    from .routes.bulk_actions import bulk_bp
    from .routes.audit import audit_bp
    from .routes.dashboard import dashboard_bp
    from .routes.users import users_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(merchants_bp, url_prefix="/api/merchants")
    app.register_blueprint(bulk_bp, url_prefix="/api/bulk")
    app.register_blueprint(audit_bp, url_prefix="/api/audit")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {"error": "Token has expired", "code": "TOKEN_EXPIRED"}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {"error": "Invalid token", "code": "INVALID_TOKEN"}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {"error": "Authorization token required", "code": "MISSING_TOKEN"}, 401

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "risk-case-management"}

    return app