document.addEventListener('DOMContentLoaded', () => {
    // --- Seletores de Elementos da UI ---
    const senderNameInput = document.getElementById('sender-name');
    const smtpEmailInput = document.getElementById('smtp-email');
    const smtpPasswordInput = document.getElementById('smtp-password');
    
    const spreadsheetUpload = document.getElementById('spreadsheet-upload');
    const spreadsheetFilename = document.getElementById('spreadsheet-filename');
    const columnMappingArea = document.getElementById('column-mapping-area');
    const emailColSelect = document.getElementById('email-col');

    const filterColumnSelect = document.getElementById('filter-column-select');
    const filterValuesArea = document.getElementById('filter-values-area');
    const filterSearchInput = document.getElementById('filter-search');
    const filterCheckboxes = document.getElementById('filter-checkboxes');
    const showMoreBtn = document.getElementById('show-more-filters-btn');

    const addEmailBodyBtn = document.getElementById('add-email-body-btn');
    const emailBodyList = document.getElementById('email-body-list');
    const randomizeBodyCheckbox = document.getElementById('randomize-body-checkbox');
    const subjectCol1Select = document.getElementById('subject-col-1');
    const subjectCol2Select = document.getElementById('subject-col-2');

    const resumeUpload = document.getElementById('resume-upload');
    const resumeFilename = document.getElementById('resume-filename');
    const coverLetterUpload = document.getElementById('cover-letter-upload');
    const coverLetterFilename = document.getElementById('cover-letter-filename');
    const cleanMetadataCheckbox = document.getElementById('clean-metadata-checkbox');
    const uploadAttachmentsBtn = document.getElementById('upload-attachments-btn');

    const minIntervalInput = document.getElementById('min-interval');
    const maxIntervalInput = document.getElementById('max-interval');
    const saveSettingsBtn = document.getElementById('save-settings-btn');

    const startBtn = document.getElementById('start-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    const stopBtn = document.getElementById('stop-btn');

    const statusText = document.getElementById('status-text');
    const sentCount = document.getElementById('sent-count');
    const totalCount = document.getElementById('total-count');
    const progressBar = document.getElementById('progress-bar');
    const errorMessage = document.getElementById('error-message');

    const nextSendContainer = document.getElementById('next-send-progress-container');
    const nextSendCountdown = document.getElementById('next-send-countdown');
    const nextSendProgressBar = document.getElementById('next-send-progress-bar');

    let allFilterValues = [];
    const initialVisibleFilters = 10;
    let statusInterval, nextSendInterval;

    // --- FUNÇÕES ESSENCIAIS RESTAURADAS ---
    const showPopup = (title, message, isError = false) => {
        const popup = document.getElementById('success-popup');
        document.getElementById('popup-title').textContent = title;
        document.getElementById('popup-message').textContent = message;
        const icon = document.getElementById('popup-icon');
        
        popup.classList.toggle('is-error', isError);
        icon.className = `fas ${isError ? 'fa-times-circle' : 'fa-check-circle'} popup-icon`;

        popup.style.display = 'grid';
        setTimeout(() => {
            popup.style.opacity = 1;
            popup.querySelector('.popup-content').style.transform = 'scale(1)';
        }, 10);
    };

    document.getElementById('popup-close-btn').addEventListener('click', () => {
        const popup = document.getElementById('success-popup');
        popup.style.opacity = 0;
        popup.querySelector('.popup-content').style.transform = 'scale(0.9)';
        setTimeout(() => { popup.style.display = 'none'; }, 300);
    });
    
    const apiCall = async (url, options = {}) => {
        try {
            errorMessage.textContent = ''; 
            const response = await fetch(url, options);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || `Erro HTTP: ${response.status}`);
            }
            return data;
        } catch (error) {
            errorMessage.textContent = error.message;
            showPopup('Erro', error.message, true);
            throw error;
        }
    };

    const safeApiCall = async (callback) => {
        try { await callback(); } catch (error) { /* Erro já exibido pelo apiCall */ }
    };

    // --- Lógica da UI e Event Listeners ---

    const renderFilterCheckboxes = (values) => {
        filterCheckboxes.innerHTML = '';
        values.slice(0, initialVisibleFilters).forEach(value => filterCheckboxes.appendChild(createCheckbox(value)));
        showMoreBtn.style.display = values.length > initialVisibleFilters ? 'block' : 'none';
        showMoreBtn.textContent = `Mostrar mais (${values.length - initialVisibleFilters} restantes)`;
    };

    const createCheckbox = (value) => {
        const id = `filter-${value.replace(/\W/g, '-')}`;
        const checkboxDiv = document.createElement('div');
        checkboxDiv.className = 'checkbox-item';
        checkboxDiv.innerHTML = `<input type="checkbox" id="${id}" value="${value}"><label for="${id}">${value}</label>`;
        return checkboxDiv;
    };

    spreadsheetUpload.addEventListener('change', () => safeApiCall(async () => {
        const file = spreadsheetUpload.files[0];
        if (!file) return;
        spreadsheetFilename.textContent = file.name;
        const formData = new FormData();
        formData.append('spreadsheet', file);
        const data = await apiCall('/upload', { method: 'POST', body: formData });
        const columns = data.columns || [];
        [emailColSelect, filterColumnSelect, subjectCol1Select, subjectCol2Select].forEach(select => {
            select.innerHTML = '<option value="">-- Selecione --</option>';
            columns.forEach(col => select.add(new Option(col, col)));
        });
        columnMappingArea.style.display = 'block';
    }));

    filterColumnSelect.addEventListener('change', () => safeApiCall(async () => {
        const selectedColumn = filterColumnSelect.value;
        filterValuesArea.style.display = selectedColumn ? 'block' : 'none';
        if (!selectedColumn) return;
        const data = await apiCall('/get-filter-values', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ column: selectedColumn }) });
        allFilterValues = data.values || [];
        renderFilterCheckboxes(allFilterValues);
    }));
    
    filterSearchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredValues = allFilterValues.filter(v => v.toLowerCase().includes(searchTerm));
        renderFilterCheckboxes(filteredValues);
    });

    showMoreBtn.addEventListener('click', () => {
        const searchTerm = filterSearchInput.value.toLowerCase();
        const filteredValues = allFilterValues.filter(v => v.toLowerCase().includes(searchTerm));
        filterCheckboxes.innerHTML = '';
        filteredValues.forEach(value => filterCheckboxes.appendChild(createCheckbox(value)));
        showMoreBtn.style.display = 'none';
    });

    addEmailBodyBtn.addEventListener('click', () => {
        const newTextArea = document.createElement('textarea');
        newTextArea.className = 'email-body-input';
        newTextArea.placeholder = 'Corpo do e-mail alternativo...';
        emailBodyList.appendChild(newTextArea);
    });

    resumeUpload.addEventListener('change', () => { resumeFilename.textContent = resumeUpload.files[0] ? resumeUpload.files[0].name : 'Nenhum'; });
    coverLetterUpload.addEventListener('change', () => { coverLetterFilename.textContent = coverLetterUpload.files[0] ? coverLetterUpload.files[0].name : 'Nenhum'; });

    uploadAttachmentsBtn.addEventListener('click', () => safeApiCall(async () => {
        const formData = new FormData();
        if (resumeUpload.files[0]) formData.append('resume', resumeUpload.files[0]);
        if (coverLetterUpload.files[0]) formData.append('cover_letter', coverLetterUpload.files[0]);
        formData.append('clean_metadata', cleanMetadataCheckbox.checked);

        if (!formData.has('resume') && !formData.has('cover_letter')) {
            showPopup('Aviso', 'Nenhum anexo selecionado para processar.');
            return;
        }
        const data = await apiCall('/upload-attachments', { method: 'POST', body: formData });
        showPopup('Sucesso', data.success);
    }));

    saveSettingsBtn.addEventListener('click', () => safeApiCall(async () => {
        const emailBodyInputs = emailBodyList.querySelectorAll('.email-body-input');
        const emailBodies = Array.from(emailBodyInputs).map(input => input.value).filter(Boolean);
        const checkedFilterValues = Array.from(filterCheckboxes.querySelectorAll('input:checked')).map(cb => cb.value);
        
        const settings = {
            smtp_credentials: {
                email: smtpEmailInput.value,
                password: smtpPasswordInput.value,
                sender_name: senderNameInput.value
            },
            column_mapping: { email_col: emailColSelect.value },
            filter_settings: { column: filterColumnSelect.value, values: checkedFilterValues },
            email_template: {
                subject_parts: [subjectCol1Select.value, subjectCol2Select.value],
                body: emailBodies,
                randomize_body: randomizeBodyCheckbox.checked
            },
            timing_settings: { min_interval: parseInt(minIntervalInput.value), max_interval: parseInt(maxIntervalInput.value) },
        };
        
        const data = await apiCall('/save-settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) });
        showPopup('Configurações Salvas', data.success);
    }));

    const setupControlAction = (btn, action) => {
        btn.addEventListener('click', () => safeApiCall(async () => {
            const data = await apiCall(`/${action}-sending`, { method: 'POST' });
            showPopup('Sucesso', data.success);
            pollStatus(); // Reinicia o polling imediatamente após a ação
        }));
    };
    setupControlAction(startBtn, 'start');
    setupControlAction(pauseBtn, 'pause');
    setupControlAction(resumeBtn, 'resume');
    setupControlAction(stopBtn, 'stop');

    // --- Polling e Lógica de Estado ---
    const updateUIwithState = (state) => {
        statusText.textContent = state.status;
        sentCount.textContent = state.sent;
        totalCount.textContent = state.total;
        progressBar.style.width = state.total > 0 ? `${(state.sent / state.total) * 100}%` : '0%';
        
        if (state.error && errorMessage.textContent !== state.error) errorMessage.textContent = state.error;

        const isRunning = state.status === 'RUNNING';
        const isPaused = state.status === 'PAUSED';
        const isStarting = state.status === 'STARTING';
        const isIdle = state.status === 'IDLE' || state.status === 'FINISHED' || state.status === 'STOPPED' || state.status === 'ERROR';

        startBtn.disabled = !isIdle;
        pauseBtn.disabled = !isRunning;
        resumeBtn.disabled = !isPaused;
        stopBtn.disabled = isIdle || isStarting;

        if (state.next_send_time > 0 && isRunning) {
            updateNextSendProgress(state.next_send_time, state.wait_interval);
        } else {
            nextSendContainer.style.display = 'none';
            if (nextSendInterval) clearInterval(nextSendInterval);
        }
        
        if (isIdle && statusInterval) {
            // Para o polling se a tarefa estiver concluída ou parada
            // clearInterval(statusInterval);
        }
    };

    const updateNextSendProgress = (endTime, totalInterval) => {
        if (nextSendInterval) clearInterval(nextSendInterval);
        nextSendContainer.style.display = 'block';
        nextSendInterval = setInterval(() => {
            const now = Date.now() / 1000;
            const remaining = endTime - now;
            if (remaining <= 0) {
                nextSendContainer.style.display = 'none';
                clearInterval(nextSendInterval);
                return;
            }
            const elapsed = totalInterval - remaining;
            const progressPercentage = (elapsed / totalInterval) * 100;
            nextSendCountdown.textContent = Math.ceil(remaining);
            nextSendProgressBar.style.width = `${progressPercentage}%`;
        }, 100);
    };

    const pollStatus = () => {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(async () => {
            try {
                // Não usa safeApiCall para não mostrar pop-up em cada falha de polling
                const response = await fetch('/status');
                const state = await response.json();
                updateUIwithState(state);
            } catch (error) {
                // Silenciosamente para o polling em caso de erro de rede
                if (statusInterval) clearInterval(statusInterval);
            }
        }, 1500);
    };
    
    safeApiCall(async () => {
        const initialState = await apiCall('/status');
        updateUIwithState(initialState);
        pollStatus();
    });
});