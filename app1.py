import os
import logging
import base64
import json
from datetime import datetime
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app1")

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
SIGNATURE_FOLDER = os.path.join(BASE_DIR, 'static', 'signatures')
PDF_FOLDER = os.path.join(BASE_DIR, 'static', 'reports')

for folder in [UPLOAD_FOLDER, SIGNATURE_FOLDER, PDF_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB max

# --- Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("webdata").sheet1
except Exception as e:
    logger.exception("Failed to authenticate with Google Sheets")
    sheet = None

# --- Helpers ---
def save_images(file_list, prefix):
    image_paths = []
    for file in file_list:
        if file and file.filename:
            filename = secure_filename(f"{prefix}_{file.filename}")
            path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                file.save(path)
                image_paths.append(path)
            except Exception as e:
                logger.error(f"Failed to save image {filename}: {e}")
    return image_paths

def save_signature(base64_data, filename):
    if base64_data and "," in base64_data:
        base64_data = base64_data.split(',')[1]
        try:
            image_data = base64.b64decode(base64_data)
            path = os.path.join(SIGNATURE_FOLDER, filename)
            with open(path, 'wb') as f:
                f.write(image_data)
            return path
        except Exception as e:
            logger.error(f"Failed to save signature {filename}: {e}")
    return None

# --- Routes ---
@app.route('/')
def form():
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # Get form fields
        form_fields = {
            key: request.form.get(key) for key in [
                'date', 'product_category', 'supplier_name', 'item_description', 'design_no',
                'colour', 'inspector_name', 'fabric_quality', 'merchandiser_name',
                'order_quantity', 'presented_quantity', 'pieces_inspected', 'sampling_range',
                'inline_inspection', 'pp_approved', 'packing_list', 'po_same', 'storage_ok',
                'carton_selected', 'total_cartons', 'inspected_cartons', 'inspection_result',
                'delivery_date', 'final_comments'
            ]
        }

        # Append to Google Sheet
        if sheet:
            try:
                sheet.append_row([
                    form_fields['date'], form_fields['product_category'], form_fields['supplier_name'],
                    form_fields['item_description'], form_fields['design_no'], form_fields['colour'],
                    form_fields['inspector_name'], form_fields['merchandiser_name'],
                    form_fields['order_quantity'], form_fields['presented_quantity'],
                    form_fields['pp_approved'], form_fields['delivery_date'], form_fields['final_comments']
                ])
                logger.info("✅ Appended row to Google Sheet.")
            except Exception as e:
                logger.error(f"❌ Failed to append to Google Sheet: {e}")

        # Defect details
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
            defect_images.append(save_images(files, f'defect_{i}'))
            i += 1

        # Signatures
        qc_signature = save_signature(request.form.get('qc_signature'), 'qc_signature.png')
        supplier_signature = save_signature(request.form.get('supplier_signature'), 'supplier_signature.png')
        aqm_signature = save_signature(request.form.get('aqm_signature'), 'aqm_signature.png')
        merch_signature = save_signature(request.form.get('merch_signature'), 'merch_signature.png')

        # Other pictures
        factory_images = save_images(request.files.getlist('factory_pictures'), 'factory')
        inline_images = save_images(request.files.getlist('inline_pictures'), 'inline')
        pp_images = save_images(request.files.getlist('pp_pictures'), 'pp')
        packing_images = save_images(request.files.getlist('packing_list_pictures'), 'packing')
        po_images = save_images(request.files.getlist('po_pictures'), 'po')
        storage_images = save_images(request.files.getlist('storage_pictures'), 'storage')
        carton_images = save_images(request.files.getlist('carton_pictures'), 'carton')

        # Generate PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Final Inspection Report", ln=True, align='C')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(220, 230, 255)
        pdf.cell(70, 10, "Field", border=1, fill=True)
        pdf.cell(120, 10, "Value", border=1, ln=True, fill=True)

        pdf.set_font("Arial", '', 12)
        for label, value in form_fields.items():
            pdf.cell(70, 10, label.replace("_", " ").title(), border=1)
            pdf.cell(120, 10, str(value or ""), border=1, ln=True)

        if defect_types:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Defects Summary", ln=True)
            pdf.set_font("Arial", '', 12)
            for i, dtype in enumerate(defect_types):
                pdf.cell(60, 10, dtype, border=1)
                pdf.cell(30, 10, minor_counts[i], border=1)
                pdf.cell(30, 10, major_counts[i], border=1)
                pdf.cell(70, 10, f"{len(defect_images[i])} image(s)", border=1, ln=True)
                for img in defect_images[i]:
                    try:
                        pdf.image(img, w=60)
                        pdf.ln(5)
                    except:
                        pdf.cell(0, 10, f"Could not load image {os.path.basename(img)}", ln=True)

            pdf.cell(60, 10, "Total", border=1)
            pdf.cell(30, 10, total_minor, border=1)
            pdf.cell(30, 10, total_major, border=1)
            pdf.cell(70, 10, "", border=1, ln=True)

        def add_images(title, images):
            if images:
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, title, ln=True)
                pdf.ln(5)
                for img in images:
                    try:
                        pdf.image(img, w=100)
                        pdf.ln(10)
                    except:
                        pdf.cell(0, 10, f"Could not load image: {os.path.basename(img)}", ln=True)

        add_images("Factory Pictures", factory_images)
        add_images("Inline Pictures", inline_images)
        add_images("PP Sample Pictures", pp_images)
        add_images("Packing List Pictures", packing_images)
        add_images("PO Pictures", po_images)
        add_images("Storage Pictures", storage_images)
        add_images("Carton Pictures", carton_images)

        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Signatures", ln=True)

        for label, path in [("QC Officer", qc_signature), ("Supplier", supplier_signature),
                            ("AQM", aqm_signature), ("Merchandiser", merch_signature)]:
            if path and os.path.exists(path):
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 10, f"{label}:", ln=True)
                try:
                    pdf.image(path, w=60)
                except:
                    pdf.cell(0, 10, f"Could not load signature for {label}", ln=True)
                pdf.ln(5)

        pdf_filename = f"inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
        pdf.output(pdf_path)
        logger.info(f"✅ PDF generated: {pdf_filename}")

        # Upload to Google Drive
        from drive_uploader import upload_to_drive
        try:
            upload_to_drive(pdf_path, pdf_filename, folder_id='1vQbksJZzNLmTaLkEfgtg4HErKArI-HVf')
            logger.info("✅ Uploaded to Google Drive successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to upload to Google Drive: {e}")

        return "✅ Form submitted and PDF uploaded to Google Drive."

    except Exception as e:
        logger.exception("❌ Error in /submit handler")
        return "❌ An error occurred during submission.", 500

# --- Run Locally ---
if __name__ == '__main__':
    app.run(debug=True)
