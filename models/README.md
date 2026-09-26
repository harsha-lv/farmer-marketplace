# Edge Computer Vision Model Repository & Registry Protocol

This directory contains trained ONNX model artifacts for edge computer vision crop quality evaluation on NVIDIA Jetson and edge gateway hardware.

---

## 1. Directory Structure

Place trained ONNX weights in their designated subdirectories:

```text
models/
├── detector/
│   ├── yolo_fastestv2_eca_simlightfpn_v1.0.onnx
│   └── yolo_fastestv2_eca_simlightfpn_v1.1_int8.onnx
├── segmentor/
│   ├── mask_rcnn_mobilenetv3_v1.0.onnx
│   └── mask_rcnn_mobilenetv3_v1.0_int8.onnx
├── texture/
│   ├── efficientnet_b0_texture_v1.0.onnx
│   └── efficientnet_b0_texture_v1.0_int8.onnx
└── README.md
```

---

## 2. Model Discovery & Version Resolution

The backend connects to the database registry table (`app.assay_models`) to discover and load models:

1. **Resolution Priority**:
   - The registry selects models by role: `detector`, `segmentor`, and `texture`.
   - For each role, the engine queries `SELECT * FROM app.assay_models WHERE name = :role AND status = 'active'`.
   - The engine deterministically picks the **highest semantic version** (e.g. `v1.2.0` over `v1.1.0`).
2. **Shadow Model Execution**:
   - Models marked with `status = 'shadow'` run asynchronously in parallel background threads.
   - Shadow inference results are logged for performance monitoring and never overwrite user-facing scores.
3. **Integrity Verification**:
   - On load, the engine calculates the file's SHA-256 hash and verifies it against the `sha256` column in `assay_models`.
4. **First-Class Fallback Guarantee (Zero-500 State)**:
   - If weights are missing, corrupt, or unregistered, the system **never fails or returns HTTP 500**.
   - The service transparently activates the rule-based grader (`app.lots.grading.evaluate_crop_quality`) and returns:
     ```json
     {
       "model_versions": null,
       "fallback": "rule_based"
     }
     ```

---

## 3. Registering Models via REST API

To register an ONNX model artifact in the database registry:

```bash
# 1. Calculate SHA-256 of the model weight file
sha256sum models/detector/yolo_fastestv2_eca_simlightfpn_v1.0.onnx
# Output: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

# 2. Register model with the API
curl -X POST "http://localhost:8000/api/v1/assay-models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "detector",
    "version": "1.0.0",
    "architecture": "YOLO-FastestV2+ECA+EMA+SimLightFPN",
    "onnx_path": "models/detector/yolo_fastestv2_eca_simlightfpn_v1.0.onnx",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "input_size": [1, 3, 352, 352],
    "class_map": {
      "0": "grain_kernel",
      "1": "foreign_matter",
      "2": "damaged_kernel",
      "3": "weevil_pest"
    },
    "metrics": {
      "mAP_50": 0.912,
      "mAP_50_95": 0.698,
      "precision": 0.924,
      "recall": 0.891
    },
    "status": "active"
  }'
```

---

## 4. Querying Active Models

To view all registered models and their statuses:

```bash
curl -X GET "http://localhost:8000/api/v1/assay-models" \
  -H "Authorization: Bearer $TOKEN"
```
