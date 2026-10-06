import os
import io
import base64
from PIL import Image
import cv2
from ultralytics import YOLO
from flask import Flask, render_template, request, jsonify

# Base paths for local and cloud/serverless environments
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# Lazy/global load model
model = None
def get_model():
    global model
    if model is None:
        try:
            model = YOLO(MODEL_PATH)
            print("✅ YOLO Model loaded successfully from:", MODEL_PATH)
        except Exception as e:
            print("❌ Error loading model:", e)
            model = None
    return model

# Warm up model on startup
get_model()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    yolo_model = get_model()
    if yolo_model is None:
        return jsonify({'error': 'Model could not be loaded.'}), 500

    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded.'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected.'}), 400

    try:
        # Read image
        image_bytes = file.read()
        pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        # Run inference
        results = yolo_model(pil_img, conf=0.25)
        res = results[0]

        # Extract predictions
        detections = []
        primary_class = "No Detection"
        confidence_pct = 0.0

        if len(res.boxes) > 0:
            top_box = res.boxes[0]
            cls_id = int(top_box.cls[0].item())
            primary_class = yolo_model.names.get(cls_id, f"Class {cls_id}")
            confidence_pct = round(float(top_box.conf[0].item()) * 100, 1)

            for b in res.boxes:
                c_id = int(b.cls[0].item())
                detections.append({
                    'class': yolo_model.names.get(c_id, f"Class {c_id}"),
                    'confidence': round(float(b.conf[0].item()) * 100, 1)
                })

        # Render annotated image
        annotated_bgr = res.plot()
        annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
        annotated_pil = Image.fromarray(annotated_rgb)

        # Convert to base64
        buf = io.BytesIO()
        annotated_pil.save(buf, format='JPEG')
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return jsonify({
            'success': True,
            'prediction': primary_class,
            'confidence': confidence_pct,
            'detections': detections,
            'image_url': f"data:image/jpeg;base64,{img_b64}"
        })

    except Exception as e:
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Web App starting at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
