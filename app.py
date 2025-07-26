import os
import logging
import base64
import sys
import json
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = True

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
SIGNATURE_FOLDER = os.path.join(BASE_DIR, 'static', 'signatures')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SIGNATURE_FOLDER, exist_ok=True)

# 20 MB size limit
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("webdata").sheet1
except Exception as e:
    logger.exception("Google Sheets setup failed")
    sheet = None

# Utilities
def save_images(file_list, prefix):
    paths = []
    for file in file_list:
        if file and file.filename:
            filename = secure_filename(f"{prefix}_{file.filename}")
            path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                file.save(path)
                paths.append(path)
            except Exception as e:
                logger.error(f"Could not save image {filename}: {e}")
    return paths

def save_signature(data_url, filename):
    if not data_url or "," not in data_url:
        return None
    try:
        encoded = data_url.split(',')[1]
        image_data = base64.b64decode(encoded)
        path = os.path.join(SIGNATURE_FOLDER, filename)
        with open(path, 'wb') as f:
            f.write(image_data)
        return path
    except Exception as e:
        logger.error(f"Failed to save signature: {e}")
        return None

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        fields = {k: request.form.get(k) for k in [
            'date', 'product_category', 'supplier_name', 'item_description', 'design_no',
            'colour', 'inspector_name', 'fabric_quality', 'merchandiser_name',
            'order_quantity', 'presented_quantity', 'pieces_inspected', 'sampling_range',
            'inline_inspection', 'pp_approved', 'packing_list', 'po_same', 'storage_ok',
            'carton_selected', 'total_cartons', 'inspected_cartons',
            'inspection_result', 'delivery_date', 'final_comments'
        ]}

        if sheet:
            try:
                sheet.append_row([
                    fields['date'], fields['product_category'], fields['supplier_name'],
                    fields['item_description'], fields['design_no'], fields['colour'],
                    fields['inspector_name'], fields['merchandiser_name'],
                    fields['order_quantity'], fields['presented_quantity'],
                    fields['pp_approved'], fields['delivery_date'], fields['final_comments']
                ])
                logger.info("✅ Appended row to Google Sheet.")
            except Exception as e:
                logger.warning(f"❌ Sheet write error: {e}")

        defect_types = request.form.getlist('defectType[]')
        minor_counts = request.form.getlist('minor[]')
        major_counts = request.form.getlist('major[]')
        total_minor = request.form.get('totalMinor', '0')
        total_major = request.form.get('totalMajor', '0')

        defect_images = []
        i = 0
        while True:
            files = request.files.getlist(f'defectImages_{i}[]')
            if not files or all(f.filename == '' for f in files):
                break
            paths = save_images(files, f'defect_{i}')
            defect_images.append(paths)
            i += 1

        # Save signatures
        signatures = {
            'QC Officer': save_signature(request.form.get('qc_signature'), 'qc_signature.png'),
            'Supplier': save_signature(request.form.get('supplier_signature'), 'supplier_signature.png'),
            'AQM': save_signature(request.form.get('aqm_signature'), 'aqm_signature.png'),
            'Merchandiser': save_signature(request.form.get('merch_signature'), 'merch_signature.png'),
        }

        # Collect category images
        image_groups = {
            "Factory Pictures": save_images(request.files.getlist('factory_pictures'), 'factory'),
            "Inline Pictures": save_images(request.files.getlist('inline_pictures'), 'inline'),
            "PP Sample Pictures": save_images(request.files.getlist('pp_pictures'), 'pp'),
            "Packing List Pictures": save_images(request.files.getlist('packing_list_pictures'), 'packing'),
            "PO Pictures": save_images(request.files.getlist('po_pictures'), 'po'),
            "Storage Pictures": save_images(request.files.getlist('storage_pictures'), 'storage'),
            "Carton Pictures": save_images(request.files.getlist('carton_pictures'), 'carton'),
        }

        # PDF generation
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Final Inspection Report", ln=True, align='C')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(220, 230, 255)
        pdf.cell(70, 10, "Field", 1, 0, 'L', True)
        pdf.cell(120, 10, "Value", 1, 1, 'L', True)

        pdf.set_font("Arial", '', 12)
        for k, v in fields.items():
            pdf.cell(70, 10, k.replace("_", " ").title(), 1)
            pdf.cell(120, 10, str(v or ""), 1, 1)

        # Defect section
        if defect_types:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Defects Summary", ln=True)
            pdf.set_font("Arial", '', 12)
            for i, dtype in enumerate(defect_types):
                pdf.cell(0, 10, f"{dtype}: Minor={minor_counts[i]}, Major={major_counts[i]}", ln=True)
                for img in defect_images[i]:
                    try:
                        pdf.image(img, w=70)
                        pdf.ln(5)
                    except:
                        pdf.cell(0, 10, f"Error loading image {os.path.basename(img)}", ln=True)
            pdf.cell(0, 10, f"Totals - Minor: {total_minor}, Major: {total_major}", ln=True)

        # Add all other image groups
        for title, images in image_groups.items():
            if images:
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, title, ln=True)
                for img in images:
                    try:
                        pdf.image(img, w=90)
                        pdf.ln(5)
                    except:
                        pdf.cell(0, 10, f"Could not load image: {os.path.basename(img)}", ln=True)

        # Add signatures
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Signatures", ln=True)
        for label, path in signatures.items():
            if path and os.path.exists(path):
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 10, f"{label}:", ln=True)
                try:
                    pdf.image(path, w=60)
                    pdf.ln(5)
                except:
                    pdf.cell(0, 10, f"Error loading signature for {label}", ln=True)

        # Save in memory
        pdf_output = BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)

        # Upload to Google Drive
        from drive_uploader import upload_to_drive
        try:
            filename = f"inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            temp_path = os.path.join("/tmp", filename)
            with open(temp_path, 'wb') as f:
                f.write(pdf_output.read())
            upload_to_drive(temp_path, filename, folder_id='1vQbksJZzNLmTaLkEfgtg4HErKArI-HVf')
            logger.info(f"✅ PDF uploaded: {filename}")
            pdf_output.seek(0)  # rewind again
        except Exception as e:
            logger.error(f"❌ Drive upload failed: {e}")

        return send_file(pdf_output, as_attachment=True, download_name="report.pdf")

    except Exception as e:
        logger.exception("❌ Error in form submission")
        return "An error occurred during submission", 500

if __name__ == '__main__':
    app.run(debug=True)
