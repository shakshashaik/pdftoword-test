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
 
# Static token (use env vars in prod)

STATIC_AUTH_TOKEN = os.getenv("STATIC_AUTH_TOKEN", "Wissda_101")
 
app = Flask(__name__)
 
# Create temp dir if it doesn't exist

TEMP_DIR = "/wissda/temp-docs"

if not os.path.exists(TEMP_DIR):

    os.makedirs(TEMP_DIR)
 
@app.route('/convert', methods=['POST'])

def convert_pdf_to_docx():

    # Step 1: Auth

    auth_token = request.headers.get('Authorization')

    if auth_token != STATIC_AUTH_TOKEN:

        logger.warning("Unauthorized access attempt")

        return {"error": "Unauthorized access. Invalid or missing token."}, 403
 
    # Unique temp file name

    unique_id = str(uuid.uuid4())

    pdf_temp_path = os.path.join(TEMP_DIR, f"temp_input_{unique_id}.pdf")

    docx_temp_path = os.path.join(TEMP_DIR, f"converted_output_{unique_id}.docx")
 
    try:

        # Step 2: Save incoming PDF

        if 'file' in request.files:

            file = request.files['file']

            file.save(pdf_temp_path)

            logger.info(f"📥 Received file: {file.filename}")

        else:

            with open(pdf_temp_path, 'wb') as f:

                f.write(request.data)

            logger.info(f"📥 Received binary data and saved to {pdf_temp_path}")
 
        # Step 3: Verify file exists and isn't empty

        if not os.path.exists(pdf_temp_path) or os.path.getsize(pdf_temp_path) == 0:

            logger.error("❌ Uploaded file is missing or empty.")

            return {"error": "Uploaded file is missing or empty."}, 500
 
        logger.info("✅ Temp PDF read test passed.")

        logger.info("Starting conversion...")
 
        # Step 4: Delay to avoid race condition

        time.sleep(0.5)
 
        # Step 5: Convert PDF to DOCX

        try:

            cv = Converter(pdf_temp_path)

            cv.convert(docx_temp_path, start=0, end=None)

            cv.close()

        except Exception as e:

            logger.error(f"❌ Error during conversion: {str(e)}")

            return {"error": "Conversion failed during PDF to DOCX processing."}, 500
 
        # Step 6: Send back DOCX

        logger.info("✅ Conversion successful, sending DOCX...")

        return send_file(

            docx_temp_path,

            as_attachment=True,

            download_name="converted.docx",

            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        )
 
    except Exception as e:

        logger.error(f"🔥 Unexpected error: {str(e)}")

        logger.error("Stack trace:\n" + traceback.format_exc())

        return {"error": "Unexpected server error."}, 500
 
    finally:

        # Step 7: Clean up

        for path in [pdf_temp_path, docx_temp_path]:

            try:

                if os.path.exists(path):

                    os.remove(path)

                    logger.info(f"🧹 Deleted temp file: {path}")

            except Exception as e:

                logger.warning(f"⚠️ Failed to delete {path}: {str(e)}")
 
if __name__ == '__main__':

    app.run(host="0.0.0.0", port=5000)
