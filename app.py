import os
import uuid
import threading
import time
from flask import Flask, render_template, request, send_file, jsonify, make_response
from werkzeug.utils import secure_filename
import pikepdf

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def delete_file_after_delay(filepath, delay=30):
    def remove():
        time.sleep(delay)
        if os.path.exists(filepath):
            os.remove(filepath)
    threading.Thread(target=remove).start()

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 20 MB.'}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/unlock', methods=['POST'])
def unlock_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['pdf']
    password = request.form.get('password')
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400

    original_filename = secure_filename(file.filename)
    unique_id = uuid.uuid4().hex
    input_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}_{original_filename}")
    file.save(input_path)
    delete_file_after_delay(input_path)

    try:
        with pikepdf.open(input_path, password=password) as pdf:
            output_path = os.path.join(PROCESSED_FOLDER, f"{unique_id}_unlocked_{original_filename}")
            pdf.save(output_path)
            delete_file_after_delay(output_path)

            # Build filename: originalname_unlocked.pdf
            base, ext = os.path.splitext(original_filename)
            download_name = f"{base}_unlocked{ext}"

            # Force download with correct headers
            response = make_response(send_file(output_path, as_attachment=False))
            response.headers['Content-Disposition'] = f'attachment; filename="{download_name}"'
            response.headers['Content-Type'] = 'application/octet-stream'
            return response
    except pikepdf.PasswordError:
        return jsonify({'error': 'Wrong password. Please try again.'}), 401
    except Exception as e:
        app.logger.error(f"Error processing PDF: {str(e)}")
        return jsonify({'error': 'Could not process PDF. The file might be corrupted or not a valid PDF.'}), 500

if __name__ == '__main__':
    app.run(debug=True)