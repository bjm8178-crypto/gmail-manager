"""Encrypt legacy OAuth tokens already stored in the database."""

import argparse

from database import rotate_encryption_keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--migrate-plaintext",
        action="store_true",
        help="Also encrypt legacy JSON tokens that were stored without encryption.",
    )
    args = parser.parse_args()
    changed = rotate_encryption_keys(migrate_plaintext=args.migrate_plaintext)
    print(f"Encrypted {changed} OAuth token(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
