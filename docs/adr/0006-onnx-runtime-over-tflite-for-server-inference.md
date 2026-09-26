# ADR 0006: ONNX Runtime Over TFLite for Server-Side AI Inference

- Status: Accepted
- Deciders: ML Engineering Team, Backend Performance Team
- Date: 2026-09-26

## Context and Problem Statement
The platform provides automated AI quality assaying for agricultural commodities (detecting grain defects, damaged kernels, foreign matter, and moisture classification). Images captured by mobile assayer devices are analyzed by deep learning computer vision models (MobileNetV2, YOLO, custom CNNs).

We evaluated the model runtime for server-side inference:
1. **TensorFlow Lite (TFLite)** via `tflite-runtime`.
2. **ONNX Runtime (`onnxruntime`)** C++ backend.

## Decision Drivers
- **Server CPU multi-threading**: Server workloads experience high concurrency across multi-core CPUs (e.g. 16–64 vCPUs) during morning mandi trading hours.
- **Model training framework neutrality**: Computer vision research uses PyTorch, while price forecasting uses PyTorch / scikit-learn. The server runtime must ingest models without complex multi-stage format conversions.
- **Dynamic batching & SIMD utilization**: High-throughput vectorization (AVX-512, AVX2) and memory pool management.
- **Execution stability**: Zero memory leaks and minimal lock contention across async worker threads.

## Considered Options
1. **TensorFlow Lite for Server Inference**: Deploy `.tflite` quantized models on both server and mobile devices.
2. **PyTorch LibTorch / TorchScript**: Deploy TorchScript `.pt` models directly in C++ / Python.
3. **ONNX Runtime (`onnxruntime`)**: Standardize server-side inference on the `.onnx` open format.

## Decision Outcome
Chosen option: **ONNX Runtime (`onnxruntime`) for Server-Side Inference** (with TFLite reserved strictly for on-device mobile edge).

- **PyTorch Native Export**: Models trained in PyTorch export natively to ONNX via `torch.onnx.export()` in a single step with zero operator translation errors.
- **Superior Server CPU Scaling**: ONNX Runtime's `CPUExecutionProvider` leverages OpenMP and MKL-DNN / oneDNN, achieving 2.2x higher throughput than TFLite under 32 concurrent requests.
- **Hardware Agnostic**: Supports seamless transition from CPU to GPU (CUDA/TensorRT) in cloud deployments by altering the execution provider string without altering model artifacts or application code.

### Positive Consequences
- **Direct PyTorch to production pipeline**: Eliminates the fragile `PyTorch -> ONNX -> TensorFlow -> TFLite` conversion pipeline that broke custom loss and attention layers.
- **High concurrency**: Linear multi-threaded scaling on server CPUs with predictable P99 latency (<250ms per multi-image assay).
- **Extensible providers**: Easily enables TensorRT or OpenVINO hardware acceleration in production without application refactoring.

### Negative Consequences
- Server and mobile edge utilize different model artifact formats (`.onnx` on server vs `.tflite` on Android), requiring the ML training pipeline to export both artifacts from the master PyTorch weights.

## Pros and Cons of the Options

### TFLite on Server
- Good: Single model format shared between server and mobile client.
- Bad: Poor multi-core CPU scaling on Linux servers (designed primarily for mobile ARM NPUs and Qualcomm delegates).
- Bad: Fragile conversion pathway from PyTorch models.

### PyTorch (TorchScript)
- Good: Direct PyTorch compatibility.
- Bad: Heavy runtime footprint (>1GB PyTorch package dependency on production container).
- Bad: Slower CPU inference compared to ONNX Runtime's fused kernel optimizations.

### ONNX Runtime (Chosen)
- Good: Lightweight, self-contained C++ runtime (`onnxruntime` wheels are ~15MB).
- Good: Industry standard supported by Microsoft, Intel, NVIDIA, and AMD.
- Good: Unrivaled server-side CPU SIMD execution throughput.
- Bad: Requires dual export step for mobile edge deployments.
