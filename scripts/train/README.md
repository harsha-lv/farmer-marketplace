# Edge Crop Grading Training Pipeline & Dataset Manifest Specification

This guide describes the dataset preparation, COCO-style annotation schema, and training protocols for deploying computer vision crop grading models under a **15 W power budget** on NVIDIA Jetson / ARM edge platforms.

---

## 1. Dataset Manifest Format (COCO-Style Annotations)

All training, validation, and benchmark datasets are formatted in standardized COCO JSON format partitioned by agricultural commodity (`wheat`, `paddy`, `maize`, `pulses`, `oilseeds`).

### 1.1 JSON Manifest Structure (`manifest.json`)

```json
{
  "info": {
    "description": "Agri-Market Edge CV Crop Quality Dataset",
    "version": "1.0.0",
    "year": 2026,
    "contributor": "Agri-Stack Quality Standards Consortium",
    "date_created": "2026-09-25T00:00:00Z"
  },
  "commodity": "wheat",
  "agmark_standard": "AGMARK-WHEAT-2024",
  "categories": [
    {
      "id": 1,
      "name": "grain_kernel",
      "supercategory": "crop"
    },
    {
      "id": 2,
      "name": "foreign_matter",
      "supercategory": "defect"
    },
    {
      "id": 3,
      "name": "damaged_kernel",
      "supercategory": "defect"
    },
    {
      "id": 4,
      "name": "weevil_pest",
      "supercategory": "pest"
    },
    {
      "id": 5,
      "name": "discolored_grain",
      "supercategory": "defect"
    }
  ],
  "images": [
    {
      "id": 1001,
      "file_name": "wheat_sample_001.jpg",
      "width": 1920,
      "height": 1080,
      "captured_at": "2026-09-20T10:15:30Z",
      "tray_calibration_scale_px_per_mm": 18.4,
      "sha256": "a3b2c1d0e4f5..."
    }
  ],
  "annotations": [
    {
      "id": 5001,
      "image_id": 1001,
      "category_id": 1,
      "bbox": [245.5, 312.0, 48.0, 22.5],
      "area": 1080.0,
      "segmentation": [
        [245.5, 312.0, 293.5, 312.0, 293.5, 334.5, 245.5, 334.5]
      ],
      "iscrowd": 0,
      "attributes": {
        "length_mm": 6.4,
        "width_mm": 2.8,
        "shriveled": false
      }
    },
    {
      "id": 5002,
      "image_id": 1001,
      "category_id": 3,
      "bbox": [410.0, 520.0, 32.0, 18.0],
      "area": 576.0,
      "segmentation": [
        [410.0, 520.0, 442.0, 520.0, 442.0, 538.0, 410.0, 538.0]
      ],
      "iscrowd": 0,
      "attributes": {
        "defect_type": "insect_bored",
        "affected_surface_pct": 35.0
      }
    }
  ]
}
```

---

## 2. Model Architecture Training Specifications (<15 W Envelope)

To guarantee real-time latency (<800ms) under a strict 15 W power envelope on Jetson Orin Nano / Nano / ARM Cortex-A78:

### 2.1 Object Detector: YOLO-FastestV2 + ECA + EMA + SimLightFPN
- **Role**: High-density small-object detection (counting hundreds of 2–8 mm grain kernels per sample tray).
- **Backbone**: ShufflenetV2 with **ECA** (Efficient Channel Attention) for selective channel weighting with near-zero FLOP overhead.
- **Neck**: **SimLightFPN** (Simplified Light Feature Pyramid Network) for multi-scale feature reuse without heavy cross-stage connections.
- **Optimization**: Exponential Moving Average (**EMA**) with decay rate 0.999 to stabilize small-target gradient updates.
- **Input Dimension**: `1x3x352x352` float32.
- **Target Metrics**: mAP@0.5 >= 0.88, inference time <= 18ms on Jetson GPU, <= 45ms on CPU.

### 2.2 Instance Segmentor: Mask R-CNN (MobileNetV3 Backbone)
- **Role**: Precise boundary segmentation for mold, fungal growth, kernel discoloration, and black point disease.
- **Outputs**: Binary pixel masks per kernel used to integrate the exact affected-area percentage.
- **Input Dimension**: `1x3x384x384` float32.
- **Losses**: Smooth L1 Box Loss + Binary Cross-Entropy Mask Loss.

### 2.3 Texture Classifier: EfficientNet-B0
- **Role**: Micro-texture surface roughness analysis (e.g. safflower filament integrity, moisture wrinkling, seed coat cracking).
- **Input Dimension**: `1x3x224x224` float32.

---

## 3. Training & Export Execution Pipeline

```bash
# 1. Train detector with ECA and SimLightFPN
python train_detector.py \
  --manifest data/wheat/manifest.json \
  --epochs 150 \
  --batch-size 32 \
  --img-size 352 \
  --backbone shufflenetv2_eca \
  --output-dir checkpoints/detector/

# 2. Export trained PyTorch weights to ONNX
python export_onnx.py \
  --weights checkpoints/detector/best.pt \
  --output models/detector/yolo_fastestv2_wheat_v1.onnx \
  --img-size 352 352 \
  --opset 17

# 3. Quantize to INT8 for Jetson edge deployment
python scripts/quantize.py \
  --input-onnx models/detector/yolo_fastestv2_wheat_v1.onnx \
  --output-onnx models/detector/yolo_fastestv2_wheat_v1_int8.onnx \
  --per-channel

# 4. Evaluate mAP and per-class reports
python scripts/eval_map.py \
  --manifest data/wheat/val_manifest.json \
  --output-json reports/wheat_detector_eval.json
```
