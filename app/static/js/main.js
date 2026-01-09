document.addEventListener('DOMContentLoaded', () => {

    // --- Seletores de Elementos do DOM ---
    const getElem = (id) => document.getElementById(id);

    const dom = {
        // SMTP
        smtpEmail: getElem('email'),
        smtpPassword: getElem('password'),
        smtpBtn: getElem('test-conn-btn'),
        // Planilha
        spreadsheetInput: getElem('spreadsheet'),
        uploadBtn: getElem('upload-button'),
        // Mapeamento Geral
        mapName: getElem('recipient_name'),
        mapEmail: getElem('recipient_email'),
        mapValue: getElem('ticket_value'),
        // Mapeamento Assunto
        mapSubject1: getElem('subject_col_1'),
        mapSubject2: getElem('subject_col_2'),
        subjectPreview: getElem('subject-preview'),
        // Anexos
        resumeFile: getElem('resume-file'),
        coverLetterFile: getElem('cover-letter-file'),
        resumeFilename: getElem('resume-filename'),
        coverLetterFilename: getElem('cover-letter-filename'),
        cleanMetadata: getElem('clean-metadata'),
        // Template
        templateSubject: getElem('subject'),
        templateBody: getElem('email_body'),
        // Timing
        minInterval: getElem('min-interval'),
        maxInterval: getElem('max-interval'),
        isRandomInterval: getElem('random-interval'),
        // Controles
        startBtn: getElem('start-btn'),
        pauseBtn: getElem('pause-btn'),
        resumeBtn: getElem('resume-btn'),
        stopBtn: getElem('stop-btn'),
        // Progresso
        progressArea: getElem('progress-area'),
        progressBar: getElem('progress-bar'),
        statusText: getElem('status-text'),
        sentCount: getElem('sent-count'),
        totalCount: getElem('total-count'),
        remainingCount: getElem('remaining-count'),
        progressOfTotal: getElem('progress-of-total'),
        logs: getElem('send_logs')
    };

    let statusInterval;

    // --- Funções de UI e Logging ---
    const log = (message, type = 'INFO') => {
        const timestamp = new Date().toLocaleTimeString();
        dom.logs.value += `[${timestamp} ${type}] ${message}\n`;
        dom.logs.scrollTop = dom.logs.scrollHeight;
    };

    const updateButtonStates = (status) => {
        dom.startBtn.style.display = (status === 'IDLE' || status === 'STOPPED' || status === 'FINISHED' || status === 'ERROR') ? 'inline-block' : 'none';
        dom.pauseBtn.style.display = (status === 'RUNNING') ? 'inline-block' : 'none';
        dom.resumeBtn.style.display = (status === 'PAUSED') ? 'inline-block' : 'none';
        dom.stopBtn.style.display = (status === 'RUNNING' || status === 'PAUSED') ? 'inline-block' : 'none';
    };

    const updateProgressUI = (data) => {
        const percentage = data.total > 0 ? (data.sent / data.total) * 100 : 0;
        dom.progressBar.style.width = `${percentage}%`;
        dom.statusText.textContent = `Status: ${data.status || 'Ocioso'}`;
        dom.sentCount.textContent = `Enviados: ${data.sent || 0}`;
        dom.totalCount.textContent = `Total: ${data.total || 0}`;
        dom.remainingCount.textContent = `Restantes: ${data.remaining || 0}`;
        dom.progressOfTotal.textContent = `${data.sent || 0} / ${data.total || 0}`;
    };

    // --- Lógica Principal ---

    // Teste de Conexão SMTP
    dom.smtpBtn.addEventListener('click', () => {
        // ... (código existente, usando fetch e log)
        fetch('/test-connection', { /*...*/ body: JSON.stringify({ email: dom.smtpEmail.value, password: dom.smtpPassword.value }) })
            .then(res => res.json()).then(data => data.success ? log(data.success, 'SUCCESS') : log(data.error, 'ERROR'));
    });

    // Upload da Planilha
    dom.uploadBtn.addEventListener('click', () => {
        const file = dom.spreadsheetInput.files[0];
        if (!file) { log('Nenhum arquivo de planilha selecionado', 'WARN'); return; }
        const formData = new FormData();
        formData.append('spreadsheet', file);
        fetch('/upload', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                if (data.error) { log(data.error, 'ERROR'); return; }
                const selects = [dom.mapName, dom.mapEmail, dom.mapValue, dom.mapSubject1, dom.mapSubject2];
                selects.forEach(s => {
                    s.innerHTML = '<option value="">-- Não usar --</option>';
                    data.columns.forEach(col => s.add(new Option(col, col)));
                });
                log(`Planilha "${file.name}" carregada. Colunas mapeadas.`, 'SUCCESS');
            });
    });

    // Preview do Assunto
    [dom.mapSubject1, dom.mapSubject2].forEach(elem => elem.addEventListener('change', () => {
        const sub1 = dom.mapSubject1.value;
        const sub2 = dom.mapSubject2.value;
        let preview = 'Preview: ';
        if (sub1 && sub2) preview += `${sub1} - ${sub2}`;
        else if (sub1) preview += sub1;
        else if (sub2) preview += sub2;
        else preview += dom.templateSubject.value || '(Assunto Padrão)';
        dom.subjectPreview.textContent = preview;
    }));

    // Feedback de nome de arquivo
    dom.resumeFile.addEventListener('change', e => dom.resumeFilename.textContent = e.target.files[0]?.name || '');
    dom.coverLetterFile.addEventListener('change', e => dom.coverLetterFilename.textContent = e.target.files[0]?.name || '');

    // --- Funções de Controle de Envio ---

    const collectAndSaveSettings = async () => {
        log('Coletando e salvando configurações...');

        // 1. Upload de Anexos (se necessário)
        const attachmentsForm = new FormData();
        attachmentsForm.append('resume', dom.resumeFile.files[0]);
        attachmentsForm.append('cover_letter', dom.coverLetterFile.files[0]);
        attachmentsForm.append('clean_metadata', dom.cleanMetadata.checked);
        try {
            const res = await fetch('/upload-attachments', { method: 'POST', body: attachmentsForm });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            log('Anexos carregados com sucesso.', 'SUCCESS');
        } catch (err) {
            log(`Erro no upload de anexos: ${err.message}`, 'ERROR');
            return false;
        }

        // 2. Coletar e salvar outras configs
        const settings = {
            column_mapping: {
                name_col: dom.mapName.value,
                email_col: dom.mapEmail.value,
                value_col: dom.mapValue.value,
            },
            email_template: {
                subject: dom.templateSubject.value,
                body: dom.templateBody.value,
                subject_mapping: [dom.mapSubject1.value, dom.mapSubject2.value].filter(Boolean)
            },
            timing_settings: {
                min_interval: parseInt(dom.minInterval.value),
                max_interval: parseInt(dom.maxInterval.value),
                is_random: dom.isRandomInterval.checked
            }
        };

        try {
            const res = await fetch('/save-settings', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(settings)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);
            log('Configurações da campanha salvas.', 'SUCCESS');
            return true;
        } catch(err) {
            log(`Erro ao salvar configurações: ${err.message}`, 'ERROR');
            return false;
        }
    };

    const startStatusPolling = () => {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(async () => {
            try {
                const res = await fetch('/status');
                const data = await res.json();
                updateProgressUI(data);
                updateButtonStates(data.status);
                
                if (['FINISHED', 'STOPPED', 'ERROR'].includes(data.status)) {
                    clearInterval(statusInterval);
                    statusInterval = null;
                    log(`Processo finalizado com status: ${data.status}.`, 'INFO');
                    if(data.error) log(`Mensagem de erro: ${data.error}`, 'ERROR');
                }
            } catch (err) {
                log('Falha ao obter status do servidor.', 'ERROR');
                clearInterval(statusInterval);
            }
        }, 1500);
    };

    dom.startBtn.addEventListener('click', async () => {
        log('Iniciando nova campanha de envio...', 'INFO');
        dom.progressArea.style.display = 'block';
        const settingsSaved = await collectAndSaveSettings();
        if (!settingsSaved) {
            log('Falha ao salvar configurações. Abortando início.', 'ERROR');
            return;
        }

        fetch('/start-sending', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.error) { log(data.error, 'ERROR'); return; }
                log(data.success, 'SUCCESS');
                startStatusPolling();
            });
    });

    dom.pauseBtn.addEventListener('click', () => {
        log('Pausando o envio...', 'WARN');
        fetch('/pause-sending', { method: 'POST' });
    });

    dom.resumeBtn.addEventListener('click', () => {
        log('Retomando o envio...', 'INFO');
        fetch('/resume-sending', { method: 'POST' });
    });

    dom.stopBtn.addEventListener('click', () => {
        if (confirm('Tem certeza que deseja parar o envio? O progresso até aqui será salvo, mas você não poderá retomar esta sessão.')) {
            log('Parando o envio...', 'WARN');
            fetch('/stop-sending', { method: 'POST' });
        }
    });

    // --- Inicialização ---
    log('Assistente de Envio inicializado.');
    fetch('/status').then(res => res.json()).then(data => { // Pega o estado inicial ao carregar
        updateProgressUI(data);
        updateButtonStates(data.status);
        if (data.status === 'RUNNING' || data.status === 'PAUSED') {
            dom.progressArea.style.display = 'block';
            startStatusPolling();
            log('Sessão de envio anterior detectada. Retomando monitoramento.', 'INFO');
        }
    });
});
