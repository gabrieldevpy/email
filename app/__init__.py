import os
from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # CORREÇÃO CRÍTICA: Usar uma chave secreta estática.
    # A chave secreta era gerada dinamicamente a cada reinicialização, o que
    # invalidava a sessão do usuário e fazia com que todas as configurações
    # salvas (credenciais, timer, mapeamentos) fossem perdidas entre os cliques.
    app.config['SECRET_KEY'] = 'a-super-secret-key-for-session-persistence'
    
    # Garante que a pasta de uploads exista
    upload_folder = os.path.join(os.path.dirname(app.root_path), 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder

    # Importa e registra a Blueprint da UI
    from .ui import ui_blueprint
    app.register_blueprint(ui_blueprint)

    return app
