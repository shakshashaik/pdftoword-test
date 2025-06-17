from flask import Flask, request, send_file
from pdf2docx import Converter
import tempfile
import os
import logging
import traceback
import time
import uuid

# Set up logging
log_dir = "/wissda/azure_app_logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, "app.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

STATIC_AUTH_TOKEN = os.getenv("STATIC_AUTH_TOKEN", "Wissda_101")

app = Flask(__name__)

TEMP_DIR = "/wissda/temp-docs"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


@app.route('/convert', methods=['POST'])
def convert_pdf_to_docx():
    auth_token = request.headers.get('Authorization')
    if auth_token != STATIC_AUTH_TOKEN:
        logger.warning("Unauthorized access attempt")
        return {"error": "Unauthorized access. Invalid or missing token."}, 403

    unique_id = str(uuid.uuid4())
    pdf_temp_path = os.path.join(TEMP_DIR, f"temp_input_{unique_id}.pdf")
    docx_temp_path = os.path.join(TEMP_DIR, f"converted_output_{unique_id}.docx")

    try:
        # Step 1: Receive input
        if 'file' in request.files:
            file = request.files['file']
            file.save(pdf_temp_path)
            logger.info(f"Received multipart file: {file.filename}")
        else:
            with open(pdf_temp_path, 'wb') as f:
                f.write(request.data)
                f.flush()
                os.fsync(f.fileno())
            logger.info(f"Received binary data and saved to {pdf_temp_path}")

        # Optional delay (for Docker or FS timing)
        time.sleep(0.2)

        # Validate file readability
        try:
            with open(pdf_temp_path, 'rb') as test_file:
                test_file.read(10)
            logger.info("✅ Temp PDF read test passed.")
        except Exception as e:
            logger.error(f"❌ Temp PDF read failed: {e}")
            return {"error": "Temp file could not be read."}, 500

        # Step 2: Convert PDF to DOCX
        logger.info("Starting conversion...")
        try:
            cv = Converter(pdf_temp_path)
            cv.convert(docx_temp_path, start=0, end=None)
            cv.close()
        except Exception as e:
            logger.error(f"Error during conversion: {str(e)}")
            return {"error": "Conversion failed during PDF to DOCX processing."}, 500

        # Step 3: Send DOCX back
        logger.info("Conversion successful, sending DOCX...")
        return send_file(
            docx_temp_path,
            as_attachment=True,
            download_name="converted.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error("Stack trace:\n" + traceback.format_exc())
        return {"error": f"Conversion error: {str(e)}"}, 500

    finally:
        # Cleanup temp files
        try:
            if os.path.exists(pdf_temp_path):
                os.remove(pdf_temp_path)
                logger.info(f"Deleted temp PDF: {pdf_temp_path}")
        except Exception as e:
            logger.error(f"Failed to delete temp PDF: {e}")

        try:
            if os.path.exists(docx_temp_path):
                os.remove(docx_temp_path)
                logger.info(f"Deleted temp DOCX: {docx_temp_path}")
        except Exception as e:
            logger.error(f"Failed to delete temp DOCX: {e}")


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
