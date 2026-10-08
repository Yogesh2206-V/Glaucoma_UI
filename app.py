import os
import io
import base64
import datetime
import numpy as np
from PIL import Image
import cv2
import onnxruntime as ort
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

# Load environment variables from .env file
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

# Base paths for local and cloud/serverless environments
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
MODEL_ONNX_PATH = os.path.join(BASE_DIR, 'best.onnx')

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
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)

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

    expected_class = request.form.get('expected_class', '').strip()

    try:
        image_bytes = file.read()
        pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        primary_class, confidence_pct, detections, img_url = run_inference(pil_img, conf_thresh=0.25)

        # Save record to MongoDB Atlas
        mongo_doc_id = None
        try:
            col = get_db_collection()
            if col is not None:
                record = {
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'filename': file.filename,
                    'prediction': primary_class,
                    'confidence': confidence_pct,
                    'expected_class': expected_class if expected_class else None,
                    'accuracy_match': (primary_class.lower() == expected_class.lower()) if expected_class else None,
                    'detections_count': len(detections),
                    'detections': detections
                }
                res = col.insert_one(record)
                mongo_doc_id = str(res.inserted_id)
                print(f"[INFO] Scan result saved to MongoDB with ID: {mongo_doc_id}")
        except Exception as mongo_err:
            print(f"[WARNING] Could not save record to MongoDB: {mongo_err}")

        return jsonify({
            'success': True,
            'prediction': primary_class,
            'confidence': confidence_pct,
            'detections': detections,
            'image_url': img_url,
            'db_saved': mongo_doc_id is not None,
            'record_id': mongo_doc_id
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500

@app.route('/api/db-status', methods=['GET'])
def db_status():
    col = get_db_collection()
    if col is not None:
        try:
            count = col.count_documents({})
            return jsonify({
                'status': 'connected',
                'database': MONGO_DB_NAME,
                'collection': 'scans',
                'total_records': count
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'disconnected', 'message': 'Could not connect to MongoDB Atlas'}), 503

@app.route('/api/history', methods=['GET'])
def history():
    col = get_db_collection()
    if col is None:
        return jsonify({'error': 'MongoDB not connected'}), 503
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
        docs = list(col.find({}, {'_id': 1, 'timestamp': 1, 'filename': 1, 'prediction': 1, 'confidence': 1, 'expected_class': 1}).sort('timestamp', -1).limit(limit))
        for d in docs:
            d['id'] = str(d.pop('_id'))
        return jsonify({'success': True, 'records': docs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[INFO] Web App starting at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

