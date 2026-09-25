"""Application factory for the Dunbar Veterinary Clinic appointment system."""
from pathlib import Path

from flask import Flask

from config import CONFIG_MAP
from app.models import db, ensure_schema_compatibility


def create_app(config=None):
    """Create and configure the Flask application.

    ``config`` may be a config name ("default", "test") or a dict of overrides
    (used by the test suite)."""
    app = Flask(__name__, instance_relative_config=True)

    if isinstance(config, dict):
        app.config.from_object(CONFIG_MAP["default"])
        app.config.update(config)
    else:
        app.config.from_object(CONFIG_MAP.get(config or "default", CONFIG_MAP["default"]))

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from app.routes.appointments import appointments_bp
    from app.routes.clients import clients_bp
    from app.routes.consultations import consultations_bp
    from app.routes.farm_visits import farm_visits_bp
    from app.routes.main import main_bp
    from app.routes.offline import offline_bp
    from app.routes.rescheduling import rescheduling_bp

    app.register_blueprint(appointments_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(consultations_bp)
    app.register_blueprint(farm_visits_bp)
    app.register_blueprint(offline_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(rescheduling_bp)

    if app.config.get("CREATE_TABLES_ON_START", True):
        with app.app_context():
            db.create_all()
            ensure_schema_compatibility()

    return app
