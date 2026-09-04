#!/usr/bin/env python3
"""
collapse_lib.py
---------------
Collapses PSpice-style continuation lines (lines beginning with '+') in .lib
files to produce LTSpice-compatible single-line statements.

Expected directory layout (paths are relative to this script):

    eps_spice/
    ├── models/          <- input .lib files go here; collapsed outputs written here too
    └── translator/
        └── collapse_lib.py   <- this script

Usage:
    # Process a single file from eps_spice/models/
    python collapse_lib.py TPS62133.lib

    # Process all .lib files in eps_spice/models/
    python collapse_lib.py --all

    # Specify a completely custom input path (overrides the models/ default)
    python collapse_lib.py /some/other/path/chip.lib -o /some/other/path/chip_collapsed.lib

    # Preview without writing anything
    python collapse_lib.py TPS62133.lib --dry-run
    python collapse_lib.py --all --dry-run

    # Replace an existing output file
    python collapse_lib.py TPS62133.lib --overwrite

Edge cases handled:
    - Lines starting with '+' mid-word (e.g. "+PULSE ...") vs indented "+ ..."
    - Blank lines and comment-only lines (* and **) are preserved as-is
    - Continuation lines inside VALUE { } expressions are collapsed correctly
    - Multiple consecutive continuation lines are all joined to one
    - Windows (CRLF) and Unix (LF) line endings are both accepted; output uses
      the same endings as the input file
    - Files with a BOM (UTF-8 with BOM) are read correctly
    - Leading/trailing whitespace on continuation tokens is stripped cleanly
    - The '+' in '.model dd d / + is=...' (diode model params) is collapsed
    - Original file is never modified; a new file is always written
    - --all skips files that already end in _collapsed.lib to avoid double-processing
"""

import argparse
import os
import sys


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# This script lives in eps_spice/translator/. The models folder is one level
# up, then into models/. All resolution is relative to *this file*, so the
# repo works identically on any machine regardless of where it's cloned.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "models"))


def resolve_input_path(filename: str) -> str:
    """
    If *filename* is already an absolute or relative path that exists, use it
    directly. Otherwise treat it as a bare filename and look for it in the
    models/ directory next to this script.
    """
    if os.path.isabs(filename) or os.sep in filename or "/" in filename:
        return filename
    return os.path.join(MODELS_DIR, filename)


def build_output_path(input_path: str) -> str:
    """
    Default output path: same directory as the input file, with '_collapsed'
    inserted before the extension.
    e.g.  models/TPS62133.lib -> models/TPS62133_LT.lib
    """
    base, ext = os.path.splitext(input_path)
    return f"{base}_LT{ext}"


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def detect_line_ending(raw: bytes) -> str:
    """Return '\\r\\n' if the file uses CRLF, else '\\n'."""
    return "\r\n" if b"\r\n" in raw else "\n"


def collapse_continuations(lines: list) -> list:
    """
    Join any line whose *next* line starts with '+' (after stripping leading
    whitespace) to form a single logical line.

    The '+' character and any surrounding whitespace are replaced by a single
    space so the joined token list remains valid SPICE syntax.

    Comment lines (* / **) and blank lines are never joined to anything and
    never absorb a continuation.
    """
    result = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip("\r\n")

        # Blank lines and pure comment lines pass through unchanged.
        stripped = line.lstrip()
        if stripped == "" or stripped.startswith("*"):
            result.append(line)
            i += 1
            continue

        # Accumulate any following continuation lines onto this logical line.
        while i + 1 < len(lines):
            next_raw = lines[i + 1].rstrip("\r\n")
            next_stripped = next_raw.lstrip()

            # A continuation line starts with '+' as the first non-space char.
            if not next_stripped.startswith("+"):
                break

            # Strip the leading '+' and surrounding whitespace, then join.
            continuation_body = next_stripped[1:].strip()

            if continuation_body:
                line = line.rstrip() + " " + continuation_body
            # else: bare '+' line (unusual but valid) — drop it silently.

            i += 1  # consume the continuation line

        result.append(line)
        i += 1

    return result


def process_file(input_path: str, output_path: str, dry_run: bool = False) -> dict:
    """
    Read *input_path*, collapse continuations, write to *output_path*.
    Returns a stats dict.
    """
    with open(input_path, "rb") as fh:
        raw = fh.read()

    original_ending = detect_line_ending(raw)
    # Try UTF-8 first (with BOM stripping), fall back to Windows-1252 (cp1252)
    # which is common for older TI/PSpice exports. Latin-1 is the final fallback
    # as it can decode any byte sequence without error.
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    lines = text.splitlines(keepends=True)
    original_line_count = len(lines)

    collapsed = collapse_continuations(lines)
    collapsed_line_count = len(collapsed)

    # Re-join with the original line ending style.
    output_text = original_ending.join(collapsed)
    if text.endswith(("\n", "\r\n")) and not output_text.endswith(("\n", "\r\n")):
        output_text += original_ending

    if not dry_run:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(output_text)

    return {
        "input": input_path,
        "output": output_path,
        "original_lines": original_line_count,
        "output_lines": collapsed_line_count,
        "lines_removed": original_line_count - collapsed_line_count,
        "dry_run": dry_run,
    }


def print_stats(stats: dict) -> None:
    print(f"  Input:         {stats['input']}")
    if not stats["dry_run"]:
        print(f"  Output:        {stats['output']}")
    print(f"  Lines before:  {stats['original_lines']}")
    print(f"  Lines after:   {stats['output_lines']}")
    print(f"  Collapsed:     {stats['lines_removed']} continuation lines removed")
    if stats["dry_run"]:
        print("  (dry-run: no file written)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Collapse PSpice '+' continuation lines in a .lib file so that "
            "LTSpice can parse all subcircuit pins correctly.\n\n"
            f"Default input/output directory: {MODELS_DIR}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "input",
        nargs="?",
        help=(
            "Filename or path of the .lib file to process. "
            "Bare filenames are resolved relative to eps_spice/models/."
        ),
    )
    group.add_argument(
        "--all",
        action="store_true",
        help=(
            "Process every .lib file in eps_spice/models/ that does not "
            "already end in '_collapsed.lib'."
        ),
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help=(
            "Output file path. Only valid when processing a single file. "
            "Defaults to <input_stem>_collapsed.lib in the same directory."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report statistics without writing any output files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing output files.",
    )

    args = parser.parse_args()

    if args.output and args.all:
        parser.error("--output cannot be used with --all.")

    # --- Collect files to process ---
    if args.all:
        if not os.path.isdir(MODELS_DIR):
            print(f"ERROR: models directory not found: {MODELS_DIR}", file=sys.stderr)
            sys.exit(1)
        candidates = [
            os.path.join(MODELS_DIR, f)
            for f in sorted(os.listdir(MODELS_DIR))
            if f.lower().endswith(".lib") and not f.lower().endswith("_collapsed.lib")
        ]
        if not candidates:
            print(f"No .lib files found in {MODELS_DIR}")
            sys.exit(0)
        jobs = [(f, build_output_path(f)) for f in candidates]
    else:
        input_path = resolve_input_path(args.input)
        output_path = args.output or build_output_path(input_path)
        jobs = [(input_path, output_path)]

    # --- Validate and run ---
    errors = 0
    for input_path, output_path in jobs:
        print(f"\nProcessing: {os.path.basename(input_path)}")

        if not os.path.isfile(input_path):
            print(f"  ERROR: File not found: {input_path}", file=sys.stderr)
            errors += 1
            continue

        if os.path.abspath(input_path) == os.path.abspath(output_path):
            print(
                f"  ERROR: Output path is the same as input. "
                "Use -o to specify a different destination.",
                file=sys.stderr,
            )
            errors += 1
            continue

        if not args.dry_run and os.path.exists(output_path) and not args.overwrite:
            print(
                f"  SKIP: Output already exists: {output_path}\n"
                "  Use --overwrite to replace it."
            )
            continue

        stats = process_file(input_path, output_path, dry_run=args.dry_run)
        print_stats(stats)

    if errors:
        print(f"\n{errors} error(s) encountered.", file=sys.stderr)
        sys.exit(1)

    print("\nAll done.")


if __name__ == "__main__":
    main()
