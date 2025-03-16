from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_migrate import Migrate
from config import Config
from flask_socketio import SocketIO

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    CORS(app, resources={
        r"/*": {
            "origins": "*",  # Allow all origins
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type", "X-Requested-With"],
            "supports_credentials": True,
            "send_wildcard": False
        }
    })
    migrate.init_app(app, db)
    login_manager.login_view = 'auth.login'

    from app.routes.main import bp as main_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.store import bp as store_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp)

    # Initialize database
    from app.models.database import init_db
    init_db(app)

    return app 