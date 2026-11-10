from flask import Blueprint

from liga.blueprints.auth import bp as auth_bp
from liga.blueprints.gameplay import bp as play_bp
from liga.blueprints.main import bp as main_bp
from liga.blueprints.profile import bp as profile_bp
from liga.blueprints.settings import bp as settings_bp
from liga.blueprints.study import bp as study_bp


def register(app) -> None:
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(play_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(study_bp)
    app.register_blueprint(settings_bp)
