from flask import Flask

def create_app():
    # CORREÇÃO: Centralizando a responsabilidade de servir arquivos estáticos no app principal.
    # Isso remove a complexidade e os conflitos gerados pelo Blueprint.
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    app.secret_key = 'super-secret-key-change-in-production'

    # Importar e registrar o Blueprint da UI. Ele ainda cuidará das rotas.
    from .ui import ui_blueprint
    app.register_blueprint(ui_blueprint)

    return app
