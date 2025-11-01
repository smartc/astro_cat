#!/usr/bin/env python3
"""FITS Cataloger v2.0 - Refactored CLI with modular command structure.

This is the new entry point for the FITS Cataloger CLI with improved
organization and consistent verb-first command syntax.

The old main.py is preserved for backward compatibility.

Examples:
    # Get help
    python main_v2.py --help
    python main_v2.py scan --help

    # Basic workflow
    python main_v2.py scan raw              # Find new FITS files
    python main_v2.py catalog raw           # Extract metadata
    python main_v2.py validate raw          # Score files
    python main_v2.py migrate raw --dry-run # Preview migration
    python main_v2.py migrate raw           # Move to library

    # Processing sessions
    python main_v2.py processing-session create "M31 LRGB" --file-ids "1,2,3"
    python main_v2.py list processing-sessions

    # Statistics and queries
    python main_v2.py stats raw
    python main_v2.py list raw --object "M31"
"""

from cli.main import cli

if __name__ == '__main__':
    cli()
