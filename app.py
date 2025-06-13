from flask import Flask, request, send_file
from pdf2docx import Converter
import tempfile
import os
import logging
import traceback
import time

# Set up logging
log_dir = "/wissda/azure_app_logs"  # Log directory for logging purposes
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, "app.log"),  # Store logs in the log folder
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Define static token (you can store this in environment variables for better security)
STATIC_AUTH_TOKEN = os.getenv("STATIC_AUTH_TOKEN", "Wissda_101")  # Fetch from environment variable

app = Flask(__name__)

# Create a dedicated directory for temp files (works in both App Service and Docker)
TEMP_DIR = "/wissda/temp-docs"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

@app.route('/convert', methods=['POST'])
def convert_pdf_to_docx():
    # Step 1: Validate Authentication Token
    auth_token = request.headers.get('Authorization')

    if auth_token != STATIC_AUTH_TOKEN:
        logger.warning("Unauthorized access attempt")
        return {"error": "Unauthorized access. Invalid or missing token."}, 403

    try:
        # Step 2: Create temporary files inside the /wissda/temp-docs directory
        pdf_temp_path = os.path.join(TEMP_DIR, "temp_input.pdf")
        docx_temp_path = os.path.join(TEMP_DIR, "converted_output.docx")

        # Step 3: Handle file from ServiceNow
        if 'file' in request.files:
            file = request.files['file']
            file.save(pdf_temp_path)
            logger.info(f"Received file: {file.filename}")
        else:
            # For application/pdf content-type (binary stream)
            with open(pdf_temp_path, 'wb') as f:
                f.write(request.data)
            logger.info("Received binary data")

        # Step 4: Convert PDF → DOCX using pdf2docx
        logger.info("Starting conversion...")
        try:
            # Initialize the converter with the input PDF
            cv = Converter(pdf_temp_path)
            # Perform the conversion
            cv.convert(docx_temp_path, start=0, end=None)
            # Close the converter once done
            cv.close()
        except Exception as e:
            # Log the error and return a user-friendly message
            logger.error(f"Error during conversion: {str(e)}")
            return {"error": "Conversion failed due to an error during PDF to DOCX conversion."}, 500

        # Step 5: Return DOCX file as response
        logger.info("Conversion successful, sending DOCX...")
        response = send_file(
            docx_temp_path,
            as_attachment=True,
            download_name="converted.docx",  # The name the file will have when downloaded
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

        return response

    except Exception as e:
        # Log full exception traceback
        logger.error(f"An unexpected error occurred: {str(e)}")
        logger.error("Full stack trace:\n" + traceback.format_exc())
        return {"error": f"Conversion error: {str(e)}"}, 500

    finally:
        # Cleanup temp files (Make sure to delete the files after processing)
        try:
            if os.path.exists(pdf_temp_path):
                os.remove(pdf_temp_path)
                logger.info(f"Deleted temporary PDF file: {pdf_temp_path}")
        except Exception as e:
            logger.error(f"Error deleting PDF temp file: {str(e)}")

        try:
            if os.path.exists(docx_temp_path):
                os.remove(docx_temp_path)
                logger.info(f"Deleted temporary DOCX file: {docx_temp_path}")
        except Exception as e:
            logger.error(f"Error deleting DOCX temp file: {str(e)}")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
