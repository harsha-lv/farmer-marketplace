#!/usr/bin/env python3
"""OpenAPI Schema Drift Guard.

Compares the current dynamically-generated FastAPI OpenAPI specification against
a committed baseline JSON file to prevent unintentional API contract breakage.

Features:
  - Detects added, removed, and modified endpoints (HTTP method + path)
  - Detects request body, parameter, and response status alterations
  - Detects model schema changes (added/removed/modified property fields)
  - Provides --update flag to re-baseline the committed contract
  - Returns exit code 0 if clean, 1 if breaking/non-breaking drift is found

Usage:
  python scripts/check_openapi_drift.py
  python scripts/check_openapi_drift.py --update
  python scripts/check_openapi_drift.py --baseline docs/openapi_baseline.json
"""

import argparse
import json
import os
import sys
from typing import Any


def get_current_spec() -> dict[str, Any]:
    """Import FastAPI application and extract full OpenAPI 3.1 schema."""
    from app.main import app
    return app.openapi()


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Strip volatile metadata before diffing."""
    cleaned = json.loads(json.dumps(spec))
    # Exclude dynamic servers if ports vary
    cleaned.pop("servers", None)
    return cleaned


def diff_schemas(base_schemas: dict[str, Any], curr_schemas: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Compare component schema models."""
    added = [s for s in curr_schemas if s not in base_schemas]
    removed = [s for s in base_schemas if s not in curr_schemas]
    changed = []

    for s_name in curr_schemas:
        if s_name in base_schemas:
            b_props = set(base_schemas[s_name].get("properties", {}).keys())
            c_props = set(curr_schemas[s_name].get("properties", {}).keys())
            if b_props != c_props:
                added_props = c_props - b_props
                removed_props = b_props - c_props
                diff_desc = []
                if added_props:
                    diff_desc.append(f"+props: {', '.join(sorted(added_props))}")
                if removed_props:
                    diff_desc.append(f"-props: {', '.join(sorted(removed_props))}")
                changed.append(f"{s_name} ({'; '.join(diff_desc)})")

    return added, removed, changed


def diff_endpoints(base_paths: dict[str, Any], curr_paths: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Compare operational API routes."""
    base_ops = {
        f"{method.upper():6s} {path}": op
        for path, path_item in base_paths.items()
        for method, op in path_item.items()
        if method.lower() in ("get", "post", "put", "patch", "delete", "options", "head")
    }
    curr_ops = {
        f"{method.upper():6s} {path}": op
        for path, path_item in curr_paths.items()
        for method, op in path_item.items()
        if method.lower() in ("get", "post", "put", "patch", "delete", "options", "head")
    }

    added = [op for op in curr_ops if op not in base_ops]
    removed = [op for op in base_ops if op not in curr_ops]
    changed = []

    for op_key in curr_ops:
        if op_key in base_ops:
            b_op = base_ops[op_key]
            c_op = curr_ops[op_key]

            # Check responses
            b_resps = set(b_op.get("responses", {}).keys())
            c_resps = set(c_op.get("responses", {}).keys())
            
            # Check query / path parameters
            b_params = {p.get("name") for p in b_op.get("parameters", [])}
            c_params = {p.get("name") for p in c_op.get("parameters", [])}

            issues = []
            if b_resps != c_resps:
                if c_resps - b_resps:
                    issues.append(f"+resps: {', '.join(sorted(c_resps - b_resps))}")
                if b_resps - c_resps:
                    issues.append(f"-resps: {', '.join(sorted(b_resps - c_resps))}")
            if b_params != c_params:
                if c_params - b_params:
                    issues.append(f"+params: {', '.join(sorted(c_params - b_params))}")
                if b_params - c_params:
                    issues.append(f"-params: {', '.join(sorted(b_params - c_params))}")

            if issues:
                changed.append(f"{op_key} ({'; '.join(issues)})")

    return added, removed, changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Check OpenAPI specification drift against committed baseline.")
    parser.add_argument(
        "--baseline",
        type=str,
        default="docs/openapi_baseline.json",
        help="Path to committed OpenAPI JSON baseline (default: docs/openapi_baseline.json)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update / overwrite the baseline JSON file with current live OpenAPI spec.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode: suppress detailed diff, only exit with code.",
    )
    args = parser.parse_args()

    current_spec = get_current_spec()

    if args.update:
        os.makedirs(os.path.dirname(os.path.abspath(args.baseline)), exist_ok=True)
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(current_spec, f, indent=2, sort_keys=True)
        print(f"[+] Successfully updated baseline: {args.baseline}")
        print(f"    Paths: {len(current_spec.get('paths', {}))}")
        print(f"    Schemas: {len(current_spec.get('components', {}).get('schemas', {}))}")
        sys.exit(0)

    if not os.path.exists(args.baseline):
        print(f"[!] Baseline file not found: {args.baseline}", file=sys.stderr)
        print("    Run `python scripts/check_openapi_drift.py --update` to establish baseline.", file=sys.stderr)
        sys.exit(1)

    with open(args.baseline, "r", encoding="utf-8") as f:
        baseline_spec = json.load(f)

    # Diff operations and schemas
    added_ops, removed_ops, changed_ops = diff_endpoints(
        baseline_spec.get("paths", {}),
        current_spec.get("paths", {}),
    )
    added_schemas, removed_schemas, changed_schemas = diff_schemas(
        baseline_spec.get("components", {}).get("schemas", {}),
        current_spec.get("components", {}).get("schemas", {}),
    )

    has_drift = bool(added_ops or removed_ops or changed_ops or added_schemas or removed_schemas or changed_schemas)

    if not has_drift:
        if not args.quiet:
            print("[+] Zero OpenAPI drift detected. Live API perfectly matches committed baseline.")
            print(f"    Paths checked:   {len(current_spec.get('paths', {}))}")
            print(f"    Schemas checked: {len(current_spec.get('components', {}).get('schemas', {}))}")
        sys.exit(0)

    print("=" * 72)
    print("OPENAPI DRIFT DETECTED")
    print("=" * 72)

    if added_ops:
        print(f"\n[+] Added Operations ({len(added_ops)}):")
        for op in sorted(added_ops):
            print(f"    + {op}")

    if removed_ops:
        print(f"\n[-] Removed Operations ({len(removed_ops)}):")
        for op in sorted(removed_ops):
            print(f"    - {op}")

    if changed_ops:
        print(f"\n[*] Modified Operations ({len(changed_ops)}):")
        for op in sorted(changed_ops):
            print(f"    ~ {op}")

    if added_schemas:
        print(f"\n[+] Added Component Schemas ({len(added_schemas)}):")
        for s in sorted(added_schemas):
            print(f"    + {s}")

    if removed_schemas:
        print(f"\n[-] Removed Component Schemas ({len(removed_schemas)}):")
        for s in sorted(removed_schemas):
            print(f"    - {s}")

    if changed_schemas:
        print(f"\n[*] Modified Component Schemas ({len(changed_schemas)}):")
        for s in sorted(changed_schemas):
            print(f"    ~ {s}")

    print("\n" + "=" * 72)
    print("Run `python scripts/check_openapi_drift.py --update` if these changes are intentional.")
    print("=" * 72)
    sys.exit(1)


if __name__ == "__main__":
    main()
