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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
SIGNATURE_FOLDER = os.path.join(BASE_DIR, 'static', 'signatures')
PDF_FOLDER = os.path.join(BASE_DIR, 'static', 'reports')

for folder in [UPLOAD_FOLDER, SIGNATURE_FOLDER, PDF_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Configure file size limits (optional, to avoid Render crashing)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB max per request

# Google Sheets client
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("webdata").sheet1
except Exception as e:
    logger.exception("Failed to authenticate with Google Sheets")
    sheet = None  # Prevent crash

# Helpers
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

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        form_fields = {
            'date': request.form.get('date'),
            'product_category': request.form.get('product_category'),
            'supplier_name': request.form.get('supplier_name'),
            'item_description': request.form.get('item_description'),
            'design_no': request.form.get('design_no'),
            'colour': request.form.get('colour'),
            'inspector_name': request.form.get('inspector_name'),
            'fabric_quality': request.form.get('fabric_quality'),
            'merchandiser_name': request.form.get('merchandiser_name'),
            'order_quantity': request.form.get('order_quantity'),
            'presented_quantity': request.form.get('presented_quantity'),
            'pieces_inspected': request.form.get('pieces_inspected'),
            'sampling_range': request.form.get('sampling_range'),
            'inline_inspection': request.form.get('inline_inspection'),
            'pp_approved': request.form.get('pp_approved'),
            'packing_list': request.form.get('packing_list'),
            'po_same': request.form.get('po_same'),
            'storage_ok': request.form.get('storage_ok'),
            'carton_selected': request.form.get('carton_selected'),
            'total_cartons': request.form.get('total_cartons'),
            'inspected_cartons': request.form.get('inspected_cartons'),
            'inspection_result': request.form.get('inspection_result'),
            'delivery_date': request.form.get('delivery_date'),
            'final_comments': request.form.get('final_comments'),
        }

        # Write to Google Sheet
        if sheet:
            try:
                sheet.append_row([
                    form_fields['date'], form_fields['product_category'], form_fields['supplier_name'],
                    form_fields['item_description'], form_fields['design_no'], form_fields['colour'],
                    form_fields['inspector_name'], form_fields['merchandiser_name'],
                    form_fields['order_quantity'], form_fields['presented_quantity'],
                    form_fields['pp_approved'], form_fields['delivery_date'], form_fields['final_comments']
                ])
                logger.info("Appended row to Google Sheet.")
            except Exception as e:
                logger.error("Failed to append to Google Sheet: %s", str(e))

        # Save defect details
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

        qc_signature = save_signature(request.form.get('qc_signature'), 'qc_signature.png')
        supplier_signature = save_signature(request.form.get('supplier_signature'), 'supplier_signature.png')
        aqm_signature = save_signature(request.form.get('aqm_signature'), 'aqm_signature.png')
        merch_signature = save_signature(request.form.get('merch_signature'), 'merch_signature.png')

        factory_images = save_images(request.files.getlist('factory_pictures'), 'factory')
        inline_images = save_images(request.files.getlist('inline_pictures'), 'inline')
        pp_images = save_images(request.files.getlist('pp_pictures'), 'pp')
        packing_images = save_images(request.files.getlist('packing_list_pictures'), 'packing')
        po_images = save_images(request.files.getlist('po_pictures'), 'po')
        storage_images = save_images(request.files.getlist('storage_pictures'), 'storage')
        carton_images = save_images(request.files.getlist('carton_pictures'), 'carton')

        # Start PDF generation
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
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(60, 10, "Defect Type", border=1)
            pdf.cell(30, 10, "Minor", border=1)
            pdf.cell(30, 10, "Major", border=1)
            pdf.cell(70, 10, "Image(s)", border=1, ln=True)
            pdf.set_font("Arial", '', 12)

            for i, dtype in enumerate(defect_types):
                pdf.cell(60, 10, dtype, border=1)
                pdf.cell(30, 10, minor_counts[i], border=1)
                pdf.cell(30, 10, major_counts[i], border=1)
                pdf.cell(70, 10, f"{len(defect_images[i])} image(s)" if i < len(defect_images) else "0", border=1, ln=True)
                for img in defect_images[i]:
                    try:
                        pdf.image(img, w=60)
                        pdf.ln(5)
                    except:
                        pdf.cell(0, 10, f"Error loading image {os.path.basename(img)}", ln=True)

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

        filename = f"inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(PDF_FOLDER, filename)
        pdf.output(pdf_path)
        logger.info(f"PDF generated: {filename}")

        # Upload to Drive
        from drive_uploader import upload_to_drive
# Upload to Google Drive
        try:
            upload_to_drive(pdf_path, pdf_filename, folder_id='1vQbksJZzNLmTaLkEfgtg4HErKArI-HVf')
            logger.info("✅ Uploaded to Google Drive successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to upload to Google Drive: {e}")

        return "Form submitted and PDF uploaded to Google Drive successfully."

    except Exception as e:
        logger.exception("❌ Error in /submit handler")
        return "An error occurred during submission. Please check the logs or contact support.", 500


if __name__ == '__main__':
    app.run(debug=True)
