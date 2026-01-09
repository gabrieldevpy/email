import os
import pandas as pd
import smtplib
import json
import time
import random
import threading
from flask import Blueprint, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from . import metadata_cleaner

ui_blueprint = Blueprint('ui', __name__, template_folder='templates')

# --- Constantes e Gerenciamento de Estado ---
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CHECKPOINT_FILE = os.path.join(UPLOAD_FOLDER, 'checkpoint.json')

# Dicionário para gerenciar o estado do processo de envio
# Este objeto será compartilhado entre as requests
sending_process_state = {
    'status': 'IDLE',  # Estados possíveis: IDLE, RUNNING, PAUSED, STOPPED, FINISHED, ERROR
    'thread': None,
    'sent_count': 0,
    'total_count': 0,
    'error_message': None
}

# --- Rota Principal e de Status ---
@ui_blueprint.route('/')
def index():
    # Reseta o estado ao carregar a página principal para garantir um começo limpo
    global sending_process_state
    if sending_process_state['status'] not in ['RUNNING', 'PAUSED']:
         sending_process_state = {
            'status': 'IDLE', 'thread': None, 'sent_count': 0, 
            'total_count': 0, 'error_message': None
        }
    return render_template('index.html')

@ui_blueprint.route('/status')
def status():
    # Retorna o estado atual do processo de envio
    state = {
        'status': sending_process_state['status'],
        'sent': sending_process_state['sent_count'],
        'total': sending_process_state['total_count'],
        'remaining': sending_process_state['total_count'] - sending_process_state['sent_count'],
        'error': sending_process_state['error_message']
    }
    return jsonify(state)

# --- Rotas de Configuração (Funções existentes adaptadas) ---

@ui_blueprint.route('/test-connection', methods=['POST'])
def test_connection():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    # Lógica de teste de conexão SMTP (inalterada)...
    # ... (código original)
    try:
        domain = email.split('@')[1]
        smtp_server_map = {
            'gmail.com': 'smtp.gmail.com', 'outlook.com': 'smtp.office365.com',
            'hotmail.com': 'smtp.office365.com', 'office365.com': 'smtp.office365.com',
            'yahoo.com': 'smtp.mail.yahoo.com'
        }
        smtp_server = smtp_server_map.get(domain, f"smtp.{domain}")
        port = 587
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(email, password)
        session['smtp_credentials'] = {'email': email, 'password': password, 'server': smtp_server, 'port': port}
        return jsonify({'success': 'Conexão bem-sucedida!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ui_blueprint.route('/upload', methods=['POST'])
def upload_spreadsheet():
    # Lógica de upload e leitura de colunas (inalterada)...
    # ... (código original)
    if 'spreadsheet' not in request.files: return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['spreadsheet']
    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(filepath)
    session['filepath'] = filepath
    try:
        df = pd.read_excel(filepath) if filepath.endswith('.xlsx') else pd.read_csv(filepath)
        return jsonify({'columns': df.columns.tolist()})
    except Exception as e:
        return jsonify({'error': f'Erro ao ler planilha: {e}'}), 500

@ui_blueprint.route('/save-settings', methods=['POST'])
def save_settings():
    # Rota unificada para salvar todas as configurações da UI
    data = request.get_json()
    session['column_mapping'] = data.get('column_mapping')
    session['email_template'] = data.get('email_template')
    session['timing_settings'] = data.get('timing_settings')
    
    # Validação Mapeamento de Assunto
    subject_mapping = data.get('email_template', {}).get('subject_mapping', [])
    if len(subject_mapping) > 2:
        return jsonify({'error': 'Você pode selecionar no máximo 2 colunas para o assunto.'}), 400

    return jsonify({'success': 'Configurações salvas com sucesso!'})


@ui_blueprint.route('/upload-attachments', methods=['POST'])
def upload_attachments():
    # Lógica de upload de anexos (inalterada)...
    # ... (código original)
    resume_file = request.files.get('resume')
    cover_letter_file = request.files.get('cover_letter')
    if not resume_file or not cover_letter_file: return jsonify({'error': 'Ambos os anexos são obrigatórios.'}), 400
    
    resume_path = os.path.join(UPLOAD_FOLDER, secure_filename(resume_file.filename))
    cover_letter_path = os.path.join(UPLOAD_FOLDER, secure_filename(cover_letter_file.filename))
    resume_file.save(resume_path)
    cover_letter_file.save(cover_letter_path)
    
    session['attachments'] = {
        'resume_path': resume_path,
        'cover_letter_path': cover_letter_path,
        'clean_metadata': request.form.get('clean_metadata') == 'true'
    }
    return jsonify({'success': 'Anexos carregados!'})


# --- Rota Principal de Disparo (agora inicia a thread) ---

@ui_blueprint.route('/start-sending', methods=['POST'])
def start_sending():
    global sending_process_state
    if sending_process_state['status'] == 'RUNNING':
        return jsonify({'error': 'Processo de envio já está em andamento.'}), 400

    # Limpa o estado de erro, se houver
    sending_process_state['error_message'] = None
    
    # Inicia a thread em background
    # Passamos uma cópia da sessão para a thread, para evitar problemas de concorrência
    sending_thread = threading.Thread(target=email_sending_worker, args=(dict(session),))
    sending_process_state['thread'] = sending_thread
    sending_thread.start()
    
    return jsonify({'success': 'Processo de envio iniciado.'})

# --- Worker de Envio (executado na thread) ---

def email_sending_worker(user_session):
    global sending_process_state
    
    # Carregar configurações da sessão passada como argumento
    filepath = user_session.get('filepath')
    column_mapping = user_session.get('column_mapping')
    email_template = user_session.get('email_template')
    attachments_info = user_session.get('attachments')
    smtp_creds = user_session.get('smtp_credentials')
    timing = user_session.get('timing_settings', {'min_interval': 5, 'max_interval': 15, 'is_random': True})

    try:
        df = pd.read_excel(filepath) if filepath.endswith('.xlsx') else pd.read_csv(filepath)
        total_emails = len(df)
        sending_process_state.update({'status': 'RUNNING', 'total_count': total_emails, 'sent_count': 0})

        # Carregar checkpoint
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoint = json.load(f)
            last_sent_index = checkpoint.get('last_sent_index', -1)
            sending_process_state['sent_count'] = last_sent_index + 1
        except (FileNotFoundError, json.JSONDecodeError):
            last_sent_index = -1
        
        # Processar anexos (limpeza de metadados)
        resume_path = metadata_cleaner.clean_metadata(attachments_info['resume_path']) if attachments_info['clean_metadata'] else attachments_info['resume_path']
        cover_letter_path = metadata_cleaner.clean_metadata(attachments_info['cover_letter_path']) if attachments_info['clean_metadata'] else attachments_info['cover_letter_path']

        # Conectar ao servidor SMTP
        with smtplib.SMTP(smtp_creds['server'], smtp_creds['port']) as server:
            server.starttls()
            server.login(smtp_creds['email'], smtp_creds['password'])

            for index, row in df.iterrows():
                if index <= last_sent_index:
                    continue
                
                # --- Pausa/Stop Check ---
                while sending_process_state['status'] == 'PAUSED':
                    time.sleep(1) # Espera 1 segundo antes de checar novamente
                
                if sending_process_state['status'] == 'STOPPED':
                    print("Processo interrompido pelo usuário.")
                    break # Sai do loop for

                # Construção do Assunto Dinâmico
                subject_parts = []
                for col_name in email_template.get('subject_mapping', []):
                    if col_name and col_name in row and pd.notna(row[col_name]):
                        subject_parts.append(str(row[col_name]))
                
                if subject_parts:
                    subject = " - ".join(subject_parts)
                else: # Fallback
                    subject = email_template.get('subject', 'Sem Assunto')

                # Construção do E-mail
                msg = MIMEMultipart()
                msg['From'] = smtp_creds['email']
                msg['To'] = row[column_mapping['email_col']]
                msg['Subject'] = subject
                
                body = email_template.get('body', '').replace('{{nome}}', str(row.get(column_mapping.get('name_col'), ''))).replace('{{valor}}', str(row.get(column_mapping.get('value_col'), '')))
                msg.attach(MIMEText(body, 'plain'))

                for path in [resume_path, cover_letter_path]:
                    with open(path, 'rb') as attachment_file:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment_file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(path)}')
                    msg.attach(part)
                
                # Envio do E-mail
                server.send_message(msg)
                
                # Atualizar estado e checkpoint
                sending_process_state['sent_count'] += 1
                with open(CHECKPOINT_FILE, 'w') as f:
                    json.dump({'last_sent_index': index}, f)

                # Intervalo de tempo
                sleep_time = random.randint(timing['min_interval'], timing['max_interval']) if timing['is_random'] else timing['min_interval']
                time.sleep(sleep_time)

        if sending_process_state['status'] != 'STOPPED':
            sending_process_state['status'] = 'FINISHED'
            if os.path.exists(CHECKPOINT_FILE):
                os.remove(CHECKPOINT_FILE) # Limpa o checkpoint ao finalizar com sucesso

    except Exception as e:
        print(f"Erro no worker de envio: {e}")
        sending_process_state['status'] = 'ERROR'
        sending_process_state['error_message'] = str(e)


# --- Rotas de Controle de Execução ---

@ui_blueprint.route('/pause-sending', methods=['POST'])
def pause_sending():
    global sending_process_state
    if sending_process_state['status'] == 'RUNNING':
        sending_process_state['status'] = 'PAUSED'
        return jsonify({'success': 'Processo de envio pausado.'})
    return jsonify({'error': 'Nenhum processo em andamento para pausar.'}), 400

@ui_blueprint.route('/resume-sending', methods=['POST'])
def resume_sending():
    global sending_process_state
    if sending_process_state['status'] == 'PAUSED':
        sending_process_state['status'] = 'RUNNING'
        return jsonify({'success': 'Processo de envio retomado.'})
    return jsonify({'error': 'Nenhum processo pausado para retomar.'}), 400

@ui_blueprint.route('/stop-sending', methods=['POST'])
def stop_sending():
    global sending_process_state
    if sending_process_state['status'] in ['RUNNING', 'PAUSED']:
        sending_process_state['status'] = 'STOPPED'
        # A thread principal irá detectar o estado 'STOPPED' e sair do loop
        return jsonify({'success': 'Processo de envio interrompido.'})
    return jsonify({'error': 'Nenhum processo em andamento para interromper.'}), 400
