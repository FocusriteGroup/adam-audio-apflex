#!/usr/bin/env python3
"""
Master Documentation Generator for DataTools
=============================================

This script automatically runs all documentation generator scripts in the docs/scripts directory.
It provides a single entry point to regenerate all DataTools documentation at once.

Usage:
    python DataTools/docs/scripts/generate_all_docs.py
    python DataTools/docs/scripts/generate_all_docs.py --skip-screenshots
    python DataTools/docs/scripts/generate_all_docs.py --keep-existing

Options:
    --skip-screenshots    Skip screenshot capture (use existing files)
    --keep-existing       Keep existing screenshots when capturing new ones
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 output for Unicode support across platforms
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


SCRIPT_DIR = Path(__file__).resolve().parent
EXCLUDED_SCRIPTS = {"generate_all_docs.py", "__pycache__"}


def _find_generator_scripts() -> list[Path]:
    """
    Find all generator scripts in the docs/scripts directory.
    
    Returns:
        Sorted list of generator script paths (excluding this script and __pycache__).
    """
    scripts = []
    for script_path in SCRIPT_DIR.glob("generate_*.py"):
        if script_path.name not in EXCLUDED_SCRIPTS:
            scripts.append(script_path)
    return sorted(scripts)


def _build_command(script_path: Path, args: argparse.Namespace) -> list[str]:
    """
    Build the command to execute a generator script with appropriate arguments.
    
    Args:
        script_path: Path to the generator script.
        args: Parsed command-line arguments.
    
    Returns:
        Command list ready for subprocess.
    """
    cmd = [sys.executable, str(script_path)]
    
    if args.skip_screenshots:
        cmd.append("--skip-screenshots")
    if args.keep_existing:
        cmd.append("--keep-existing")
    
    return cmd


def run_all_generators(skip_screenshots: bool = False, keep_existing: bool = False) -> int:
    """
    Run all generator scripts and report results.
    
    Args:
        skip_screenshots: If True, skip screenshot capture for all scripts.
        keep_existing: If True, keep existing screenshots when capturing.
    
    Returns:
        Exit code (0 for success, 1+ for failures).
    """
    scripts = _find_generator_scripts()
    
    if not scripts:
        print("❌ No generator scripts found in docs/scripts/")
        return 1
    
    print(f"📚 Found {len(scripts)} documentation generator script(s):")
    for script in scripts:
        print(f"   • {script.name}")
    print()
    
    successful = []
    failed = []
    
    for script_path in scripts:
        script_name = script_path.stem.replace("generate_", "").replace("_", " ").title()
        print(f"🔄 Running: {script_path.name}")
        print("-" * 60)
        
        # Build command with flags
        cmd = [sys.executable, str(script_path)]
        if skip_screenshots:
            cmd.append("--skip-screenshots")
        if keep_existing:
            cmd.append("--keep-existing")
        
        try:
            result = subprocess.run(cmd, capture_output=False, text=True, timeout=300)
            if result.returncode == 0:
                successful.append(script_path.name)
                print(f"✅ {script_path.name} completed successfully")
            else:
                failed.append((script_path.name, result.returncode))
                print(f"❌ {script_path.name} failed with exit code {result.returncode}")
        except subprocess.TimeoutExpired:
            failed.append((script_path.name, "timeout"))
            print(f"⏱️  {script_path.name} timed out (exceeded 5 minutes)")
        except Exception as e:
            failed.append((script_path.name, str(e)))
            print(f"❌ {script_path.name} error: {e}")
        
        print()
    
    # Print summary
    print("=" * 60)
    print("📊 Documentation Generation Summary")
    print("=" * 60)
    print(f"✅ Successful: {len(successful)}")
    for name in successful:
        print(f"   • {name}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for name, error in failed:
            print(f"   • {name} ({error})")
        return 1
    else:
        print(f"\n🎉 All {len(successful)} documentation generators ran successfully!")
        return 0


def main() -> None:
    """Parse arguments and run all documentation generators."""
    parser = argparse.ArgumentParser(
        description="Run all DataTools documentation generators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skip-screenshots",
        action="store_true",
        help="Skip screenshot capture for all generators (use existing files)",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing screenshots when capturing new ones",
    )
    
    args = parser.parse_args()
    
    exit_code = run_all_generators(
        skip_screenshots=args.skip_screenshots,
        keep_existing=args.keep_existing,
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
