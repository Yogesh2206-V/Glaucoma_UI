# 👁️ OculoScan AI — YOLO11 Glaucoma & Optic Disc Testing Studio

A diagnostic and model validation web studio for your trained **`best.pt`** YOLO11 neural network.

---

## 🔬 Model Analysis Summary (`best.pt`)

- **Architecture**: **YOLO11 Nano (`yolo11n`)** Detection Model
- **Task**: Object Detection (`detect`)
- **Trained Classes**: 
  - `0: Glaucoma`
  - `1: Normal`
- **Model Parameters**: `2,590,230` (~2.59M parameters)
- **Model Depth**: `181 layers`
- **Computational Complexity**: `6.44 GFLOPs`
- **Trained Input Resolution**: `640 × 640 px`
- **Training Config**: `25 epochs`, `AdamW optimizer` (`lr0=0.001667`), `batch size: 16`
- **Source Dataset**: `Glaucoma.v1i.yolov11`

---

## 🚀 Key Features

1. **Interactive Image Testing**:
   - Drag & drop or browse retinal fundus images (JPG, PNG, DICOM, BMP).
   - Built-in **Quick Test Samples** for instant testing without uploading files.
2. **Ground Truth & Accuracy Checker**:
   - Select expected ground truth class (`Glaucoma` or `Normal`).
   - Live accuracy score banner (`True Positive`, `True Negative`, `False Positive`, `False Negative`).
   - Real-time **Session Accuracy Score Tracker** (Total tests, Correct predictions, Mismatches, Accuracy %).
3. **Detection Visualizer & Controls**:
   - Toggle between **Annotated Detection**, **Side-by-Side (Split)**, and **Original Input**.
   - Adjustable **Confidence Threshold** (1% - 95%) and **IoU NMS Threshold**.
   - Bounding box telemetry table (coordinates, width, height, area %).
   - One-click annotated output download.
4. **Batch Dataset Benchmark**:
   - Upload multiple retinal fundus images to run automated evaluation with latency and class breakdown.

---

## 💻 How to Run

Double-click `run.bat` or execute in terminal:

```bash
python app.py
```

Then open your browser at: **[http://localhost:5000](http://localhost:5000)**
