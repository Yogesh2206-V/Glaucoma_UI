document.addEventListener('DOMContentLoaded', () => {
    let selectedFile = null;
    let currentFilter = 'glaucoma'; // Default to Glaucoma patients list as requested
    let currentSearch = '';
    let currentSort = 'newest';
    let currentViewMode = 'cards'; // 'cards' or 'table'
    let currentPatientsData = [];
    let activeModalPatientId = null;

    // ==========================================================================
    // Theme Switcher Logic
    // ==========================================================================
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const themeText = document.getElementById('themeText');
    const htmlElement = document.documentElement;

    const savedTheme = localStorage.getItem('oculoscan_theme') || 'light';
    applyTheme(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = htmlElement.getAttribute('data-theme');
            const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
            applyTheme(nextTheme);
            localStorage.setItem('oculoscan_theme', nextTheme);
        });
    }

    function applyTheme(theme) {
        htmlElement.setAttribute('data-theme', theme);
        if (theme === 'dark') {
            if (themeIcon) {
                themeIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
            }
            if (themeText) themeText.textContent = 'Light';
        } else {
            if (themeIcon) {
                themeIcon.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
            }
            if (themeText) themeText.textContent = 'Dark';
        }
    }

    // ==========================================================================
    // Tab Navigation
    // ==========================================================================
    const tabBtnStudio = document.getElementById('tabBtnStudio');
    const tabBtnHistory = document.getElementById('tabBtnHistory');
    const studioView = document.getElementById('studioView');
    const historyView = document.getElementById('historyView');
    const btnJumpToRegistry = document.getElementById('btnJumpToRegistry');

    function switchView(viewName) {
        if (viewName === 'history') {
            tabBtnHistory.classList.add('active');
            tabBtnStudio.classList.remove('active');
            studioView.style.display = 'none';
            historyView.style.display = 'block';
            loadPatientsHistory();
        } else {
            tabBtnStudio.classList.add('active');
            tabBtnHistory.classList.remove('active');
            studioView.style.display = 'block';
            historyView.style.display = 'none';
        }
    }

    if (tabBtnStudio) tabBtnStudio.addEventListener('click', () => switchView('studio'));
    if (tabBtnHistory) tabBtnHistory.addEventListener('click', () => switchView('history'));
    if (btnJumpToRegistry) btnJumpToRegistry.addEventListener('click', () => switchView('history'));

    // ==========================================================================
    // View Mode Toggle (Cards vs Table)
    // ==========================================================================
    const btnModeCards = document.getElementById('btnModeCards');
    const btnModeTable = document.getElementById('btnModeTable');
    const patientCardsGrid = document.getElementById('patientCardsGrid');
    const patientTableContainer = document.getElementById('patientTableContainer');

    function setViewMode(mode) {
        currentViewMode = mode;
        if (mode === 'table') {
            btnModeTable.classList.add('active');
            btnModeCards.classList.remove('active');
            patientCardsGrid.style.display = 'none';
            patientTableContainer.style.display = 'block';
        } else {
            btnModeCards.classList.add('active');
            btnModeTable.classList.remove('active');
            patientCardsGrid.style.display = 'grid';
            patientTableContainer.style.display = 'none';
        }
        renderPatientRecords(currentPatientsData);
    }

    if (btnModeCards) btnModeCards.addEventListener('click', () => setViewMode('cards'));
    if (btnModeTable) btnModeTable.addEventListener('click', () => setViewMode('table'));

    // ==========================================================================
    // Patient Form & Direct Intake
    // ==========================================================================
    const patientNameInput = document.getElementById('patientNameInput');
    const patientAgeInput = document.getElementById('patientAgeInput');
    const patientGlaucomaStatus = document.getElementById('patientGlaucomaStatus');
    const toggleStatusGlaucoma = document.getElementById('toggleStatusGlaucoma');
    const toggleStatusNormal = document.getElementById('toggleStatusNormal');
    const btnSubmitPatient = document.getElementById('btnSubmitPatient');
    const btnAutoGeneratePatient = document.getElementById('btnAutoGeneratePatient');

    // Legacy fallbacks for optional elements
    const patientIdInput = document.getElementById('patientIdInput');
    const patientGenderInput = document.getElementById('patientGenderInput');
    const patientEyeInput = document.getElementById('patientEyeInput');
    const patientIopInput = document.getElementById('patientIopInput');
    const patientCdrInput = document.getElementById('patientCdrInput');
    const patientNotesInput = document.getElementById('patientNotesInput');

    function generatePatientId() {
        const randNum = Math.floor(1000 + Math.random() * 9000);
        return `GLC-2026-${randNum}`;
    }

    function setGlaucomaStatus(status) {
        const isGlaucoma = status.toLowerCase() === 'glaucoma';
        if (patientGlaucomaStatus) {
            patientGlaucomaStatus.value = isGlaucoma ? 'Glaucoma' : 'Normal';
        }
        if (toggleStatusGlaucoma && toggleStatusNormal) {
            if (isGlaucoma) {
                toggleStatusGlaucoma.classList.add('active-glaucoma');
                toggleStatusNormal.classList.remove('active-normal');
            } else {
                toggleStatusNormal.classList.add('active-normal');
                toggleStatusGlaucoma.classList.remove('active-glaucoma');
            }
        }
    }

    if (toggleStatusGlaucoma) {
        toggleStatusGlaucoma.addEventListener('click', () => setGlaucomaStatus('Glaucoma'));
    }
    if (toggleStatusNormal) {
        toggleStatusNormal.addEventListener('click', () => setGlaucomaStatus('Normal'));
    }
    if (patientGlaucomaStatus) {
        patientGlaucomaStatus.addEventListener('change', (e) => setGlaucomaStatus(e.target.value));
    }

    if (btnAutoGeneratePatient) {
        btnAutoGeneratePatient.addEventListener('click', () => {
            const sampleNames = [
                'Arthur Pendelton', 'Clara Oswald', 'Vikram Patel', 'Miriam Al-Said',
                'Jonathan Reyes', 'Dr. Beatrice Shaw', 'Sophia Lindholm', 'Robert MacIntyre',
                'Elena Rostova', 'David Chen'
            ];
            if (patientNameInput) {
                patientNameInput.value = sampleNames[Math.floor(Math.random() * sampleNames.length)];
            }
            if (patientAgeInput) {
                patientAgeInput.value = Math.floor(48 + Math.random() * 30);
            }
            const randomStatus = Math.random() > 0.45 ? 'Glaucoma' : 'Normal';
            setGlaucomaStatus(randomStatus);
            showToast('Clinical demographic profile loaded.');
        });
    }

    // ==========================================================================
    // BLE Tonometer & IOP Biomarker Logic
    // ==========================================================================
    const iopRiskBadge = document.getElementById('iopRiskBadge');
    const btnBleConnect = document.getElementById('btnBleConnect');
    const bleBtnText = document.getElementById('bleBtnText');
    const btnSyncCloudTonometer = document.getElementById('btnSyncCloudTonometer');
    const bleStatusStrip = document.getElementById('bleStatusStrip');
    const bleStatusText = document.getElementById('bleStatusText');

    function updateIopRiskBadge(val) {
        const num = parseFloat(val);
        if (isNaN(num) || !iopRiskBadge) return;
        if (num < 10.0) {
            iopRiskBadge.textContent = 'Hypotony (<10 mmHg)';
            iopRiskBadge.className = 'iop-risk-pill badge-borderline';
        } else if (num <= 21.0) {
            iopRiskBadge.textContent = 'Normal (10-21 mmHg)';
            iopRiskBadge.className = 'iop-risk-pill badge-normal';
        } else if (num <= 24.0) {
            iopRiskBadge.textContent = 'Borderline (21-24 mmHg)';
            iopRiskBadge.className = 'iop-risk-pill badge-borderline';
        } else {
            iopRiskBadge.textContent = 'High Glaucoma Risk (>24 mmHg)';
            iopRiskBadge.className = 'iop-risk-pill badge-high';
        }
    }

    if (patientIopInput) {
        patientIopInput.addEventListener('input', (e) => updateIopRiskBadge(e.target.value));
        updateIopRiskBadge(patientIopInput.value);
    }

    // Web Bluetooth API Integration
    let bleDevice = null;
    let bleServer = null;
    const TONOMETER_SERVICE_UUID = '4fafc201-1fb5-459e-8fcc-c5c9c331914b';
    const TONOMETER_CHAR_UUID = 'beb5483e-36e1-4688-b7f5-ea07361b26a8';

    if (btnBleConnect) {
        btnBleConnect.addEventListener('click', async () => {
            if (!navigator.bluetooth) {
                alert('Web Bluetooth is supported on Google Chrome, Microsoft Edge, and Android browsers. For other browsers, please use the "Cloud Sync" button to fetch live ESP32 readings via Wi-Fi!');
                return;
            }

            try {
                if (bleStatusStrip) bleStatusStrip.className = 'ble-status-strip connecting';
                if (bleStatusText) bleStatusText.textContent = 'Pairing with ESP32 Tonometer...';

                bleDevice = await navigator.bluetooth.requestDevice({
                    filters: [
                        { namePrefix: 'ESP32' },
                        { namePrefix: 'Tonometer' },
                        { name: 'ESP32_Tonometer' }
                    ],
                    optionalServices: [TONOMETER_SERVICE_UUID, 'battery_service', 'environmental_sensing']
                });

                if (bleStatusText) bleStatusText.textContent = `Connecting to ${bleDevice.name || 'ESP32'}...`;
                bleDevice.addEventListener('gattserverdisconnected', onBleDisconnected);

                bleServer = await bleDevice.gatt.connect();

                let service;
                try {
                    service = await bleServer.getPrimaryService(TONOMETER_SERVICE_UUID);
                } catch (e) {
                    const services = await bleServer.getPrimaryServices();
                    if (services.length > 0) service = services[0];
                }

                if (service) {
                    const characteristics = await service.getCharacteristics();
                    for (const char of characteristics) {
                        if (char.properties.notify || char.properties.read) {
                            try {
                                await char.startNotifications();
                                char.addEventListener('characteristicvaluechanged', (evt) => {
                                    const valStr = new TextDecoder().decode(evt.target.value).trim();
                                    const parsedIop = parseFloat(valStr);
                                    if (!isNaN(parsedIop)) {
                                        if (patientIopInput) {
                                            patientIopInput.value = parsedIop.toFixed(1);
                                            updateIopRiskBadge(parsedIop);
                                        }
                                        if (bleStatusText) {
                                            bleStatusText.textContent = `Live BLE: ${parsedIop.toFixed(1)} mmHg (${bleDevice.name || 'ESP32'})`;
                                        }
                                    }
                                });
                            } catch (err) {
                                console.warn('Notification start error:', err);
                            }
                        }
                    }
                }

                if (bleStatusStrip) bleStatusStrip.className = 'ble-status-strip connected';
                if (btnBleConnect) {
                    btnBleConnect.classList.add('connected');
                    if (bleBtnText) bleBtnText.textContent = 'BLE Connected';
                }
                if (bleStatusText) bleStatusText.textContent = `Connected: ${bleDevice.name || 'ESP32'} • Live IOP streaming`;
                showToast(`✅ BLE Tonometer connected! Streaming pressure data.`);

            } catch (err) {
                console.error('BLE connection error:', err);
                onBleDisconnected();
                if (err.name !== 'NotFoundError') {
                    showToast(`BLE: ${err.message}`);
                }
            }
        });
    }

    function onBleDisconnected() {
        if (bleStatusStrip) bleStatusStrip.className = 'ble-status-strip';
        if (btnBleConnect) {
            btnBleConnect.classList.remove('connected');
            if (bleBtnText) bleBtnText.textContent = 'Connect BLE';
        }
        if (bleStatusText) bleStatusText.textContent = 'BLE Tonometer: Disconnected';
    }

    // Cloud Sync from ESP32 Backend
    if (btnSyncCloudTonometer) {
        btnSyncCloudTonometer.addEventListener('click', async () => {
            try {
                btnSyncCloudTonometer.disabled = true;
                const res = await fetch('/api/tonometer/latest');
                const data = await res.json();
                if (data.success && data.reading) {
                    const iopVal = data.reading.iop || 18.0;
                    if (patientIopInput) {
                        patientIopInput.value = iopVal;
                        updateIopRiskBadge(iopVal);
                    }
                    if (bleStatusText) {
                        const timeStr = data.reading.timestamp ? new Date(data.reading.timestamp).toLocaleTimeString() : 'Recent';
                        bleStatusText.textContent = `Cloud Synced: ${iopVal} mmHg (${data.reading.device_id || 'ESP32'} @ ${timeStr})`;
                    }
                    showToast(`Cloud Sync: ${iopVal} mmHg received from ESP32!`);
                } else {
                    showToast('No active cloud reading yet.');
                }
            } catch (e) {
                console.error('Sync tonometer error:', e);
                showToast('Failed to fetch from cloud.');
            } finally {
                btnSyncCloudTonometer.disabled = false;
            }
        });
    }

    // Direct submit to Patient List
    if (btnSubmitPatient) {
        btnSubmitPatient.addEventListener('click', async () => {
            const name = patientNameInput ? patientNameInput.value.trim() : '';
            if (!name) {
                alert('Please enter the patient full name.');
                if (patientNameInput) patientNameInput.focus();
                return;
            }

            const ageVal = patientAgeInput ? patientAgeInput.value.trim() : '';
            const age = parseInt(ageVal, 10) || 50;
            if (age < 1 || age > 125) {
                alert('Please enter a valid age between 1 and 125.');
                if (patientAgeInput) patientAgeInput.focus();
                return;
            }

            const status = patientGlaucomaStatus ? patientGlaucomaStatus.value : 'Glaucoma';
            const isGlaucoma = (status.toLowerCase() === 'glaucoma');
            const iop = parseFloat(patientIopInput ? patientIopInput.value : 18.0) || 18.0;
            const eyeType = patientEyeInput ? patientEyeInput.value : 'OD (Right Eye)';

            btnSubmitPatient.disabled = true;
            const originalContent = btnSubmitPatient.innerHTML;
            btnSubmitPatient.innerHTML = `
                <div class="spinner-ring" style="width: 18px; height: 18px; border-width: 2px;"></div>
                <span>Adding to Patient List...</span>
            `;

            try {
                const res = await fetch('/api/patients', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        patient_name: name,
                        age: age,
                        status: status,
                        glaucoma_present: isGlaucoma,
                        iop: iop,
                        eye_type: eyeType
                    })
                });

                const data = await res.json();
                if (data.success) {
                    showToast(`✅ Patient ${name} added with IOP ${iop} mmHg!`);
                    
                    // Reset input fields
                    if (patientNameInput) patientNameInput.value = '';
                    if (patientAgeInput) patientAgeInput.value = '60';

                    // Update navigation counters
                    updateNavBadges();

                    // Switch immediately to Patient History & Glaucoma Registry view
                    switchView('history');
                } else {
                    alert('Error adding patient: ' + (data.message || 'Unknown error'));
                }
            } catch (err) {
                console.error('Submit patient error:', err);
                alert('Failed to connect to server: ' + err.message);
            } finally {
                btnSubmitPatient.disabled = false;
                btnSubmitPatient.innerHTML = originalContent;
            }
        });
    }

    // Allow Enter key to trigger submit
    [patientNameInput, patientAgeInput].forEach(inp => {
        if (inp) {
            inp.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (btnSubmitPatient) btnSubmitPatient.click();
                }
            });
        }
    });

    // ==========================================================================
    // Sample Scan Loader Buttons
    // ==========================================================================
    const btnLoadGlaucomaSample = document.getElementById('btnLoadGlaucomaSample');
    const btnLoadNormalSample = document.getElementById('btnLoadNormalSample');

    async function loadSampleScan(url, filename, expectedCls) {
        try {
            showToast('Loading reference clinical fundus scan...');
            const res = await fetch(url);
            const blob = await res.blob();
            const file = new File([blob], filename, { type: 'image/jpeg' });
            handleFileSelect(file);

            const expectedClass = document.getElementById('expectedClass');
            if (expectedClass && expectedCls) {
                expectedClass.value = expectedCls;
            }
        } catch (e) {
            console.error('Failed to load sample image:', e);
            alert('Could not load sample image: ' + e.message);
        }
    }

    if (btnLoadGlaucomaSample) {
        btnLoadGlaucomaSample.addEventListener('click', () => {
            loadSampleScan('/static/sample_glaucoma.jpg', 'reference_glaucoma_scan.jpg', 'Glaucoma');
        });
    }

    if (btnLoadNormalSample) {
        btnLoadNormalSample.addEventListener('click', () => {
            loadSampleScan('/static/sample_normal.jpg', 'reference_normal_scan.jpg', 'Normal');
        });
    }

    // ==========================================================================
    // Upload Studio Elements & Dropzone
    // ==========================================================================
    const dropArea = document.getElementById('dropArea');
    const imageInput = document.getElementById('imageInput');
    const dropEmptyState = document.getElementById('dropEmptyState');
    const dropPreviewState = document.getElementById('dropPreviewState');
    const inputPreviewImg = document.getElementById('inputPreviewImg');
    const previewFileName = document.getElementById('previewFileName');
    const expectedClass = document.getElementById('expectedClass');
    const btnTest = document.getElementById('btnTest');
    const spinner = document.getElementById('spinner');
    const resultBox = document.getElementById('resultBox');
    const predBadge = document.getElementById('predBadge');
    const confVal = document.getElementById('confVal');
    const confMeterFill = document.getElementById('confMeterFill');
    const severitySubtitle = document.getElementById('severitySubtitle');
    const iopRiskPill = document.getElementById('iopRiskPill');
    const clinicalHintText = document.getElementById('clinicalHintText');
    const accStatus = document.getElementById('accStatus');
    const resultImage = document.getElementById('resultImage');

    if (dropArea) {
        ['dragenter', 'dragover'].forEach(name => {
            dropArea.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropArea.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(name => {
            dropArea.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropArea.classList.remove('dragover');
            });
        });

        dropArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleFileSelect(files[0]);
            }
        });
    }

    if (imageInput) {
        imageInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }

    window.addEventListener('paste', (e) => {
        const items = e.clipboardData.items;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                handleFileSelect(blob);
                break;
            }
        }
    });

    function handleFileSelect(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid fundus image file (JPG, PNG, WEBP).');
            return;
        }

        selectedFile = file;

        const reader = new FileReader();
        reader.onload = (e) => {
            inputPreviewImg.src = e.target.result;
            previewFileName.textContent = file.name || 'Retinal_Scan.jpg';
            dropEmptyState.style.display = 'none';
            dropPreviewState.style.display = 'flex';
            btnTest.disabled = false;
            resultBox.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }

    // ==========================================================================
    // Run AI Inference & Store Patient Record
    // ==========================================================================
    btnTest.addEventListener('click', async () => {
        if (!selectedFile) return;

        btnTest.disabled = true;
        spinner.style.display = 'block';
        resultBox.style.display = 'none';
        accStatus.style.display = 'none';

        if (confMeterFill) confMeterFill.style.width = '0%';

        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('patient_id', patientIdInput ? patientIdInput.value.trim() : '');
        formData.append('patient_name', patientNameInput ? patientNameInput.value.trim() : '');
        formData.append('age', patientAgeInput ? patientAgeInput.value.trim() : '');
        formData.append('gender', patientGenderInput ? patientGenderInput.value : '');
        formData.append('eye_type', patientEyeInput ? patientEyeInput.value : '');
        formData.append('iop', patientIopInput ? patientIopInput.value.trim() : '');
        formData.append('cup_disc_ratio', patientCdrInput ? patientCdrInput.value.trim() : '');
        formData.append('notes', patientNotesInput ? patientNotesInput.value.trim() : '');
        if (expectedClass && expectedClass.value) {
            formData.append('expected_class', expectedClass.value);
        }

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                const isGlaucoma = data.prediction.toLowerCase() === 'glaucoma';
                const isNormal = data.prediction.toLowerCase() === 'normal';

                predBadge.innerHTML = (isGlaucoma ? '⚠️ ' : (isNormal ? '✅ ' : '')) + data.prediction;
                predBadge.className = 'classification-badge ' + (isGlaucoma ? 'glaucoma' : (isNormal ? 'normal' : ''));
                confVal.textContent = `${data.confidence}%`;
                resultImage.src = data.image_url;

                if (severitySubtitle) {
                    severitySubtitle.textContent = data.severity || (isGlaucoma ? 'Pathological Glaucomatous Signs' : 'Normal Physiological Retina');
                }

                // Check IOP value
                const iopVal = parseFloat(patientIopInput ? patientIopInput.value : 18.0) || 18.0;
                if (iopRiskPill) {
                    if (iopVal >= 22.0) {
                        iopRiskPill.textContent = `${iopVal} mmHg ⚠️ High Risk`;
                        iopRiskPill.className = 'biomarker-chip high';
                    } else {
                        iopRiskPill.textContent = `${iopVal} mmHg Normal Range`;
                        iopRiskPill.className = 'biomarker-chip normal';
                    }
                }

                if (clinicalHintText) {
                    const cdrVal = parseFloat(patientCdrInput ? patientCdrInput.value : 0.5) || 0.5;
                    clinicalHintText.textContent = `CDR: ${cdrVal.toFixed(2)} • ${cdrVal > 0.6 ? 'Abnormal Cup-to-Disc cupping' : 'Physiological disc cup'}`;
                }

                // Animate meter
                if (confMeterFill) {
                    setTimeout(() => {
                        confMeterFill.style.width = `${Math.min(100, Math.max(5, data.confidence))}%`;
                    }, 50);
                }

                // Accuracy match check
                const expected = expectedClass.value;
                if (expected) {
                    accStatus.style.display = 'block';
                    if (expected.toLowerCase() === data.prediction.toLowerCase()) {
                        accStatus.className = 'accuracy-banner correct';
                        accStatus.innerHTML = `✅ <strong>Diagnostic Verification Concordant:</strong> Model classified <strong>${data.prediction}</strong> (${data.confidence}%), matching actual ground truth.`;
                    } else {
                        accStatus.className = 'accuracy-banner incorrect';
                        accStatus.innerHTML = `❌ <strong>Diagnostic Verification Discordant:</strong> Model predicted <strong>${data.prediction}</strong> (${data.confidence}%), expected <strong>${expected}</strong>.`;
                    }
                }

                resultBox.style.display = 'block';
                showToast(`Record cataloged for ${data.patient_record.patient_name} (${data.patient_record.patient_id})`);

                // Prepare next patient ID
                if (patientIdInput) {
                    patientIdInput.value = generatePatientId();
                }

                updateNavBadges();

                setTimeout(() => {
                    resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }, 100);
            } else {
                alert('Prediction error: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            console.error('Inference error:', err);
            alert('Failed to connect to backend server. Make sure the server is running.');
        } finally {
            spinner.style.display = 'none';
            btnTest.disabled = false;
        }
    });

    // ==========================================================================
    // Patient History & Glaucoma Registry Functions
    // ==========================================================================
    const patientTableBody = document.getElementById('patientTableBody');
    const patientEmptyState = document.getElementById('patientEmptyState');
    const patientListCount = document.getElementById('patientListCount');
    const currentListHeading = document.getElementById('currentListHeading');
    const statGlaucomaCount = document.getElementById('statGlaucomaCount');
    const statGlaucomaPct = document.getElementById('statGlaucomaPct');
    const statTotalCount = document.getElementById('statTotalCount');
    const statAvgConf = document.getElementById('statAvgConf');
    const statHighIopCount = document.getElementById('statHighIopCount');
    const navGlaucomaCount = document.getElementById('navGlaucomaCount');
    const patientSearchInput = document.getElementById('patientSearchInput');
    const btnClearSearch = document.getElementById('btnClearSearch');
    const patientSortSelect = document.getElementById('patientSortSelect');
    const btnRefreshHistory = document.getElementById('btnRefreshHistory');
    const btnExportCsv = document.getElementById('btnExportCsv');
    const btnSeedGlaucomaData = document.getElementById('btnSeedGlaucomaData');

    // Filter Pills
    const filterGlaucoma = document.getElementById('filterGlaucoma');
    const filterAll = document.getElementById('filterAll');
    const filterNormal = document.getElementById('filterNormal');

    [filterGlaucoma, filterAll, filterNormal].forEach(pill => {
        if (!pill) return;
        pill.addEventListener('click', () => {
            [filterGlaucoma, filterAll, filterNormal].forEach(p => p && p.classList.remove('active'));
            pill.classList.add('active');
            currentFilter = pill.getAttribute('data-filter');
            loadPatientsHistory();
        });
    });

    // Keyboard shortcut '/' to search
    window.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== patientSearchInput && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
            e.preventDefault();
            switchView('history');
            if (patientSearchInput) {
                patientSearchInput.focus();
                patientSearchInput.select();
            }
        }
    });

    if (patientSearchInput) {
        let debounceTimer = null;
        patientSearchInput.addEventListener('input', (e) => {
            currentSearch = e.target.value.trim();
            btnClearSearch.style.display = currentSearch ? 'block' : 'none';
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                loadPatientsHistory();
            }, 250);
        });
    }

    if (btnClearSearch) {
        btnClearSearch.addEventListener('click', () => {
            patientSearchInput.value = '';
            currentSearch = '';
            btnClearSearch.style.display = 'none';
            loadPatientsHistory();
        });
    }

    if (patientSortSelect) {
        patientSortSelect.addEventListener('change', (e) => {
            currentSort = e.target.value;
            loadPatientsHistory();
        });
    }

    if (btnRefreshHistory) {
        btnRefreshHistory.addEventListener('click', () => {
            loadPatientsHistory();
            showToast('Patient registry synchronizing with database...');
        });
    }

    if (btnExportCsv) {
        btnExportCsv.addEventListener('click', () => {
            window.location.href = '/api/export-patients';
            showToast('Downloading CSV patient registry...');
        });
    }

    if (btnSeedGlaucomaData) {
        btnSeedGlaucomaData.addEventListener('click', async () => {
            try {
                showToast('Seeding historical Glaucoma records...');
                const res = await fetch('/api/seed-historical-glaucoma', { method: 'POST' });
                const d = await res.json();
                if (d.success) {
                    showToast(d.message);
                    loadPatientsHistory();
                }
            } catch (err) {
                console.error('Seeding error:', err);
            }
        });
    }

    async function loadPatientsHistory() {
        try {
            const url = `/api/patients?disease=${encodeURIComponent(currentFilter)}&search=${encodeURIComponent(currentSearch)}&sort=${encodeURIComponent(currentSort)}`;
            const res = await fetch(url);
            const data = await res.json();

            if (data.success) {
                currentPatientsData = data.records;
                renderStatistics(data.stats);
                renderPatientRecords(data.records);
            }
        } catch (err) {
            console.error('Failed to load patient history:', err);
        }
    }

    function renderStatistics(stats) {
        if (!stats) return;
        if (statGlaucomaCount) statGlaucomaCount.textContent = stats.glaucoma_count;
        if (statTotalCount) statTotalCount.textContent = stats.total;
        if (statAvgConf) statAvgConf.textContent = `${stats.avg_confidence}%`;
        if (statHighIopCount) statHighIopCount.textContent = stats.high_risk_iop_count;

        if (statGlaucomaPct) {
            const pct = stats.total > 0 ? Math.round((stats.glaucoma_count / stats.total) * 100) : 0;
            statGlaucomaPct.textContent = `${pct}% of screened cases`;
        }

        if (navGlaucomaCount) {
            navGlaucomaCount.textContent = `${stats.glaucoma_count} Glaucoma Cases`;
        }
    }

    function renderPatientRecords(records) {
        if (currentListHeading) {
            if (currentFilter === 'glaucoma') {
                currentListHeading.textContent = 'Showing Previous Glaucoma Patients';
            } else if (currentFilter === 'normal') {
                currentListHeading.textContent = 'Showing Healthy Normal Eye Cases';
            } else {
                currentListHeading.textContent = 'Showing All Screened Patients';
            }
        }

        if (patientListCount) {
            patientListCount.textContent = `${records.length} records`;
        }

        if (records.length === 0) {
            patientCardsGrid.style.display = 'none';
            patientTableContainer.style.display = 'none';
            patientEmptyState.style.display = 'block';
            return;
        }

        patientEmptyState.style.display = 'none';

        if (currentViewMode === 'table') {
            patientCardsGrid.style.display = 'none';
            patientTableContainer.style.display = 'block';
            renderTableView(records);
        } else {
            patientTableContainer.style.display = 'none';
            patientCardsGrid.style.display = 'grid';
            renderCardsView(records);
        }
    }

    function renderCardsView(records) {
        if (!patientCardsGrid) return;
        patientCardsGrid.innerHTML = '';

        records.forEach(p => {
            const isGlaucoma = (p.prediction || '').toLowerCase() === 'glaucoma';
            const card = document.createElement('div');
            card.className = `patient-card ${isGlaucoma ? 'glaucoma-card' : 'normal-card'}`;

            let formattedDate = 'Recently';
            if (p.timestamp) {
                try {
                    const d = new Date(p.timestamp);
                    formattedDate = d.toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                    }) + ' • ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
                } catch (e) {
                    formattedDate = p.timestamp.substring(0, 10);
                }
            }

            const initials = (p.patient_name || 'PT')
                .split(' ')
                .map(n => n[0])
                .slice(0, 2)
                .join('')
                .toUpperCase();

            const iopVal = parseFloat(p.iop) || 18.0;
            const isHighIop = iopVal >= 22.0;
            const thumbSrc = p.thumbnail || '/static/sample_glaucoma.jpg';

            card.innerHTML = `
                <div class="card-top">
                    <div class="patient-avatar" title="${isGlaucoma ? 'Glaucoma Positive' : 'Normal Retina'}">
                        ${initials}
                    </div>
                    <div class="patient-details">
                        <span class="patient-id-tag copy-id" data-copy="${escapeHtml(p.patient_id)}" title="Click to copy ID">${escapeHtml(p.patient_id || 'ID-UNKNOWN')}</span>
                        <h4 class="patient-name-heading">${escapeHtml(p.patient_name || 'Anonymous Patient')}</h4>
                        <span class="patient-sub-info">${p.age || '55'} yrs &bull; ${p.gender || 'Clinical'} &bull; <strong>${p.eye_type || 'OD'}</strong></span>
                    </div>
                </div>

                <div class="card-middle">
                    <div class="card-thumb-frame" title="Click to view high-resolution scan">
                        <img src="${thumbSrc}" alt="Fundus Scan">
                    </div>
                    <div class="card-vitals-stack">
                        <div class="diag-pill-compact ${isGlaucoma ? 'glaucoma' : 'normal'}">
                            <span class="indicator-dot ${isGlaucoma ? 'pulse-rose' : 'pulse-emerald'}"></span>
                            <span>${isGlaucoma ? 'Glaucoma' : 'Normal'}</span> &bull; ${p.confidence || 95}%
                        </div>
                        <div class="vitals-line">
                            <span>IOP:</span>
                            <span class="pressure-pill ${isHighIop ? 'high' : 'healthy'}">${iopVal} mmHg ${isHighIop ? '(High)' : ''}</span>
                        </div>
                        <div class="vitals-line">
                            <span>CDR:</span>
                            <strong>${p.cup_disc_ratio || '0.50'}</strong>
                        </div>
                    </div>
                </div>

                <div class="card-bottom">
                    <span class="time-stamp">${formattedDate}</span>
                    <div class="card-button-cluster">
                        <button type="button" class="btn-open-report" data-id="${p.id || p.patient_id}">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                                <line x1="16" y1="13" x2="8" y2="13"></line>
                                <line x1="16" y1="17" x2="8" y2="17"></line>
                            </svg>
                            <span>Report</span>
                        </button>
                        <button type="button" class="btn-delete-row" data-id="${p.id || p.patient_id}" title="Delete Record">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            `;

            patientCardsGrid.appendChild(card);
        });

        attachCardEventHandlers();
    }

    function renderTableView(records) {
        if (!patientTableBody) return;
        patientTableBody.innerHTML = '';

        records.forEach(p => {
            const isGlaucoma = (p.prediction || '').toLowerCase() === 'glaucoma';
            const iopVal = parseFloat(p.iop) || 18.0;
            const isHighIop = iopVal >= 22.0;

            let formattedDate = 'Recently';
            if (p.timestamp) {
                try {
                    const d = new Date(p.timestamp);
                    formattedDate = d.toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                    });
                } catch (e) {
                    formattedDate = p.timestamp.substring(0, 10);
                }
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong class="mono-code copy-id" data-copy="${escapeHtml(p.patient_id)}" style="cursor:pointer;" title="Click to copy">${escapeHtml(p.patient_id)}</strong></td>
                <td><strong>${escapeHtml(p.patient_name || 'Anonymous')}</strong></td>
                <td>${p.age || 50} yrs</td>
                <td>
                    <span class="diag-pill-compact ${isGlaucoma ? 'glaucoma' : 'normal'}">
                        <span class="indicator-dot ${isGlaucoma ? 'pulse-rose' : 'pulse-emerald'}"></span>
                        <span>${isGlaucoma ? 'Glaucoma' : 'Normal'}</span>
                    </span>
                </td>
                <td><strong>${p.confidence || 95}%</strong></td>
                <td><span class="pressure-pill ${isHighIop ? 'high' : 'healthy'}">${iopVal} mmHg</span></td>
                <td>${p.cup_disc_ratio || '0.50'}</td>
                <td>${formattedDate}</td>
                <td class="text-right">
                    <button type="button" class="btn-open-report" data-id="${p.id || p.patient_id}">Report</button>
                    <button type="button" class="btn-delete-row" data-id="${p.id || p.patient_id}" title="Delete" style="display:inline-flex;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </td>
            `;

            patientTableBody.appendChild(tr);
        });

        attachCardEventHandlers();
    }

    function attachCardEventHandlers() {
        document.querySelectorAll('.btn-open-report').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                openPatientModal(id);
            });
        });

        document.querySelectorAll('.btn-delete-row').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                if (confirm(`Are you sure you want to delete patient record ${id}?`)) {
                    await deletePatientRecord(id);
                }
            });
        });

        document.querySelectorAll('.copy-id').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const text = el.getAttribute('data-copy');
                if (text && navigator.clipboard) {
                    navigator.clipboard.writeText(text);
                    showToast(`Copied ${text} to clipboard!`);
                }
            });
        });
    }

    async function deletePatientRecord(id) {
        try {
            const res = await fetch(`/api/patients/${encodeURIComponent(id)}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                showToast('Record deleted successfully.');
                loadPatientsHistory();
                updateNavBadges();
            }
        } catch (err) {
            console.error('Delete error:', err);
            alert('Failed to delete record: ' + err.message);
        }
    }

    // ==========================================================================
    // Patient Clinical Report Modal
    // ==========================================================================
    const patientModal = document.getElementById('patientModal');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnCloseModalBtn = document.getElementById('btnCloseModalBtn');
    const btnPrintReport = document.getElementById('btnPrintReport');
    const btnDeleteRecord = document.getElementById('btnDeleteRecord');

    const modalReportId = document.getElementById('modalReportId');
    const modalPatientName = document.getElementById('modalPatientName');
    const modalScanDate = document.getElementById('modalScanDate');
    const modalPatientImage = document.getElementById('modalPatientImage');
    const modalImageEye = document.getElementById('modalImageEye');
    const modalImageDetections = document.getElementById('modalImageDetections');
    const modalPatientId = document.getElementById('modalPatientId');
    const modalPatientAgeSex = document.getElementById('modalPatientAgeSex');
    const modalPatientEye = document.getElementById('modalPatientEye');
    const modalPatientFilename = document.getElementById('modalPatientFilename');
    const modalDiagnosisBanner = document.getElementById('modalDiagnosisBanner');
    const modalDiagStatus = document.getElementById('modalDiagStatus');
    const modalDiagConfidence = document.getElementById('modalDiagConfidence');
    const modalDiagSeverity = document.getElementById('modalDiagSeverity');
    const modalPatientIop = document.getElementById('modalPatientIop');
    const modalIopStatus = document.getElementById('modalIopStatus');
    const modalPatientCdr = document.getElementById('modalPatientCdr');
    const modalCdrStatus = document.getElementById('modalCdrStatus');
    const modalClinicalNotes = document.getElementById('modalClinicalNotes');
    const modalRecList = document.getElementById('modalRecList');

    async function openPatientModal(recordId) {
        activeModalPatientId = recordId;
        try {
            const res = await fetch(`/api/patients/${encodeURIComponent(recordId)}`);
            const data = await res.json();
            if (!data.success || !data.patient) {
                alert('Could not find patient record.');
                return;
            }

            const p = data.patient;
            const isGlaucoma = (p.prediction || '').toLowerCase() === 'glaucoma';

            if (modalReportId) modalReportId.textContent = `REPORT #${(p.patient_id || '2026-000').toUpperCase()}`;
            if (modalPatientName) modalPatientName.textContent = p.patient_name || 'Patient Summary';

            let dateStr = 'October 18, 2026';
            if (p.timestamp) {
                try {
                    dateStr = new Date(p.timestamp).toLocaleString();
                } catch (e) {
                    dateStr = p.timestamp;
                }
            }
            if (modalScanDate) modalScanDate.textContent = `Retinal examination recorded on ${dateStr}`;

            if (modalPatientImage) {
                modalPatientImage.src = p.image_url || p.thumbnail || '/static/sample_glaucoma.jpg';
            }
            if (modalImageEye) modalImageEye.textContent = p.eye_type || 'OD (Right Eye)';
            if (modalImageDetections) {
                const count = p.detections_count || (p.detections ? p.detections.length : 1);
                modalImageDetections.textContent = `${count} YOLO Detection Box${count > 1 ? 'es' : ''}`;
            }

            if (modalPatientId) modalPatientId.textContent = p.patient_id || 'N/A';
            if (modalPatientAgeSex) modalPatientAgeSex.textContent = `${p.age || 50} Years / ${p.gender || 'Unspecified'}`;
            if (modalPatientEye) modalPatientEye.textContent = p.eye_type || 'OD (Right Eye)';
            if (modalPatientFilename) modalPatientFilename.textContent = p.filename || 'fundus_scan.jpg';

            if (modalDiagnosisBanner) {
                modalDiagnosisBanner.className = `diagnosis-lead-card ${isGlaucoma ? 'glaucoma' : 'normal'}`;
            }
            if (modalDiagStatus) modalDiagStatus.textContent = isGlaucoma ? '⚠️ Glaucoma Confirmed' : '✅ Normal Retina';
            if (modalDiagConfidence) modalDiagConfidence.textContent = `${p.confidence || 0}% AI Certainty`;
            if (modalDiagSeverity) {
                modalDiagSeverity.textContent = p.severity || (isGlaucoma ? 'Pathological Glaucomatous Cupping' : 'Healthy Retina');
            }

            const iopVal = parseFloat(p.iop) || 18.0;
            if (modalPatientIop) modalPatientIop.innerHTML = `${iopVal} <small>mmHg</small>`;
            if (modalIopStatus) {
                if (iopVal >= 22.0) {
                    modalIopStatus.textContent = '⚠️ Elevated Intraocular Pressure';
                    modalIopStatus.className = 'cell-alert alert-danger';
                } else {
                    modalIopStatus.textContent = '✅ Normal Physiological Pressure';
                    modalIopStatus.className = 'cell-alert alert-healthy';
                }
            }

            const cdrVal = parseFloat(p.cup_disc_ratio) || 0.5;
            if (modalPatientCdr) modalPatientCdr.textContent = cdrVal.toFixed(2);
            if (modalCdrStatus) {
                if (cdrVal >= 0.6) {
                    modalCdrStatus.textContent = '⚠️ Significant Optic Cupping (>0.6)';
                    modalCdrStatus.className = 'cell-alert alert-danger';
                } else {
                    modalCdrStatus.textContent = '✅ Normal Physiological Cup';
                    modalCdrStatus.className = 'cell-alert alert-healthy';
                }
            }

            if (modalClinicalNotes) {
                modalClinicalNotes.textContent = p.notes || 'No previous clinical abnormalities documented.';
            }

            if (modalRecList) {
                if (isGlaucoma) {
                    modalRecList.innerHTML = `
                        <li>Schedule Humphrey Visual Field Analyzer 24-2 to map peripheral scotoma</li>
                        <li>Perform Gonioscopy to evaluate open vs closed iridocorneal angle</li>
                        <li>Initiate topical hypotensive prostaglandin analog drops (e.g. Latanoprost) as indicated</li>
                        <li>Schedule 4-week follow-up for diurnal IOP curve assessment</li>
                    `;
                } else {
                    modalRecList.innerHTML = `
                        <li>Optic nerve head within physiological limits obeying the ISNT rule</li>
                        <li>Continue routine annual ophthalmology screening examination</li>
                        <li>Maintain baseline optic disc photography for longitudinal comparison</li>
                    `;
                }
            }

            patientModal.style.display = 'flex';
        } catch (err) {
            console.error('Error fetching patient detail:', err);
        }
    }

    function closePatientModal() {
        if (patientModal) patientModal.style.display = 'none';
        activeModalPatientId = null;
    }

    if (btnCloseModal) btnCloseModal.addEventListener('click', closePatientModal);
    if (btnCloseModalBtn) btnCloseModalBtn.addEventListener('click', closePatientModal);
    if (patientModal) {
        patientModal.addEventListener('click', (e) => {
            if (e.target === patientModal) closePatientModal();
        });
    }

    if (btnPrintReport) {
        btnPrintReport.addEventListener('click', () => {
            window.print();
        });
    }

    if (btnDeleteRecord) {
        btnDeleteRecord.addEventListener('click', async () => {
            if (activeModalPatientId && confirm('Delete this patient clinical record?')) {
                await deletePatientRecord(activeModalPatientId);
                closePatientModal();
            }
        });
    }

    // ==========================================================================
    // DB Status & Badge Sync
    // ==========================================================================
    async function updateNavBadges() {
        try {
            const res = await fetch('/api/db-status');
            const data = await res.json();
            const dbStatusText = document.getElementById('dbStatusText');

            if (data.status === 'connected') {
                if (dbStatusText) dbStatusText.textContent = `MongoDB Connected (${data.glaucoma_records || 0} Glaucoma)`;
            } else {
                if (dbStatusText) dbStatusText.textContent = 'High-Availability Local DB';
            }

            if (navGlaucomaCount && data.glaucoma_records !== undefined) {
                navGlaucomaCount.textContent = `${data.glaucoma_records} Glaucoma Cases`;
            }
        } catch (e) {
            console.warn('DB Status check:', e);
        }
    }

    // ==========================================================================
    // Toast Notification Utility
    // ==========================================================================
    function showToast(msg, duration = 3000) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = 'toast-message';
        toast.textContent = msg;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Startup initializations
    updateNavBadges();
    loadPatientsHistory();
});
