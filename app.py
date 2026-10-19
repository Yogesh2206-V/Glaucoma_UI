import os
import io
import base64
import datetime
import random
import csv
from bson import ObjectId
import numpy as np
from PIL import Image
import cv2
import onnxruntime as ort
from flask import Flask, render_template, request, jsonify, send_from_directory, Response
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb+srv://yogesh12345:Yogeshmkce251@cluster0.43npwmp.mongodb.net/?appName=Cluster0'
)
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'glaucoma_db')

mongo_client = None
db = None
scans_collection = None
tonometer_collection = None

# In-memory fallbacks in case MongoDB has transient network issues
local_patient_records = []
local_tonometer_readings = []

latest_tonometer_reading = {
    'iop': 16.5,
    'raw_adc': None,
    'status': 'Normal',
    'risk_level': 'Normal Pressure (10-21 mmHg)',
    'eye_type': 'OD (Right Eye)',
    'patient_id': None,
    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'device_id': 'ESP32-BLE-Tonometer'
}

def get_db_collection():
    global mongo_client, db, scans_collection
    if scans_collection is not None:
        return scans_collection
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        mongo_client.admin.command('ping')
        db = mongo_client[MONGO_DB_NAME]
        scans_collection = db['scans']
        print(f"[INFO] MongoDB Atlas connected successfully. Database: {MONGO_DB_NAME}")
        return scans_collection
    except Exception as e:
        print(f"[WARNING] MongoDB Atlas connection error: {e}")
        return None

def get_tonometer_collection():
    global mongo_client, db, tonometer_collection
    if tonometer_collection is not None:
        return tonometer_collection
    try:
        from pymongo import MongoClient
        if mongo_client is None:
            mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
            mongo_client.admin.command('ping')
            db = mongo_client[MONGO_DB_NAME]
        tonometer_collection = db['tonometer_readings']
        return tonometer_collection
    except Exception as e:
        print(f"[WARNING] MongoDB tonometer collection error: {e}")
        return None

def classify_iop(iop_val):
    try:
        val = float(iop_val)
    except (TypeError, ValueError):
        val = 18.0
    if val < 10.0:
        return 'Hypotony', 'Low Pressure (<10 mmHg)', 'alert-warning'
    elif val <= 21.0:
        return 'Normal', 'Normal Pressure (10-21 mmHg)', 'alert-normal'
    elif val <= 24.0:
        return 'Borderline', 'Borderline Elevated (21-24 mmHg - Close Monitor)', 'alert-warning'
    else:
        return 'High Risk', 'High Glaucoma Risk (>24 mmHg - Ocular Hypertension)', 'alert-danger'

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
MODEL_ONNX_PATH = os.path.join(BASE_DIR, 'best.onnx')
SAMPLE_GLAUCOMA_PATH = os.path.join(STATIC_DIR, 'sample_glaucoma.jpg')
SAMPLE_NORMAL_PATH = os.path.join(STATIC_DIR, 'sample_normal.jpg')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# Class mappings for Glaucoma model
CLASSES = {0: 'Glaucoma', 1: 'Normal'}
COLORS = {
    'Glaucoma': (0, 0, 230),  # Bright Red in BGR
    'Normal': (0, 200, 40)    # Bright Green in BGR
}

# Lazy load ONNX session
onnx_session = None

def get_session():
    global onnx_session
    if onnx_session is None:
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            onnx_session = ort.InferenceSession(MODEL_ONNX_PATH, opts, providers=['CPUExecutionProvider'])
            print("[INFO] ONNX Model loaded successfully from:", MODEL_ONNX_PATH)
        except Exception as e:
            print("[ERROR] Error loading ONNX model:", e)
            onnx_session = None
    return onnx_session

# Warm up model on startup
get_session()
get_db_collection()

def generate_base64_thumbnail(pil_img, size=(180, 180)):
    """Generate a lightweight JPEG base64 thumbnail for quick list view rendering."""
    try:
        thumb = pil_img.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=75)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception as e:
        print(f"[WARNING] Thumbnail creation failed: {e}")
        return ""

def get_sample_image_b64(filepath):
    """Generate base64 for sample fundus images if available."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
                return f"data:image/jpeg;base64,{base64.b64encode(data).decode('utf-8')}"
        except Exception:
            pass
    return ""

def run_inference(img_orig, conf_thresh=0.25, iou_thresh=0.45):
    session = get_session()
    if session is None:
        raise RuntimeError("Model session is not loaded.")

    orig_w, orig_h = img_orig.size

    # Letterbox resize to 640x640 maintaining aspect ratio
    scale = min(640.0 / orig_w, 640.0 / orig_h)
    nw, nh = int(round(orig_w * scale)), int(round(orig_h * scale))
    img_resized = img_orig.resize((nw, nh), Image.Resampling.BILINEAR)

    pad_w = (640 - nw) // 2
    pad_h = (640 - nh) // 2

    canvas = Image.new('RGB', (640, 640), (114, 114, 114))
    canvas.paste(img_resized, (pad_w, pad_h))

    # Preprocess
    img_np = np.array(canvas, dtype=np.float32) / 255.0
    img_np = np.transpose(img_np, (2, 0, 1))  # Shape (3, 640, 640)
    img_np = np.expand_dims(img_np, axis=0)   # Shape (1, 3, 640, 640)

    # Run ONNX inference
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: img_np})[0]  # Shape (1, 6, 8400)
    predictions = np.transpose(outputs[0])                # Shape (8400, 6)

    boxes = []
    confidences = []
    class_ids = []

    for row in predictions:
        cx, cy, w, h = row[:4]
        scores = row[4:]
        cls_id = int(np.argmax(scores))
        conf = float(scores[cls_id])

        if conf >= conf_thresh:
            # Map coordinates back to original image scale
            x1 = (cx - w / 2.0 - pad_w) / scale
            y1 = (cy - h / 2.0 - pad_h) / scale
            x2 = (cx + w / 2.0 - pad_w) / scale
            y2 = (cy + h / 2.0 - pad_h) / scale

            x1 = max(0, min(orig_w, x1))
            y1 = max(0, min(orig_h, y1))
            w_box = max(0, min(orig_w - x1, x2 - x1))
            h_box = max(0, min(orig_h - y1, y2 - y1))

            boxes.append([int(x1), int(y1), int(w_box), int(h_box)])
            confidences.append(conf)
            class_ids.append(cls_id)

    # Non-Maximum Suppression
    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_thresh, iou_thresh)
    detections = []
    
    # Convert PIL to OpenCV BGR for high quality bounding box drawing
    img_bgr = cv2.cvtColor(np.array(img_orig), cv2.COLOR_RGB2BGR)

    if len(indices) > 0:
        flat_indices = indices.flatten() if hasattr(indices, 'flatten') else indices
        for i in flat_indices:
            box = boxes[i]
            conf = confidences[i]
            cls_id = class_ids[i]
            cls_name = CLASSES.get(cls_id, f"Class {cls_id}")
            color = COLORS.get(cls_name, (255, 255, 0))

            x, y, w, h = box
            cv2.rectangle(img_bgr, (x, y), (x + w, y + h), color, 3)

            label = f"{cls_name} {round(conf * 100, 1)}%"
            font_scale = max(0.5, min(orig_w, orig_h) / 800.0)
            thickness = max(1, int(font_scale * 2))
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)

            y_text = max(y, th + 10)
            cv2.rectangle(img_bgr, (x, y_text - th - 8), (x + tw + 10, y_text + 4), color, -1)
            cv2.putText(img_bgr, label, (x + 5, y_text - 4), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

            detections.append({
                'class': cls_name,
                'confidence': round(conf * 100, 1),
                'box': {'x': x, 'y': y, 'w': w, 'h': h}
            })

    detections.sort(key=lambda d: d['confidence'], reverse=True)
    primary_class = detections[0]['class'] if detections else "No Detection"
    top_confidence = detections[0]['confidence'] if detections else 0.0

    _, buf = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    img_b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

    return primary_class, top_confidence, detections, f"data:image/jpeg;base64,{img_b64}"

# Default historical glaucoma and clinical records
SEED_PATIENTS = [
    {
        'patient_id': 'GLC-2026-0104',
        'patient_name': 'Eleanor Vance',
        'age': 67,
        'gender': 'Female',
        'eye_type': 'OD (Right Eye)',
        'iop': 26.4,
        'cup_disc_ratio': 0.82,
        'prediction': 'Glaucoma',
        'confidence': 94.8,
        'severity': 'Advanced Open-Angle Glaucoma',
        'timestamp': '2026-09-14T10:30:00.000Z',
        'notes': 'Marked neuroretinal rim thinning in inferior and superior poles, deep cup excavation. Peripheral arcuate scotoma confirmed. Prescribed Bimatoprost 0.01% nightly.',
        'filename': 'patient_vance_od_fundus.jpg',
        'expected_class': 'Glaucoma',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Glaucoma', 'confidence': 94.8, 'box': {'x': 180, 'y': 150, 'w': 280, 'h': 290}}],
        'is_glaucoma': True
    },
    {
        'patient_id': 'GLC-2026-0219',
        'patient_name': 'Marcus Aurelius Chen',
        'age': 59,
        'gender': 'Male',
        'eye_type': 'OS (Left Eye)',
        'iop': 24.1,
        'cup_disc_ratio': 0.76,
        'prediction': 'Glaucoma',
        'confidence': 91.2,
        'severity': 'Moderate Open-Angle Glaucoma',
        'timestamp': '2026-09-28T14:15:00.000Z',
        'notes': 'Early nasal step on Humphrey visual field testing. Increased vertical cup-to-disc asymmetry compared to right eye. Prescribed Timolol maleate 0.5% BID.',
        'filename': 'chen_left_retina.jpg',
        'expected_class': 'Glaucoma',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Glaucoma', 'confidence': 91.2, 'box': {'x': 210, 'y': 175, 'w': 245, 'h': 260}}],
        'is_glaucoma': True
    },
    {
        'patient_id': 'GLC-2026-0342',
        'patient_name': 'Devi Ramanathan',
        'age': 72,
        'gender': 'Female',
        'eye_type': 'OD (Right Eye)',
        'iop': 29.8,
        'cup_disc_ratio': 0.88,
        'prediction': 'Glaucoma',
        'confidence': 96.5,
        'severity': 'Severe Chronic Angle-Closure Glaucoma',
        'timestamp': '2026-10-02T09:45:00.000Z',
        'notes': 'Very narrow iridocorneal angles on gonioscopy, severe optic nerve head cupping with bayoneting of retinal vessels. Urgent laser peripheral iridotomy indicated.',
        'filename': 'ramanathan_od_oct.jpg',
        'expected_class': 'Glaucoma',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Glaucoma', 'confidence': 96.5, 'box': {'x': 195, 'y': 160, 'w': 290, 'h': 305}}],
        'is_glaucoma': True
    },
    {
        'patient_id': 'GLC-2026-0418',
        'patient_name': "James O'Connor",
        'age': 63,
        'gender': 'Male',
        'eye_type': 'OS (Left Eye)',
        'iop': 22.8,
        'cup_disc_ratio': 0.71,
        'prediction': 'Glaucoma',
        'confidence': 87.4,
        'severity': 'Early Stage Primary Open-Angle Glaucoma',
        'timestamp': '2026-10-08T11:20:00.000Z',
        'notes': 'Notching of inferior neuroretinal rim. Retinal nerve fiber layer (RNFL) bundle defect detected. Under close 3-month follow-up monitoring.',
        'filename': 'oconnor_os_scan.jpg',
        'expected_class': 'Glaucoma',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Glaucoma', 'confidence': 87.4, 'box': {'x': 220, 'y': 190, 'w': 230, 'h': 240}}],
        'is_glaucoma': True
    },
    {
        'patient_id': 'GLC-2026-0505',
        'patient_name': 'Fatima Al-Mansoor',
        'age': 55,
        'gender': 'Female',
        'eye_type': 'OD (Right Eye)',
        'iop': 25.0,
        'cup_disc_ratio': 0.79,
        'prediction': 'Glaucoma',
        'confidence': 93.1,
        'severity': 'Pseudoexfoliation Glaucoma',
        'timestamp': '2026-10-12T16:00:00.000Z',
        'notes': 'Fibrillar white deposits on anterior lens capsule and pupillary margin. Fluctuation in diurnal IOP. Initiated Dorzolamide/Timolol combination drops.',
        'filename': 'almansoor_fundus_od.jpg',
        'expected_class': 'Glaucoma',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Glaucoma', 'confidence': 93.1, 'box': {'x': 185, 'y': 165, 'w': 275, 'h': 285}}],
        'is_glaucoma': True
    },
    {
        'patient_id': 'GLC-2026-0611',
        'patient_name': 'David K. Miller',
        'age': 68,
        'gender': 'Male',
        'eye_type': 'OD (Right Eye)',
        'iop': 27.2,
        'cup_disc_ratio': 0.85,
        'prediction': 'Glaucoma',
        'confidence': 89.6,
        'severity': 'Advanced Glaucoma with Vascular Dysregulation',
        'timestamp': '2026-10-15T13:10:00.000Z',
        'notes': 'Progressive optic neuropathy with flame-shaped splinter disc hemorrhages at 7 oclock margin. Systemic nocturnal dipping monitored.',
        'filename': 'miller_retinal_scan.jpg',
        'expected_class': 'Glaucoma',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Glaucoma', 'confidence': 89.6, 'box': {'x': 200, 'y': 155, 'w': 260, 'h': 270}}],
        'is_glaucoma': True
    },
    {
        'patient_id': 'PAT-2026-0701',
        'patient_name': 'Hannah Abbott',
        'age': 38,
        'gender': 'Female',
        'eye_type': 'OD (Right Eye)',
        'iop': 15.2,
        'cup_disc_ratio': 0.28,
        'prediction': 'Normal',
        'confidence': 95.2,
        'severity': 'Healthy Normal Retina',
        'timestamp': '2026-10-16T10:15:00.000Z',
        'notes': 'Healthy neuroretinal rim obeying the ISNT rule. Pink optic disc with crisp margins, normal physiological cup. Normal Humphrey visual field.',
        'filename': 'abbott_healthy_od.jpg',
        'expected_class': 'Normal',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Normal', 'confidence': 95.2, 'box': {'x': 150, 'y': 140, 'w': 340, 'h': 350}}],
        'is_glaucoma': False
    },
    {
        'patient_id': 'PAT-2026-0755',
        'patient_name': 'Carlos Gomez',
        'age': 44,
        'gender': 'Male',
        'eye_type': 'OS (Left Eye)',
        'iop': 16.5,
        'cup_disc_ratio': 0.32,
        'prediction': 'Normal',
        'confidence': 93.8,
        'severity': 'Healthy Normal Retina',
        'timestamp': '2026-10-17T15:30:00.000Z',
        'notes': 'Routine screening examination. No optic disc cupping, clear healthy retinal vasculature without microaneurysms or pallor.',
        'filename': 'gomez_os_fundus.jpg',
        'expected_class': 'Normal',
        'accuracy_match': True,
        'detections_count': 1,
        'detections': [{'class': 'Normal', 'confidence': 93.8, 'box': {'x': 160, 'y': 150, 'w': 320, 'h': 330}}],
        'is_glaucoma': False
    }
]

def ensure_historical_patients_seeded(col=None):
    """Seed historical patient records if database has no detailed patient records."""
    glaucoma_thumb = get_sample_image_b64(SAMPLE_GLAUCOMA_PATH)
    normal_thumb = get_sample_image_b64(SAMPLE_NORMAL_PATH)

    records_to_seed = []
    for item in SEED_PATIENTS:
        rec = dict(item)
        if rec['is_glaucoma']:
            rec['thumbnail'] = glaucoma_thumb
            rec['image_url'] = glaucoma_thumb
        else:
            rec['thumbnail'] = normal_thumb
            rec['image_url'] = normal_thumb
        records_to_seed.append(rec)

    if col is not None:
        try:
            # Check if any documents already have patient_id
            existing_patient_count = col.count_documents({'patient_id': {'$exists': True}})
            if existing_patient_count < 4:
                for doc in records_to_seed:
                    # Upsert by patient_id
                    col.update_one({'patient_id': doc['patient_id']}, {'$set': doc}, upsert=True)
                print(f"[INFO] Seeded {len(records_to_seed)} historical patient records into MongoDB Atlas.")
        except Exception as e:
            print(f"[WARNING] MongoDB Atlas seeding error: {e}")

    # Also keep in local fallback
    global local_patient_records
    if len(local_patient_records) < 4:
        local_patient_records = [dict(r) for r in records_to_seed]

# Perform initial seed check
try:
    ensure_historical_patients_seeded(get_db_collection())
except Exception as e:
    print(f"[WARNING] Startup seed check: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/predict', methods=['POST'])
def predict():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded.'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected.'}), 400

    # Extract patient metadata from form
    patient_id = request.form.get('patient_id', '').strip()
    if not patient_id:
        patient_id = f"GLC-2026-{random.randint(1000, 9999)}"

    patient_name = request.form.get('patient_name', '').strip()
    if not patient_name:
        patient_name = f"Patient {patient_id}"

    age_str = request.form.get('age', '').strip()
    age = int(age_str) if age_str.isdigit() else 50

    gender = request.form.get('gender', 'Unspecified').strip()
    eye_type = request.form.get('eye_type', 'OD (Right Eye)').strip()
    
    iop_str = request.form.get('iop', '').strip()
    try:
        iop = float(iop_str) if iop_str else 18.0
    except ValueError:
        iop = 18.0

    cdr_str = request.form.get('cup_disc_ratio', '').strip()
    try:
        cup_disc_ratio = float(cdr_str) if cdr_str else 0.5
    except ValueError:
        cup_disc_ratio = 0.5

    notes = request.form.get('notes', '').strip()
    expected_class = request.form.get('expected_class', '').strip()

    try:
        image_bytes = file.read()
        pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        # Run AI inference
        primary_class, confidence_pct, detections, img_url = run_inference(pil_img, conf_thresh=0.25)

        # Generate lightweight thumbnail for fast list loading
        thumbnail_b64 = generate_base64_thumbnail(pil_img, size=(180, 180))

        # Severity classification
        is_glaucoma = (primary_class.lower() == 'glaucoma')
        if is_glaucoma:
            if confidence_pct >= 90.0 or iop >= 25.0:
                severity = "Severe Glaucoma / High Cupping"
            elif confidence_pct >= 75.0 or iop >= 21.0:
                severity = "Moderate Open-Angle Glaucoma"
            else:
                severity = "Early / Borderline Glaucoma Signs"
        else:
            severity = "Healthy Normal Retina"

        record = {
            'patient_id': patient_id,
            'patient_name': patient_name,
            'age': age,
            'gender': gender,
            'eye_type': eye_type,
            'iop': iop,
            'cup_disc_ratio': cup_disc_ratio,
            'notes': notes if notes else f"Screening evaluation completed. Diagnosis: {primary_class}.",
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'filename': file.filename,
            'prediction': primary_class,
            'confidence': confidence_pct,
            'severity': severity,
            'expected_class': expected_class if expected_class else None,
            'accuracy_match': (primary_class.lower() == expected_class.lower()) if expected_class else None,
            'detections_count': len(detections),
            'detections': detections,
            'thumbnail': thumbnail_b64 if thumbnail_b64 else img_url,
            'image_url': img_url,
            'is_glaucoma': is_glaucoma
        }

        # Save record to MongoDB Atlas
        mongo_doc_id = None
        try:
            col = get_db_collection()
            if col is not None:
                res = col.insert_one(record)
                mongo_doc_id = str(res.inserted_id)
                record['id'] = mongo_doc_id
                print(f"[INFO] Patient record saved to MongoDB with ID: {mongo_doc_id}")
        except Exception as mongo_err:
            print(f"[WARNING] Could not save record to MongoDB: {mongo_err}")

        # Always append to local records fallback
        if not mongo_doc_id:
            record['id'] = f"local-{len(local_patient_records)+1}"
        local_patient_records.insert(0, record)

        return jsonify({
            'success': True,
            'prediction': primary_class,
            'confidence': confidence_pct,
            'severity': severity,
            'detections': detections,
            'image_url': img_url,
            'db_saved': mongo_doc_id is not None,
            'patient_record': {
                'id': record.get('id', mongo_doc_id or record['patient_id']),
                'patient_id': patient_id,
                'patient_name': patient_name,
                'age': age,
                'gender': gender,
                'eye_type': eye_type,
                'iop': iop,
                'cup_disc_ratio': cup_disc_ratio,
                'notes': record['notes'],
                'timestamp': record['timestamp'],
                'prediction': primary_class,
                'confidence': confidence_pct,
                'severity': severity,
                'is_glaucoma': is_glaucoma
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500

@app.route('/api/patients', methods=['GET', 'POST'])
def get_patients():
    """Retrieve historical patient records or create a new patient intake record."""
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        patient_name = (data.get('patient_name') or 'Anonymous Patient').strip()
        age_str = str(data.get('age', 50)).strip()
        age = int(age_str) if age_str.isdigit() else 50

        status_input = str(data.get('status') or data.get('glaucoma_present') or 'Glaucoma').strip().lower()
        is_glaucoma = status_input in ['glaucoma', 'yes', 'true', 'present', '1', 'positive']
        primary_class = 'Glaucoma' if is_glaucoma else 'Normal'

        patient_id = data.get('patient_id')
        if not patient_id:
            patient_id = f"GLC-2026-{random.randint(1000, 9999)}"

        gender = data.get('gender', 'Unspecified')
        eye_type = data.get('eye_type', 'OD (Right Eye)')

        default_thumb = '/static/sample_glaucoma.jpg' if is_glaucoma else '/static/sample_normal.jpg'
        thumbnail = data.get('thumbnail') or default_thumb
        image_url = data.get('image_url') or default_thumb

        confidence = float(data.get('confidence', 95.5 if is_glaucoma else 97.2))
        iop = float(data.get('iop', 24.5 if is_glaucoma else 15.5))
        cup_disc_ratio = float(data.get('cup_disc_ratio', 0.75 if is_glaucoma else 0.35))
        severity = "Confirmed Glaucoma - Clinical Assessment" if is_glaucoma else "Healthy Normal Retina - Clinical Assessment"
        notes = data.get('notes', f"Clinical intake entry. Glaucoma Status: {'Present' if is_glaucoma else 'Not Present'}.")

        record = {
            'patient_id': patient_id,
            'patient_name': patient_name,
            'age': age,
            'gender': gender,
            'eye_type': eye_type,
            'iop': iop,
            'cup_disc_ratio': cup_disc_ratio,
            'notes': notes,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'filename': 'clinical_profile.jpg',
            'prediction': primary_class,
            'confidence': confidence,
            'severity': severity,
            'expected_class': primary_class,
            'accuracy_match': True,
            'detections_count': 1 if is_glaucoma else 0,
            'detections': [{'class': primary_class, 'confidence': confidence, 'box': {'x': 180, 'y': 160, 'w': 280, 'h': 280}}] if is_glaucoma else [],
            'thumbnail': thumbnail,
            'image_url': image_url,
            'is_glaucoma': is_glaucoma
        }

        mongo_doc_id = None
        try:
            col = get_db_collection()
            if col is not None:
                res = col.insert_one(record)
                mongo_doc_id = str(res.inserted_id)
                record['id'] = mongo_doc_id
                print(f"[INFO] New patient record saved to MongoDB with ID: {mongo_doc_id}")
        except Exception as mongo_err:
            print(f"[WARNING] Could not save new patient to MongoDB: {mongo_err}")

        if not mongo_doc_id:
            record['id'] = f"local-{len(local_patient_records)+1}"

        local_patient_records.insert(0, record)

        return jsonify({
            'success': True,
            'message': 'Patient added successfully',
            'patient': {
                'id': record.get('id', mongo_doc_id or record['patient_id']),
                'patient_id': patient_id,
                'patient_name': patient_name,
                'age': age,
                'gender': gender,
                'eye_type': eye_type,
                'iop': iop,
                'cup_disc_ratio': cup_disc_ratio,
                'notes': record['notes'],
                'timestamp': record['timestamp'],
                'prediction': primary_class,
                'confidence': confidence,
                'severity': severity,
                'is_glaucoma': is_glaucoma
            }
        }), 201

    disease_filter = request.args.get('disease', 'all').strip()
    search_query = request.args.get('search', '').strip().lower()
    sort_by = request.args.get('sort', 'newest').strip()
    limit = min(int(request.args.get('limit', 100)), 200)

    records = []
    col = get_db_collection()

    if col is not None:
        try:
            query = {}
            # Ensure historical seed exists
            if col.count_documents({'patient_id': {'$exists': True}}) < 4:
                ensure_historical_patients_seeded(col)

            # Build MongoDB query
            if disease_filter.lower() == 'glaucoma':
                query['prediction'] = {'$regex': '^glaucoma$', '$options': 'i'}
            elif disease_filter.lower() == 'normal':
                query['prediction'] = {'$regex': '^normal$', '$options': 'i'}

            if search_query:
                query['$or'] = [
                    {'patient_id': {'$regex': search_query, '$options': 'i'}},
                    {'patient_name': {'$regex': search_query, '$options': 'i'}},
                    {'notes': {'$regex': search_query, '$options': 'i'}},
                    {'filename': {'$regex': search_query, '$options': 'i'}}
                ]

            cursor = col.find(query)
            # Sort
            if sort_by == 'oldest':
                cursor = cursor.sort('timestamp', 1)
            elif sort_by == 'confidence_high':
                cursor = cursor.sort('confidence', -1)
            elif sort_by == 'iop_high':
                cursor = cursor.sort('iop', -1)
            else:  # newest
                cursor = cursor.sort('timestamp', -1)

            for d in cursor.limit(limit):
                d['id'] = str(d.pop('_id'))
                # Backfill patient_id/name if missing on older test records
                if 'patient_id' not in d:
                    d['patient_id'] = f"LEGACY-{d['id'][-4:].upper()}"
                if 'patient_name' not in d:
                    d['patient_name'] = f"Patient {d['patient_id']}"
                if 'is_glaucoma' not in d:
                    d['is_glaucoma'] = (d.get('prediction', '').lower() == 'glaucoma')
                records.append(d)

        except Exception as e:
            print(f"[WARNING] MongoDB fetch failed, using memory fallback: {e}")
            records = []

    # If MongoDB returned empty or had an issue, fallback to local memory list
    if not records:
        filtered = list(local_patient_records)
        if disease_filter.lower() == 'glaucoma':
            filtered = [r for r in filtered if r.get('prediction', '').lower() == 'glaucoma']
        elif disease_filter.lower() == 'normal':
            filtered = [r for r in filtered if r.get('prediction', '').lower() == 'normal']

        if search_query:
            filtered = [
                r for r in filtered
                if search_query in r.get('patient_name', '').lower()
                or search_query in r.get('patient_id', '').lower()
                or search_query in r.get('notes', '').lower()
            ]

        if sort_by == 'oldest':
            filtered.sort(key=lambda x: x.get('timestamp', ''))
        elif sort_by == 'confidence_high':
            filtered.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        elif sort_by == 'iop_high':
            filtered.sort(key=lambda x: x.get('iop', 0), reverse=True)
        else:
            filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        records = filtered[:limit]

    # Calculate overall clinical metrics
    total_count = len(records)
    glaucoma_count = sum(1 for r in records if r.get('prediction', '').lower() == 'glaucoma')
    normal_count = sum(1 for r in records if r.get('prediction', '').lower() == 'normal')
    avg_conf = round(sum(r.get('confidence', 0) for r in records) / total_count, 1) if total_count > 0 else 0
    high_risk_iop = sum(1 for r in records if float(r.get('iop', 0) or 0) >= 22.0)

    # Sanitize records to prevent sending excessively large payloads in list view
    clean_records = []
    for r in records:
        clean_r = {
            'id': r.get('id', r.get('patient_id')),
            'patient_id': r.get('patient_id', 'Unknown'),
            'patient_name': r.get('patient_name', 'Anonymous'),
            'age': r.get('age', 50),
            'gender': r.get('gender', 'Unspecified'),
            'eye_type': r.get('eye_type', 'OD (Right Eye)'),
            'iop': r.get('iop', 18.0),
            'cup_disc_ratio': r.get('cup_disc_ratio', 0.5),
            'prediction': r.get('prediction', 'Unknown'),
            'confidence': r.get('confidence', 0.0),
            'severity': r.get('severity', 'Evaluation completed'),
            'timestamp': r.get('timestamp', ''),
            'notes': r.get('notes', ''),
            'filename': r.get('filename', ''),
            'thumbnail': r.get('thumbnail') or r.get('image_url', ''),
            'is_glaucoma': (r.get('prediction', '').lower() == 'glaucoma')
        }
        clean_records.append(clean_r)

    return jsonify({
        'success': True,
        'records': clean_records,
        'stats': {
            'total': total_count,
            'glaucoma_count': glaucoma_count,
            'normal_count': normal_count,
            'avg_confidence': avg_conf,
            'high_risk_iop_count': high_risk_iop
        },
        'filter': disease_filter
    })

@app.route('/api/patients/<record_id>', methods=['GET'])
def get_patient_detail(record_id):
    """Retrieve full details for a single patient record including high-res image and annotations."""
    col = get_db_collection()
    patient = None

    if col is not None:
        try:
            if ObjectId.is_valid(record_id):
                patient = col.find_one({'_id': ObjectId(record_id)})
            if not patient:
                patient = col.find_one({'patient_id': record_id})
        except Exception as e:
            print(f"[WARNING] Single patient lookup error: {e}")

    if not patient:
        for r in local_patient_records:
            if r.get('id') == record_id or r.get('patient_id') == record_id:
                patient = r
                break

    if not patient:
        return jsonify({'error': 'Patient record not found.'}), 404

    if '_id' in patient:
        patient['id'] = str(patient.pop('_id'))

    return jsonify({'success': True, 'patient': patient})

@app.route('/api/patients/<record_id>', methods=['DELETE'])
def delete_patient(record_id):
    """Delete a patient record."""
    col = get_db_collection()
    deleted = False

    if col is not None:
        try:
            if ObjectId.is_valid(record_id):
                res = col.delete_one({'_id': ObjectId(record_id)})
                if res.deleted_count > 0:
                    deleted = True
            if not deleted:
                res = col.delete_one({'patient_id': record_id})
                if res.deleted_count > 0:
                    deleted = True
        except Exception as e:
            print(f"[WARNING] Single patient delete error: {e}")

    global local_patient_records
    local_patient_records = [r for r in local_patient_records if r.get('id') != record_id and r.get('patient_id') != record_id]

    return jsonify({'success': True, 'message': 'Record deleted successfully.'})

@app.route('/api/seed-historical-glaucoma', methods=['POST'])
def seed_historical_glaucoma():
    """Manual trigger to re-seed realistic historical glaucoma records."""
    col = get_db_collection()
    ensure_historical_patients_seeded(col)
    return jsonify({
        'success': True,
        'message': f'Successfully seeded {len(SEED_PATIENTS)} historical patients into Glaucoma Registry.'
    })

@app.route('/api/export-patients', methods=['GET'])
def export_patients_csv():
    """Export all patient history as a downloadable CSV file."""
    col = get_db_collection()
    records = []
    if col is not None:
        try:
            cursor = col.find({}).sort('timestamp', -1)
            for d in cursor:
                records.append(d)
        except Exception:
            records = list(local_patient_records)
    else:
        records = list(local_patient_records)

    output = io.StringIO()
    writer = csv.writer(output)
    # Header
    writer.writerow([
        'Patient ID', 'Patient Name', 'Age', 'Gender', 'Examined Eye',
        'Diagnosis', 'AI Confidence (%)', 'Severity', 'IOP (mmHg)', 'Cup-to-Disc Ratio',
        'Date & Time (UTC)', 'Clinical Notes'
    ])

    for r in records:
        writer.writerow([
            r.get('patient_id', 'N/A'),
            r.get('patient_name', 'Anonymous'),
            r.get('age', ''),
            r.get('gender', ''),
            r.get('eye_type', ''),
            r.get('prediction', ''),
            r.get('confidence', ''),
            r.get('severity', ''),
            r.get('iop', ''),
            r.get('cup_disc_ratio', ''),
            r.get('timestamp', ''),
            r.get('notes', '')
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=glaucoma_patients_registry.csv"}
    )

@app.route('/api/db-status', methods=['GET'])
def db_status():
    col = get_db_collection()
    if col is not None:
        try:
            count = col.count_documents({})
            glaucoma_count = col.count_documents({'prediction': {'$regex': '^glaucoma$', '$options': 'i'}})
            return jsonify({
                'status': 'connected',
                'database': MONGO_DB_NAME,
                'collection': 'scans',
                'total_records': count,
                'glaucoma_records': glaucoma_count
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({
        'status': 'fallback',
        'message': 'Running on high-availability local storage',
        'total_records': len(local_patient_records),
        'glaucoma_records': sum(1 for r in local_patient_records if r.get('prediction', '').lower() == 'glaucoma')
    }), 200

# ==============================================================================
# PATIENT HISTORY ENDPOINTS
# ==============================================================================

@app.route('/api/history', methods=['GET'])
@app.route('/api/patient-history', methods=['GET'])
@app.route('/api/patients/history', methods=['GET'])
def patient_history():
    """Retrieve all patient records with optional query filtering (?disease=glaucoma, ?search=..., ?sort=..., ?limit=...)."""
    return get_patients()

@app.route('/api/patient-history/<patient_id>', methods=['GET'])
def single_patient_longitudinal_history(patient_id):
    """Retrieve full longitudinal history for a specific patient ID, including all scans and tonometer readings."""
    col = get_db_collection()
    ton_col = get_tonometer_collection()
    
    patient_scans = []
    tonometer_readings = []
    
    # Fetch scans from MongoDB
    if col is not None:
        try:
            query = {
                '$or': [
                    {'patient_id': patient_id},
                    {'id': patient_id}
                ]
            }
            if ObjectId.is_valid(patient_id):
                query['$or'].append({'_id': ObjectId(patient_id)})
                
            cursor = col.find(query).sort('timestamp', -1)
            for d in cursor:
                d['id'] = str(d.pop('_id'))
                patient_scans.append(d)
        except Exception as e:
            print(f"[WARNING] Single patient history lookup error: {e}")

    # Fallback to local memory if empty
    if not patient_scans:
        patient_scans = [
            r for r in local_patient_records
            if r.get('patient_id') == patient_id or r.get('id') == patient_id
        ]

    if not patient_scans:
        return jsonify({'error': f'No records found for Patient ID: {patient_id}'}), 404

    # Fetch associated tonometer pressure measurements
    if ton_col is not None:
        try:
            ton_cursor = ton_col.find({'patient_id': patient_id}).sort('timestamp', -1).limit(50)
            for t in ton_cursor:
                t['id'] = str(t.pop('_id'))
                tonometer_readings.append(t)
        except Exception as e:
            print(f"[WARNING] Tonometer history lookup error: {e}")

    if not tonometer_readings:
        tonometer_readings = [
            t for t in local_tonometer_readings
            if t.get('patient_id') == patient_id
        ]

    # Calculate summary IOP statistics
    all_iops = [float(s.get('iop', 0)) for s in patient_scans if s.get('iop') is not None]
    all_iops += [float(t.get('iop', 0)) for t in tonometer_readings if t.get('iop') is not None]
    
    latest_scan = patient_scans[0]
    avg_iop = round(sum(all_iops) / len(all_iops), 1) if all_iops else latest_scan.get('iop', 18.0)
    max_iop = max(all_iops) if all_iops else latest_scan.get('iop', 18.0)
    status_label, risk_desc, _ = classify_iop(avg_iop)

    return jsonify({
        'success': True,
        'patient_id': patient_id,
        'patient_name': latest_scan.get('patient_name', f'Patient {patient_id}'),
        'age': latest_scan.get('age', 50),
        'gender': latest_scan.get('gender', 'Unspecified'),
        'eye_type': latest_scan.get('eye_type', 'OD (Right Eye)'),
        'current_diagnosis': latest_scan.get('prediction', 'Unknown'),
        'confidence': latest_scan.get('confidence', 0.0),
        'severity': latest_scan.get('severity', 'Evaluation completed'),
        'average_iop': avg_iop,
        'peak_iop': max_iop,
        'iop_risk_classification': risk_desc,
        'total_scans_recorded': len(patient_scans),
        'scans_history': patient_scans,
        'tonometer_readings': tonometer_readings
    })

# ==============================================================================
# BLE TONOMETER & PRESSURE SENSOR ENDPOINTS
# ==============================================================================

@app.route('/api/tonometer', methods=['GET', 'POST'])
@app.route('/api/pressure', methods=['GET', 'POST'])
def handle_tonometer():
    """
    POST: Receive IOP pressure reading from ESP32 BLE Tonometer or WiFi gateway.
    GET: Retrieve current live reading and device status.
    """
    global latest_tonometer_reading
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'reading': latest_tonometer_reading,
            'device': latest_tonometer_reading.get('device_id', 'ESP32-BLE-Tonometer')
        })

    # POST handling
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        
        # Read IOP or pressure value
        iop_val = data.get('iop') if data.get('iop') is not None else data.get('pressure')
        if iop_val is None:
            return jsonify({
                'error': 'Missing required pressure data. Provide {"iop": <number>} or {"pressure": <number>}'
            }), 400

        iop = round(float(iop_val), 1)
        raw_adc = data.get('raw_adc') or data.get('raw')
        patient_id = data.get('patient_id') or None
        patient_name = data.get('patient_name') or None
        eye_type = data.get('eye_type', 'OD (Right Eye)')
        device_id = data.get('device_id', 'ESP32-BLE-Tonometer')
        notes = data.get('notes', 'Real-time BLE Tonometer probe measurement.')

        status, risk_desc, alert_class = classify_iop(iop)

        reading_doc = {
            'iop': iop,
            'raw_adc': int(raw_adc) if raw_adc is not None else None,
            'status': status,
            'risk_level': risk_desc,
            'alert_class': alert_class,
            'patient_id': patient_id,
            'patient_name': patient_name,
            'eye_type': eye_type,
            'device_id': device_id,
            'notes': notes,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # Update in-memory state
        latest_tonometer_reading = dict(reading_doc)
        local_tonometer_readings.insert(0, reading_doc)
        if len(local_tonometer_readings) > 100:
            local_tonometer_readings.pop()

        # Save into MongoDB tonometer collection
        mongo_id = None
        ton_col = get_tonometer_collection()
        if ton_col is not None:
            try:
                res = ton_col.insert_one(dict(reading_doc))
                mongo_id = str(res.inserted_id)
                reading_doc['id'] = mongo_id
                print(f"[INFO] Tonometer reading stored in MongoDB with ID: {mongo_id}")
            except Exception as e:
                print(f"[WARNING] MongoDB tonometer insertion error: {e}")

        # If a patient_id was specified, link/update IOP on that patient's latest record
        if patient_id:
            col = get_db_collection()
            if col is not None:
                try:
                    col.update_many(
                        {'patient_id': patient_id},
                        {'$set': {'iop': iop, 'last_tonometer_sync': reading_doc['timestamp']}}
                    )
                except Exception as e:
                    print(f"[WARNING] Could not update patient IOP in scans: {e}")

        return jsonify({
            'success': True,
            'message': 'Tonometer reading recorded successfully.',
            'id': mongo_id or f"local-{len(local_tonometer_readings)}",
            'iop': iop,
            'status': status,
            'risk_level': risk_desc,
            'patient_id': patient_id,
            'timestamp': reading_doc['timestamp']
        }), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to process tonometer reading: {str(e)}'}), 500

@app.route('/api/tonometer/latest', methods=['GET'])
@app.route('/api/pressure/latest', methods=['GET'])
def get_latest_tonometer():
    """Retrieve the single most recent IOP pressure reading recorded by any ESP32 tonometer."""
    return jsonify({
        'success': True,
        'reading': latest_tonometer_reading
    })

@app.route('/api/tonometer/history', methods=['GET'])
@app.route('/api/pressure/history', methods=['GET'])
def get_tonometer_history():
    """Retrieve past tonometer readings (?patient_id=..., ?limit=50)."""
    patient_id = request.args.get('patient_id')
    limit = min(int(request.args.get('limit', 50)), 100)

    ton_col = get_tonometer_collection()
    records = []

    if ton_col is not None:
        try:
            query = {'patient_id': patient_id} if patient_id else {}
            cursor = ton_col.find(query).sort('timestamp', -1).limit(limit)
            for d in cursor:
                d['id'] = str(d.pop('_id'))
                records.append(d)
        except Exception as e:
            print(f"[WARNING] MongoDB tonometer history error: {e}")

    if not records:
        if patient_id:
            records = [t for t in local_tonometer_readings if t.get('patient_id') == patient_id][:limit]
        else:
            records = list(local_tonometer_readings)[:limit]

    return jsonify({
        'success': True,
        'count': len(records),
        'records': records
    })

# ==============================================================================
# ESP32-CAM INGESTION ENDPOINT
# ==============================================================================

@app.route('/api/cam_predict', methods=['POST'])
def cam_predict():
    """Endpoint for ESP32-CAM to push a captured eye photo and run automated YOLO inference."""
    try:
        if request.content_type == 'image/jpeg':
            image_bytes = request.data
        elif 'image' in request.files:
            image_bytes = request.files['image'].read()
        else:
            return jsonify({'error': 'Unsupported content type or missing image. Send JPEG binary or multipart form file "image".'}), 400

        pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        primary_class, confidence_pct, detections, img_url = run_inference(pil_img, conf_thresh=0.25)
        thumbnail_b64 = generate_base64_thumbnail(pil_img, size=(180, 180))

        patient_id = request.form.get('patient_id') or request.args.get('patient_id') or f"CAM-2026-{random.randint(1000, 9999)}"
        patient_name = request.form.get('patient_name') or f"ESP32-CAM Capture ({patient_id})"
        eye_type = request.form.get('eye_type', 'OD (Right Eye)')
        
        # Link current live tonometer IOP reading
        current_iop = latest_tonometer_reading.get('iop', 18.0)
        is_glaucoma = (primary_class.lower() == 'glaucoma')
        severity = "High Cupping / Elevated Pressure" if (is_glaucoma and current_iop >= 22.0) else ("Confirmed Glaucoma" if is_glaucoma else "Healthy Normal Retina")

        record = {
            'patient_id': patient_id,
            'patient_name': patient_name,
            'age': 55,
            'gender': 'Unspecified',
            'eye_type': eye_type,
            'iop': current_iop,
            'cup_disc_ratio': 0.7 if is_glaucoma else 0.35,
            'notes': f"Direct ESP32-CAM optical capture. Paired with Tonometer IOP: {current_iop} mmHg.",
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'filename': f"esp32_cam_{patient_id}.jpg",
            'prediction': primary_class,
            'confidence': confidence_pct,
            'severity': severity,
            'expected_class': None,
            'accuracy_match': None,
            'detections_count': len(detections),
            'detections': detections,
            'thumbnail': thumbnail_b64 if thumbnail_b64 else img_url,
            'image_url': img_url,
            'is_glaucoma': is_glaucoma,
            'source': 'ESP32-CAM'
        }

        # Store in MongoDB
        mongo_doc_id = None
        col = get_db_collection()
        if col is not None:
            try:
                res = col.insert_one(record)
                mongo_doc_id = str(res.inserted_id)
                record['id'] = mongo_doc_id
            except Exception as e:
                print(f"[WARNING] Could not save CAM scan to MongoDB: {e}")

        if not mongo_doc_id:
            record['id'] = f"local-cam-{len(local_patient_records)+1}"
        local_patient_records.insert(0, record)

        return jsonify({
            'success': True,
            'prediction': primary_class,
            'confidence': confidence_pct,
            'severity': severity,
            'iop_linked': current_iop,
            'record_id': record['id'],
            'image_url': img_url
        }), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'CAM prediction failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[INFO] Web App starting at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
