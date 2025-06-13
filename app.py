from flask import Flask, request, send_file
from pdf2docx import Converter
import tempfile
import os
import logging
import traceback
import time
import fitz  # PyMuPDF for PDF text extraction

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

# Function to extract text from PDF using PyMuPDF (updated method for get_text())
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)  # Open the PDF file
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text("text")  # Extract text from each page using get_text()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
    return text

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

        # Step 4: Extract text using PyMuPDF (optional, for debugging)
        logger.info("Extracting text from PDF...")
        extracted_text = extract_text_from_pdf(pdf_temp_path)
        logger.info(f"Extracted text: {extracted_text[:500]}")  # Log first 500 characters

        # Step 5: Convert PDF → DOCX
        logger.info("Starting conversion...")
        cv = Converter(pdf_temp_path)
        try:
            cv.convert(docx_temp_path, start=0, end=None)
        except Exception as e:
            logger.error(f"Error during conversion: {str(e)}")
            return {"error": "Conversion failed due to an unexpected error during the conversion process."}, 500
        cv.close()

        # Step 6: Return DOCX file as response
        response = send_file(
            docx_temp_path,
            as_attachment=True,
            download_name="converted.docx",  # The name the file will have when downloaded
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

        logger.info(f"Response headers: {response.headers}")
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
