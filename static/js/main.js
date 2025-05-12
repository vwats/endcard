// Main JavaScript for EndCard Converter Pro

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const portraitFileInput = document.getElementById('portrait-file-input');
    const landscapeFileInput = document.getElementById('landscape-file-input');
    const uploadButton = document.getElementById('combined-upload-btn');
    const uploadForm = document.getElementById('combined-upload-form');
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultsContainer = document.getElementById('results-container');
    const errorContainer = document.getElementById('error-container');
    const errorMessage = document.getElementById('error-message');
    const clearFileBtn = document.getElementById('clear-file-btn');
    const mediaPreview = document.getElementById('media-preview');
    const videoPreview = document.getElementById('video-preview');
    const previewArea = document.querySelector('.preview-area');
    const endcardPreview = document.getElementById('endcard-preview');
    const rotatePreviewBtn = document.getElementById('rotate-preview-btn');
    const previewContainer = document.getElementById('preview-container');
    const orientationStatus = document.getElementById('orientation-status');
    const downloadEndcardBtn = document.getElementById('download-endcard-btn');
    const endcardId = document.getElementById('endcard-id');

    // State
    let currentPreviewOrientation = 'portrait';
    let currentEndcardId = endcardId ? endcardId.value : null;

    // Initialize
    function init() {
        // Add event listeners
        portraitFileInput.addEventListener('change', function() {
            previewFile(this);
            checkFilesAndEnableButton();
        });

        landscapeFileInput.addEventListener('change', function() {
            previewFile(this);
            checkFilesAndEnableButton();
        });

        if (clearFileBtn) {
            clearFileBtn.addEventListener('click', clearFileSelection);
        }

        if (uploadForm) {
            uploadForm.addEventListener('submit', function(e) {
                e.preventDefault();
                processUpload();
            });
        }

        if (rotatePreviewBtn) {
            rotatePreviewBtn.addEventListener('click', togglePreviewOrientation);
        }

        if (downloadEndcardBtn) {
            downloadEndcardBtn.addEventListener('click', function() {
                if (currentEndcardId) {
                    window.location.href = `/download_template/rotatable/${currentEndcardId}`;
                }
            });
        }
    }

    // Check if both files are selected and enable button
    function checkFilesAndEnableButton() {
        if (portraitFileInput.files.length > 0 && landscapeFileInput.files.length > 0) {
            uploadButton.disabled = false;
        } else {
            uploadButton.disabled = true;
        }
    }

    // Preview the file
    function previewFile(fileInput) {
        if (fileInput.files && fileInput.files[0]) {
            const file = fileInput.files[0];
            const reader = new FileReader();

            reader.onload = function(e) {
                previewArea.classList.remove('d-none');
                
                const isVideo = file.type.startsWith('video/');
                if (isVideo) {
                    videoPreview.src = e.target.result;
                    videoPreview.classList.remove('d-none');
                    mediaPreview.classList.add('d-none');
                } else {
                    mediaPreview.src = e.target.result;
                    mediaPreview.classList.remove('d-none');
                    videoPreview.classList.add('d-none');
                }
            };

            reader.readAsDataURL(file);
        }
    }

    // Clear file selection
    function clearFileSelection() {
        portraitFileInput.value = '';
        landscapeFileInput.value = '';
        mediaPreview.src = '';
        videoPreview.src = '';
        previewArea.classList.add('d-none');
        uploadButton.disabled = true;
    }

    // Process the upload
    function processUpload() {
        // Validate files
        const portraitFile = portraitFileInput.files[0];
        const landscapeFile = landscapeFileInput.files[0];

        if (!portraitFile || !landscapeFile) {
            showError('Please select both portrait and landscape files.');
            return;
        }

        // Create form data
        const formData = new FormData();
        formData.append('portrait_file', portraitFile);
        formData.append('landscape_file', landscapeFile);
        
        // If editing an existing endcard, add its ID
        if (endcardId && endcardId.value) {
            formData.append('endcard_id', endcardId.value);
        }

        // Show loading indicator
        loadingIndicator.classList.remove('d-none');
        errorContainer.classList.add('d-none');
        resultsContainer.classList.add('d-none');

        // Send the request
        fetch('/process_upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            loadingIndicator.classList.add('d-none');
            
            if (data.success) {
                // Store endcard ID for future use
                currentEndcardId = data.endcard_id;
                
                // Update the preview iframe
                updateEndcardPreview(data);
                
                // Show results
                resultsContainer.classList.remove('d-none');
                
                // Scroll to results
                resultsContainer.scrollIntoView({behavior: 'smooth'});
            } else {
                showError(data.error);
            }
        })
        .catch(error => {
            loadingIndicator.classList.add('d-none');
            showError('An error occurred while processing your upload. Please try again.');
            console.error('Error:', error);
        });
    }

    // Show error message
    function showError(message) {
        errorContainer.classList.remove('d-none');
        errorMessage.textContent = message;
        
        // Scroll to error
        errorContainer.scrollIntoView({behavior: 'smooth'});
        
        // Hide after 10 seconds
        setTimeout(() => {
            errorContainer.classList.add('d-none');
        }, 10000);
    }

    // Toggle preview orientation
    function togglePreviewOrientation() {
        if (currentPreviewOrientation === 'portrait') {
            currentPreviewOrientation = 'landscape';
            previewContainer.classList.remove('portrait-container');
            previewContainer.classList.add('landscape-container');
            orientationStatus.textContent = 'Landscape Mode';
            orientationStatus.style.background = 'linear-gradient(45deg, #0ea5e9, #06b6d4)';
        } else {
            currentPreviewOrientation = 'portrait';
            previewContainer.classList.remove('landscape-container');
            previewContainer.classList.add('portrait-container');
            orientationStatus.textContent = 'Portrait Mode';
            orientationStatus.style.background = 'linear-gradient(45deg, #6366f1, #8b5cf6)';
        }
    }

    // Update endcard preview
    function updateEndcardPreview(data) {
        if (!endcardPreview) return;
        
        // Create a blob URL for the iframe
        const html = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                html, body {
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    background-color: black;
                }
                .media-content {
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                    display: none;
                }
                .media-content.active {
                    display: block;
                }
            </style>
        </head>
        <body>
            ${data.is_video ? `
                <video id="portrait" class="media-content active" src="${data.portrait_data_url}" autoplay loop muted playsinline></video>
                <video id="landscape" class="media-content" src="${data.landscape_data_url}" autoplay loop muted playsinline></video>
            ` : `
                <img id="portrait" class="media-content active" src="${data.portrait_data_url}" alt="Endcard">
                <img id="landscape" class="media-content" src="${data.landscape_data_url}" alt="Endcard">
            `}
            <script>
                const isPortrait = () => window.innerHeight > window.innerWidth;
                const portrait = document.getElementById('portrait');
                const landscape = document.getElementById('landscape');
                
                function updateOrientation() {
                    if (isPortrait()) {
                        portrait.classList.add('active');
                        landscape.classList.remove('active');
                    } else {
                        portrait.classList.remove('active');
                        landscape.classList.add('active');
                    }
                }
                
                window.addEventListener('resize', updateOrientation);
                updateOrientation();
            </script>
        </body>
        </html>
        `;
        
        const blob = new Blob([html], {type: 'text/html'});
        const url = URL.createObjectURL(blob);
        
        endcardPreview.src = url;
    }

    // Initialize the app
    init();
});