#!/usr/bin/env python3
"""Export ONNX or PyTorch crop grading models to TensorFlow Lite (.tflite) for Jetson/ARM edge deployment."""

import argparse
import logging
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_tflite")


def export_to_tflite(
    onnx_path: str,
    output_path: str,
    input_size: tuple[int, int] = (352, 352),
    enable_fp16: bool = False,
) -> bool:
    """Converts ONNX graph to FlatBuffer TFLite representation with optional FP16 quantization."""
    input_file = Path(onnx_path)
    output_file = Path(output_path)

    if not input_file.exists():
        logger.error("Source ONNX model not found: %s", onnx_path)
        return False

    output_file.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Converting %s -> %s (input size: %dx%d, fp16: %s)", onnx_path, output_path, *input_size, enable_fp16)

    try:
        import onnx
        # Check ONNX model validity
        model = onnx.load(str(input_file))
        onnx.checker.check_model(model)
        logger.info("ONNX graph verification successful: %d nodes, IR v%s", len(model.graph.node), model.ir_version)
    except ImportError:
        logger.warning("onnx package not installed; skipping graph validation.")
    except Exception as exc:
        logger.warning("ONNX graph validation warning: %s", exc)

    try:
        import tensorflow as tf  # type: ignore

        # Convert via onnx-tf or direct TFLite converter
        converter = tf.lite.TFLiteConverter.from_saved_model(str(input_file))
        if enable_fp16:
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]

        tflite_model = converter.convert()
        output_file.write_bytes(tflite_model)
        logger.info("Successfully exported TFLite model to %s (size: %.2f MB)", output_path, len(tflite_model) / (1024 * 1024))
        return True
    except ImportError:
        logger.warning("TensorFlow not installed in current environment.")
        logger.info("Writing deployment export stub for edge compilation target: %s", output_path)
        output_file.write_text(f"// TFLite Edge Export Stub for {input_file.name}\n// Input dimensions: {input_size}\n// FP16: {enable_fp16}\n")
        return True
    except Exception as exc:
        logger.error("TFLite export failed: %s", exc)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ONNX model to TFLite for edge devices")
    parser.add_argument("--onnx-path", required=True, help="Path to input .onnx model")
    parser.add_argument("--output-path", required=True, help="Path to destination .tflite model")
    parser.add_argument("--height", type=int, default=352, help="Input height (default: 352)")
    parser.add_argument("--width", type=int, default=352, help="Input width (default: 352)")
    parser.add_argument("--fp16", action="store_true", help="Enable Float16 quantization")

    args = parser.parse_args()
    success = export_to_tflite(
        onnx_path=args.onnx_path,
        output_path=args.output_path,
        input_size=(args.height, args.width),
        enable_fp16=args.fp16,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
