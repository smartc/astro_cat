#!/usr/bin/env python3
"""FITS Cataloger v2.0 - Refactored CLI with modular command structure.

This is the new entry point for the FITS Cataloger CLI with improved
organization and consistent verb-first command syntax.

The old main.py is preserved for backward compatibility.

Examples:
    # Get help
    python -m main --help
    python -m main scan --help

    # Basic workflow
    python -m main scan raw              # Find new FITS files
    python -m main catalog raw           # Extract metadata
    python -m main validate raw          # Score files
    python -m main migrate raw --dry-run # Preview migration
    python -m main migrate raw           # Move to library

    # Processing sessions
    python -m main processing-session create "M31 LRGB" --file-ids "1,2,3"
    python -m main list processing-sessions

    # Statistics and queries
    python -m main stats raw
    python -m main list raw --object "M31"
"""

from cli.main import cli

if __name__ == '__main__':
    cli()
