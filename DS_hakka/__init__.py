# __init__.py （DS_HAKKAの直下にある前提）
from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # ルートの登録
    from routes.general.explamation import general_bp
    from routes.stores.store import store_bp 
    from routes.stores_detail.stores_detail import stores_detail_bp
    from routes.users_home.users_home import users_home_bp
    from routes.users_login.users_login import users_login_bp
    from routes.users_order.users_order import users_order_bp
    from routes.stores_home_relation.stores_home_relation import stores_home_relation_bp


    app.register_blueprint(general_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(stores_detail_bp)
    app.register_blueprint(users_home_bp)
    app.register_blueprint(users_login_bp)
    app.register_blueprint(users_order_bp)
    app.register_blueprint(stores_home_relation_bp)


    return app
