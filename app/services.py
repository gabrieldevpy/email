import os
import time
import random
import smtplib
import pandas as pd
import piexif
import shutil
from threading import Thread, Lock
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- Estado e Checkpoint ---
class SendingState:
    def __init__(self):
        self.status = 'IDLE'
        self.sent_count = 0
        self.total_count = 0
        self.error_message = None
        self.stop_flag = False
        self.pause_flag = False
        self.next_send_time = 0
        self.wait_interval = 0
        self.lock = Lock()

    def get_status_dict(self):
        with self.lock:
            return {'status': self.status, 'sent': self.sent_count, 'total': self.total_count, 'error': self.error_message, 'next_send_time': self.next_send_time, 'wait_interval': self.wait_interval}

    def set_status(self, status, sent=None, total=None, error=None):
        with self.lock:
            self.status = status
            if sent is not None: self.sent_count = sent
            if total is not None: self.total_count = total
            self.error_message = str(error) if error else None

    def set_next_send_time(self, next_send_time, interval):
        with self.lock:
            self.next_send_time = next_send_time
            self.wait_interval = interval

class CheckpointManager:
    def __init__(self, filepath='checkpoint.txt'): self.filepath = filepath
    def save(self, index): 
        with open(self.filepath, 'w') as f: f.write(str(index))
    def load(self):
        try: return int(open(self.filepath, 'r').read().strip()) if os.path.exists(self.filepath) else 0
        except (ValueError, IOError): return 0
    def clear(self): 
        if os.path.exists(self.filepath): os.remove(self.filepath)

# --- SERVIÇO DE E-MAIL ---
class EmailSenderService:
    def __init__(self, state_manager, checkpoint_manager):
        self.state = state_manager
        self.checkpoint = checkpoint_manager
        self.thread = None

    def _validate_config(self, config):
        if not config.get('smtp_credentials'): raise ValueError("As credenciais SMTP (Passo 1) não foram testadas e salvas. Por favor, teste a conexão.")
        if not config.get('filepath'): raise ValueError("A planilha de contatos (Passo 2) não foi enviada.")
        
        column_mapping = config.get('column_mapping')
        if not column_mapping or not column_mapping.get('email_col'): 
            raise ValueError("A coluna que contém os e-mails dos destinatários não foi selecionada no Passo 2.")

        email_template = config.get('email_template')
        if not email_template or not email_template.get('body') or all(not body.strip() for body in email_template['body']):
            raise ValueError("Pelo menos um corpo de e-mail (Passo 3) deve ser preenchido.")

        timing_settings = config.get('timing_settings')
        if not timing_settings or timing_settings.get('min_interval') is None or timing_settings.get('max_interval') is None:
             raise ValueError("Os intervalos de envio (Passo 4) não foram configurados corretamente.")

    def _clean_metadata(self, file_path):
        if not file_path or not os.path.exists(file_path): return None
        if file_path.lower().endswith(('.jpg', '.jpeg')):
            clean_path = os.path.join('uploads', 'clean_' + os.path.basename(file_path))
            shutil.copy(file_path, clean_path)
            try:
                piexif.remove(clean_path)
                return clean_path
            except Exception: return clean_path 
        return file_path

    def start_sending_process(self, session_data):
        if self.thread and self.thread.is_alive():
            raise ValueError("Um processo de envio já está em andamento.")
        self.state.__init__() 
        self.checkpoint.clear()
        self.thread = Thread(target=self._email_sending_loop, args=(session_data,))
        self.thread.start()

    def _email_sending_loop(self, config):
        self.state.set_status('STARTING')
        try:
            self._validate_config(config)
            
            df = pd.read_excel(config['filepath']) if config['filepath'].endswith(('.xlsx', '.xls')) else pd.read_csv(config['filepath'])
            if config.get('filter_settings', {}).get('values'):
                df = df[df[config['filter_settings']['column']].astype(str).isin(config['filter_settings']['values'])]
            
            contacts = df.to_dict('records')
            total_emails = len(contacts)
            if total_emails == 0: raise ValueError("A sua planilha (ou o filtro aplicado) não resultou em nenhum contato para envio.")
            
            start_index = self.checkpoint.load()
            self.state.set_status('RUNNING', sent=start_index, total=total_emails)

            smtp_creds = config['smtp_credentials']
            with smtplib.SMTP(smtp_creds['server'], smtp_creds['port']) as server:
                server.starttls()
                server.login(smtp_creds['email'], smtp_creds['password'])

                for i in range(start_index, total_emails):
                    if self.state.stop_flag: break
                    while self.state.pause_flag: time.sleep(1)
                    if i > start_index and i % 10 == 0: server.noop()
                    
                    self.send_single_email(server, contacts[i], smtp_creds, config)

                    self.state.set_status('RUNNING', sent=i + 1)
                    self.checkpoint.save(i + 1)
                    
                    if i < total_emails - 1:
                        wait_time = random.randint(config['timing_settings']['min_interval'], config['timing_settings']['max_interval'])
                        self.state.set_next_send_time(time.time() + wait_time, wait_time)
                        time.sleep(wait_time)
                        self.state.set_next_send_time(0, 0)

            if not self.state.stop_flag: self.state.set_status('FINISHED')

        except (KeyError, ValueError, Exception) as e:
            self.state.set_status('ERROR', error=f"{e}")
        finally:
            if self.state.status != 'ERROR' and not self.state.stop_flag: self.checkpoint.clear()

    def send_single_email(self, server, contact, smtp_creds, config):
        msg = MIMEMultipart()
        msg['From'] = f"{smtp_creds.get('sender_name') or smtp_creds['email']} <{smtp_creds['email']}>"
        msg['To'] = contact[config['column_mapping']['email_col']]
        
        subject_parts = [str(contact.get(col, '')) for col in config['email_template']['subject_parts'] if col and contact.get(col)]
        msg['Subject'] = ' '.join(filter(None, subject_parts))

        email_bodies = config['email_template']['body']
        body_to_use = random.choice(email_bodies) if config['email_template'].get('randomize_body') and email_bodies else email_bodies[0]
        for col, val in contact.items(): body_to_use = body_to_use.replace(f'{{{col}}}', str(val))
        msg.attach(MIMEText(body_to_use, 'plain'))

        clean_metadata_flag = config.get('attachments', {}).get('clean_metadata', False)
        cleaned_files = []
        try:
            for file_path in config.get('attachments', {}).get('files', []):
                file_to_attach = self._clean_metadata(file_path) if clean_metadata_flag else file_path
                if file_to_attach and os.path.exists(file_to_attach):
                    cleaned_files.append(file_to_attach)
                    with open(file_to_attach, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(file_path)}")
                        msg.attach(part)
            server.send_message(msg)
        finally:
            for f in cleaned_files:
                if 'clean_' in f and os.path.exists(f): os.remove(f)

    def pause_sending(self): self.state.pause_flag = True; self.state.set_status('PAUSED')
    def resume_sending(self): self.state.pause_flag = False; self.state.set_status('RUNNING')
    def stop_sending(self): 
        self.state.stop_flag = True
        if self.thread: self.thread.join(timeout=2)
        self.state.set_status('STOPPED')
