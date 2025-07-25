import os
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from fpdf import FPDF
import base64
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)  # ✅ MUST come before client usage
# Open your target Google Sheet by name (not URL)
sheet = client.open("webdata").sheet1

    
app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
SIGNATURE_FOLDER = os.path.join(BASE_DIR, 'static', 'signatures')
PDF_FOLDER = os.path.join(BASE_DIR, 'static', 'reports')



os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SIGNATURE_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

# Save uploaded images
def save_images(file_list, prefix):
    image_paths = []
    for file in file_list:
        if file and file.filename:
            filename = secure_filename(f"{prefix}_{file.filename}")
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            image_paths.append(path)
    return image_paths
def save_signature(base64_data, filename):
    if base64_data:
        if "," in base64_data:
            base64_data = base64_data.split(',')[1]
            image_data = base64.b64decode(base64_data)
            path = os.path.join(SIGNATURE_FOLDER, filename)
            with open(path, 'wb') as f:
                f.write(image_data)
                return path
        return None

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    # Get form data
    date = request.form.get('date')
    product_category = request.form.get('product_category')
    supplier_name = request.form.get('supplier_name')
    item_description = request.form.get('item_description')
    design_no = request.form.get('design_no')
    colour = request.form.get('colour')
    inspector_name = request.form.get('inspector_name')
    fabric_quality = request.form.get('fabric_quality')
    merchandiser_name = request.form.get('merchandiser_name')
    order_quantity = request.form.get('order_quantity')
    presented_quantity = request.form.get('presented_quantity')
    pieces_inspected = request.form.get('pieces_inspected')
    sampling_range = request.form.get('sampling_range')
    inline_inspection = request.form.get('inline_inspection')
    pp_approved = request.form.get('pp_approved')
    packing_list = request.form.get('packing_list')
    po_same = request.form.get('po_same')
    storage_ok = request.form.get('storage_ok')
    carton_selected = request.form.get('carton_selected')
    total_cartons = request.form.get('total_cartons')
    inspected_cartons = request.form.get('inspected_cartons')
    inspection_result = request.form.get('inspection_result')
    delivery_date = request.form.get('delivery_date')
    final_comments = request.form.get('final_comments')

    # Google Sheet update
    sheet.append_row([
        date, product_category, supplier_name, item_description, design_no, colour,
        inspector_name, merchandiser_name, order_quantity, presented_quantity,
        pp_approved, delivery_date, final_comments
    ])

    # Images and signatures
    defect_types = request.form.getlist('defectType[]')
    minor_counts = request.form.getlist('minor[]')
    major_counts = request.form.getlist('major[]')
    total_minor = request.form.get('totalMinor', '0')
    total_major = request.form.get('totalMajor', '0')
    # Group defect images for each defect type
    defect_images = []

    i = 0
    while True:
       files = request.files.getlist(f'defectImages_{i}[]')
       if not files or all(f.filename == '' for f in files):  # check for actual files
        break
       paths = save_images(files, f'defect_{i}')
       defect_images.append(paths)
       i += 1

     
    qc_signature_path = save_signature(request.form.get('qc_signature'), 'qc_signature.png')
    supplier_signature_path = save_signature(request.form.get('supplier_signature'), 'supplier_signature.png')
    aqm_signature_path = save_signature(request.form.get('aqm_signature'), 'aqm_signature.png')
    merch_signature_path = save_signature(request.form.get('merch_signature'), 'merch_signature.png')

    factory_images = save_images(request.files.getlist('factory_pictures'), 'factory')
    inline_images = save_images(request.files.getlist('inline_pictures'), 'inline')
    pp_images = save_images(request.files.getlist('pp_pictures'), 'pp')
    packing_list_images = save_images(request.files.getlist('packing_list_pictures'), 'packing')
    po_images = save_images(request.files.getlist('po_pictures'), 'po')
    storage_images = save_images(request.files.getlist('storage_pictures'), 'storage')
    carton_images = save_images(request.files.getlist('carton_pictures'), 'carton')

    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Final Inspection Report", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.ln(5)

    fields = [
        ("Inspection Date", date),
        ("Product Category", product_category),
        ("Supplier Name", supplier_name),
        ("Item Description", item_description),
        ("Design No", design_no),
        ("Colour", colour),
        ("Inspector Name", inspector_name),
        ("Fabric Quality", fabric_quality),
        ("Merchandiser Name", merchandiser_name),
        ("Order Quantity", order_quantity),
        ("Presented Quantity", presented_quantity),
        ("Number of Pieces Inspected", pieces_inspected),
        ("Sampling Range Selected", sampling_range),
        ("Inline Inspection Performed?", inline_inspection),
        ("PP Sample Approved?", pp_approved),
        ("Packing List Available?", packing_list),
        ("PO Quantity Match?", po_same),
        ("Storage OK?", storage_ok),
        ("Carton Numbers Selected", carton_selected),
        ("Total No. of Cartons", total_cartons),
        ("Inspected Cartons", inspected_cartons),
        ("Inspection Result", inspection_result),
        ("Delivery Date", delivery_date),
        ("Final Comments", final_comments),
    ]

    pdf.set_fill_color(220, 230, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, "Field", border=1, fill=True)
    pdf.cell(120, 10, "Value", border=1, ln=True, fill=True)
    pdf.set_font("Arial", '', 12)

    for label, value in fields:
        pdf.cell(70, 10, label, border=1)
        pdf.cell(120, 10, str(value) if value else "", border=1, ln=True)


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

       for i in range(len(defect_types)):
            pdf.cell(60, 10, defect_types[i], border=1)
            pdf.cell(30, 10, minor_counts[i], border=1)
            pdf.cell(30, 10, major_counts[i], border=1)

            if i < len(defect_images):
               img_count = len(defect_images[i])
               pdf.cell(70, 10, f"{img_count} image(s)", border=1, ln=True)

            # ✅ Add all images under this defect
               for img_path in defect_images[i]:
                  if img_path and os.path.exists(img_path):
                    try:
                          pdf.image(img_path, w=60)
                          pdf.ln(5)
                    except:
                        pdf.cell(0, 10, f"Error loading image: {os.path.basename(img_path)}", ln=True)
    else:
            pdf.cell(70, 10, "No Image", border=1, ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(60, 10, "Total", border=1)
    pdf.cell(30, 10, total_minor, border=1)
    pdf.cell(30, 10, total_major, border=1)
    pdf.cell(70, 10, "", border=1, ln=True)

            

    def add_images_to_pdf(title, img_list):
        if img_list:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, title, ln=True)
            pdf.ln(5)
            for img in img_list:
                try:
                    pdf.image(img, w=100)
                    pdf.ln(10)
                except Exception:
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(0, 10, f"Could not load image: {os.path.basename(img)}", ln=True)

    add_images_to_pdf("Factory Pictures", factory_images)
    add_images_to_pdf("Inline Pictures", inline_images)
    add_images_to_pdf("PP Sample Pictures", pp_images)
    add_images_to_pdf("Packing List Pictures", packing_list_images)
    add_images_to_pdf("PO Pictures", po_images)
    add_images_to_pdf("Storage Pictures", storage_images)
    add_images_to_pdf("Carton Pictures", carton_images)

    # Signatures
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Signatures", ln=True)
    pdf.ln(10)

    def draw_signature(label, path):
        if path and os.path.exists(path):
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 10, f"{label}:", ln=True)
            pdf.image(path, w=60)
            pdf.ln(10)

    draw_signature("QC Officer", qc_signature_path)
    draw_signature("Supplier Representative", supplier_signature_path)
    draw_signature("Assistant Quality Manager", aqm_signature_path)
    draw_signature("Merchandiser", merch_signature_path)

    pdf_filename = f"inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join('static/reports', pdf_filename)
    pdf.output(pdf_path)

    from drive_uploader import upload_to_drive
    folder_id = '1JRaPohdgYZ63gjNxbKLBITlLN-WTWZgb'  # replace with your folder's ID
    upload_to_drive(pdf_path, pdf_filename, folder_id)



    

    return send_file(pdf_path, as_attachment=True)
if __name__ == '__main__':
    app.run(debug=True)
