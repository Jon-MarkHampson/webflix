import os
from flask import Flask
from models import db

def create_app():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    db_path  = os.path.join(BASE_DIR, 'data', 'moviweb.db')

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI']        = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    @app.cli.command("init-db")
    def init_db():
        db.drop_all()
        db.create_all()
        print(f"✅ Database initialized at {db_path}")

    @app.route('/')
    def home():
        return "Welcome to MovieWeb App!"

    return app

if __name__ == '__main__':
    create_app().run(debug=True)