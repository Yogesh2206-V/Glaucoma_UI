document.addEventListener('DOMContentLoaded', () => {
    let selectedFile = null;

    // Theme Switcher Logic
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const themeText = document.getElementById('themeText');
    const htmlElement = document.documentElement;

    const savedTheme = localStorage.getItem('oculoscan_theme') || 'light';
    applyTheme(savedTheme);

    themeToggle.addEventListener('click', () => {
        const currentTheme = htmlElement.getAttribute('data-theme');
        const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(nextTheme);
        localStorage.setItem('oculoscan_theme', nextTheme);
    });

    function applyTheme(theme) {
        htmlElement.setAttribute('data-theme', theme);
        if (theme === 'dark') {
            themeIcon.textContent = '☀️';
            themeText.textContent = 'Light';
        } else {
            themeIcon.textContent = '🌙';
            themeText.textContent = 'Dark';
        }
    }

    // UI Elements
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
    const accStatus = document.getElementById('accStatus');
    const resultImage = document.getElementById('resultImage');

    // Drag and Drop
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

    // File Input change
    imageInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Paste from clipboard support (Ctrl+V)
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
            alert('Please select a valid image file (PNG, JPG, WEBP).');
            return;
        }

        selectedFile = file;

        // Render preview inside dropzone immediately
        const reader = new FileReader();
        reader.onload = (e) => {
            inputPreviewImg.src = e.target.result;
            previewFileName.textContent = file.name || 'Pasted Image';
            dropEmptyState.style.display = 'none';
            dropPreviewState.style.display = 'flex';
            btnTest.disabled = false;
            resultBox.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }

    // Run prediction
    btnTest.addEventListener('click', async () => {
        if (!selectedFile) return;

        btnTest.disabled = true;
        spinner.style.display = 'block';
        resultBox.style.display = 'none';
        accStatus.style.display = 'none';

        const formData = new FormData();
        formData.append('image', selectedFile);

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                predBadge.textContent = data.prediction;
                predBadge.className = 'prediction-pill ' + (data.prediction.toLowerCase() === 'glaucoma' ? 'glaucoma' : 'normal');
                confVal.textContent = `${data.confidence}%`;
                resultImage.src = data.image_url;

                // Check accuracy if expected class was chosen
                const expected = expectedClass.value;
                if (expected) {
                    accStatus.style.display = 'block';
                    if (expected.toLowerCase() === data.prediction.toLowerCase()) {
                        accStatus.className = 'accuracy-alert correct';
                        accStatus.innerHTML = `✅ <strong>Accurate Match:</strong> Model correctly predicted <strong>${data.prediction}</strong> matching your actual label.`;
                    } else {
                        accStatus.className = 'accuracy-alert incorrect';
                        accStatus.innerHTML = `❌ <strong>Diagnostic Mismatch:</strong> Model predicted <strong>${data.prediction}</strong> (${data.confidence}%), but actual label is <strong>${expected}</strong>.`;
                    }
                }

                resultBox.style.display = 'block';

                // Smooth scroll to results
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
});
