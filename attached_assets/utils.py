import os
import base64
import mimetypes
from werkzeug.utils import secure_filename
from app import app

def save_file_temporarily(file, filename):
    """Save uploaded file to temporary location and return the path"""
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return filepath

def get_file_extension(filename):
    """Get file extension from filename"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def is_image_file(filename):
    """Check if file is an image based on extension"""
    ext = get_file_extension(filename)
    return ext in {'jpg', 'jpeg', 'png', 'gif'}

def is_video_file(filename):
    """Check if file is a video based on extension"""
    ext = get_file_extension(filename)
    return ext in {'mp4', 'webm'}

def file_to_data_url(file_path):
    """Convert file to data URL format"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    with open(file_path, 'rb') as file:
        encoded = base64.b64encode(file.read()).decode('utf-8')
        
    return f"data:{mime_type};base64,{encoded}"

def cleanup_temporary_files():
    """Clean up temporary uploaded files"""
    # This could be expanded to delete old files from the uploads folder
    pass