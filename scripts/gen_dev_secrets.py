#!/usr/bin/env python3
"""Generate development secrets for the Agri-Market Intelligence Platform.

Usage:
    python scripts/gen_dev_secrets.py [--write]

Without --write, prints the secrets to stdout only.
With --write, appends/overwrites the corresponding keys in .env (never .env.example).

Generated secrets:
  - APP_JWT_SECRET_KEY          : 64-char hex string (HMAC-SHA256 for JWT)
  - APP_CONSENT_SIGNING_SECRET  : 64-char hex string (HMAC for consent artifacts)
  - APP_ASSAY_HMAC_SECRET       : 64-char hex string (HMAC for assay tamper-evidence)
  - APP_ONDC_SIGNING_PRIVATE_KEY_HEX : 64-char hex (32-byte Ed25519 seed)
  - METRICS_BEARER_TOKEN        : 48-char hex string (Prometheus /metrics auth)
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

# ── Key generation ────────────────────────────────────────────────────────────

def gen_hex(nbytes: int) -> str:
    return secrets.token_hex(nbytes)


def gen_ed25519_seed_hex() -> str:
    """Generate a random 32-byte Ed25519 private key seed as hex."""
    return secrets.token_hex(32)


def generate_all() -> dict[str, str]:
    return {
        "APP_JWT_SECRET_KEY": gen_hex(32),
        "APP_CONSENT_SIGNING_SECRET": gen_hex(32),
        "APP_ASSAY_HMAC_SECRET": gen_hex(32),
        "APP_ONDC_SIGNING_PRIVATE_KEY_HEX": gen_ed25519_seed_hex(),
        "METRICS_BEARER_TOKEN": gen_hex(24),
    }


# ── .env manipulation ─────────────────────────────────────────────────────────

def write_to_dotenv(secrets_map: dict[str, str], env_path: Path) -> None:
    """Upsert keys in .env without touching any other lines.

    Lines matching `^KEY=` are replaced; missing keys are appended.
    """
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        matched = False
        for key in secrets_map:
            if re.match(rf"^{re.escape(key)}\s*=", line):
                new_lines.append(f"{key}={secrets_map[key]}\n")
                updated_keys.add(key)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    # Append any keys that weren't already present
    appended: list[str] = []
    for key, val in secrets_map.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")
            appended.append(key)

    env_path.write_text("".join(new_lines), encoding="utf-8")
    print(f"\nWritten to {env_path}:")
    for key in updated_keys:
        print(f"  [updated] {key}")
    for key in appended:
        print(f"  [added]   {key}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dev secrets.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write generated secrets into .env (never .env.example).",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the .env file to write (default: .env).",
    )
    args = parser.parse_args()

    generated = generate_all()

    print("# --- Generated dev secrets -------------------------------------")
    print("# DO NOT commit these values. Add them to .env (never .env.example).")
    print()
    for key, val in generated.items():
        print(f"{key}={val}")

    if args.write:
        env_path = Path(args.env_file)
        if str(env_path.resolve()) == str(Path(".env.example").resolve()):
            print("\nERROR: Refusing to write secrets to .env.example.", file=sys.stderr)
            sys.exit(1)
        write_to_dotenv(generated, env_path)
    else:
        print("\n# To write these directly into .env, run:")
        print("# python scripts/gen_dev_secrets.py --write")


if __name__ == "__main__":
    main()
