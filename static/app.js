document.addEventListener('DOMContentLoaded', () => {
    let selectedFile = null;

    // Theme Switcher Logic
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const themeText = document.getElementById('themeText');
    const htmlElement = document.documentElement;

    // Load saved theme or default to light
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
    const expectedClass = document.getElementById('expectedClass');
    const btnTest = document.getElementById('btnTest');
    const spinner = document.getElementById('spinner');
    const resultBox = document.getElementById('resultBox');
    const predBadge = document.getElementById('predBadge');
    const confVal = document.getElementById('confVal');
    const accStatus = document.getElementById('accStatus');
    const resultImage = document.getElementById('resultImage');
    const uploadTitle = document.getElementById('uploadTitle');

    // Click to upload
    dropArea.addEventListener('click', () => {
        imageInput.click();
    });

    // Drag and Drop
    ['dragenter', 'dragover'].forEach(name => {
        dropArea.addEventListener(name, (e) => {
            e.preventDefault();
            dropArea.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        dropArea.addEventListener(name, (e) => {
            e.preventDefault();
            dropArea.classList.remove('dragover');
        });
    });

    dropArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    imageInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid image file.');
            return;
        }
        selectedFile = file;
        if (uploadTitle) {
            uploadTitle.textContent = `Selected: ${file.name}`;
        }
        btnTest.disabled = false;
        resultBox.style.display = 'none';
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
                        accStatus.innerHTML = `✅ <strong>Accurate Prediction:</strong> Model matched actual (${expected}).`;
                    } else {
                        accStatus.className = 'accuracy-alert incorrect';
                        accStatus.innerHTML = `❌ <strong>Mismatch:</strong> Model predicted ${data.prediction}, but actual was ${expected}.`;
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
            console.error(err);
            alert('Failed to connect to backend server.');
        } finally {
            spinner.style.display = 'none';
            btnTest.disabled = false;
        }
    });
});
