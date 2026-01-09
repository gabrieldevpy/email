import os
import pandas as pd
import smtplib
from flask import Blueprint, render_template, request, jsonify, session
from werkzeug.utils import secure_filename

from .services import EmailSenderService, SendingState, CheckpointManager

# --- Instância dos Serviços e Estado Global ---
sending_state = SendingState()
checkpoint_manager = CheckpointManager()
email_service = EmailSenderService(state_manager=sending_state, checkpoint_manager=checkpoint_manager)

# --- Configuração da Blueprint ---
ui_blueprint = Blueprint('ui', __name__, template_folder='templates', static_folder='static')
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Funções Auxiliares ---
def get_smtp_server_details(email):
    """Determina o servidor SMTP a partir do domínio do e-mail."""
    domain = email.split('@')[1]
    server_map = {
        'gmail.com': ('smtp.gmail.com', 587),
        'outlook.com': ('smtp.office365.com', 587),
        'hotmail.com': ('smtp.office365.com', 587),
        'yahoo.com': ('smtp.mail.yahoo.com', 587),
    }
    return server_map.get(domain, (f"smtp.{domain}", 587))

# --- Rotas da Aplicação ---

@ui_blueprint.route('/')
def index():
    """Renderiza a página inicial e limpa o estado de campanhas anteriores."""
    current_status = sending_state.get_status_dict()['status']
    if current_status not in ['RUNNING', 'PAUSED', 'STARTING']:
        email_service.stop_sending()
        checkpoint_manager.clear()
        session.clear()
        sending_state.__init__() # Garante um estado inicial limpo
    return render_template('index.html')

@ui_blueprint.route('/status')
def status():
    """Fornece o estado atual da campanha para o front-end."""
    return jsonify(sending_state.get_status_dict())

@ui_blueprint.route('/test-connection', methods=['POST'])
def test_connection():
    """Testa as credenciais SMTP e as salva na sessão."""
    data = request.get_json() or {}
    try:
        email, password, sender_name = data.get('email'), data.get('password'), data.get('sender_name', '')
        if not email or not password: raise ValueError("E-mail e senha são obrigatórios.")
        server_addr, port = get_smtp_server_details(email)
        with smtplib.SMTP(server_addr, port) as server:
            server.starttls()
            server.login(email, password)
        session['smtp_credentials'] = {
            'email': email, 'password': password, 
            'server': server_addr, 'port': port, 'sender_name': sender_name
        }
        session.modified = True
        return jsonify({'success': 'Conexão SMTP bem-sucedida!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ui_blueprint.route('/upload', methods=['POST'])
def upload_spreadsheet():
    """Faz o upload da planilha e extrai os nomes das colunas."""
    if 'spreadsheet' not in request.files: return jsonify({'error': 'Nenhum arquivo de planilha selecionado.'}), 400
    file = request.files['spreadsheet']
    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(filepath)
    session['filepath'] = filepath
    session.modified = True
    try:
        df = pd.read_excel(filepath) if filepath.endswith(('.xlsx', '.xls')) else pd.read_csv(filepath)
        return jsonify({'columns': df.columns.tolist()})
    except Exception as e:
        return jsonify({'error': f'Erro ao ler planilha: {e}'}), 500

@ui_blueprint.route('/get-filter-values', methods=['POST'])
def get_filter_values():
    """Retorna os valores únicos de uma coluna da planilha para filtragem."""
    data, filepath = request.get_json() or {}, session.get('filepath')
    column = data.get('column')
    if not column or not filepath: return jsonify({'error': 'Coluna ou planilha não especificada.'}), 400
    try:
        df = pd.read_excel(filepath) if filepath.endswith(('.xlsx', '.xls')) else pd.read_csv(filepath)
        if column not in df.columns: return jsonify({'error': 'A coluna selecionada não existe na planilha.'}), 400
        unique_values = df[column].dropna().unique().tolist()
        return jsonify({'values': sorted([str(v) for v in unique_values])})
    except Exception as e:
        return jsonify({'error': f'Erro ao processar valores do filtro: {e}'}), 500

@ui_blueprint.route('/upload-attachments', methods=['POST'])
def upload_attachments():
    """Processa os anexos e salva suas informações na sessão."""
    files_to_save = [request.files.get('resume'), request.files.get('cover_letter')]
    saved_paths = []
    for file in files_to_save:
        if file and file.filename:
            filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
            file.save(filepath)
            saved_paths.append(filepath)
    
    # Estrutura correta para o services.py
    session['attachments'] = {
        'files': saved_paths, 
        'clean_metadata': request.form.get('clean_metadata') == 'true'
    }
    session.modified = True
    return jsonify({'success': 'Anexos processados com sucesso!'})

@ui_blueprint.route('/save-settings', methods=['POST'])
def save_settings():
    """Salva todas as configurações da campanha na sessão."""
    data = request.get_json() or {}
    session['column_mapping'] = data.get('column_mapping')
    session['email_template'] = data.get('email_template')
    session['timing_settings'] = data.get('timing_settings')
    session['filter_settings'] = data.get('filter_settings')
    session.modified = True
    return jsonify({'success': 'Configurações salvas com sucesso!'})

# --- Rotas de Controle da Campanha ---

@ui_blueprint.route('/start-sending', methods=['POST'])
def start_sending():
    try:
        # Passa uma cópia do dicionário da sessão para o serviço
        email_service.start_sending_process(dict(session))
        return jsonify({'success': 'Processo de envio iniciado.'})
    except (ValueError, KeyError) as e:
        return jsonify({'error': f'Erro ao iniciar: {e}'}), 400

@ui_blueprint.route('/pause-sending', methods=['POST'])
def pause_sending():
    email_service.pause_sending()
    return jsonify({'success': 'Processo de envio pausado.'})

@ui_blueprint.route('/resume-sending', methods=['POST'])
def resume_sending():
    email_service.resume_sending()
    return jsonify({'success': 'Processo de envio retomado.'})

@ui_blueprint.route('/stop-sending', methods=['POST'])
def stop_sending():
    email_service.stop_sending()
    return jsonify({'success': 'Processo de envio interrompido.'})
