import subprocess
import logging

logger = logging.getLogger(__name__)

def get_version():
    """Get version from git tags and commit status."""
    try:
        # Get latest tag
        tag = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0'],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        
        # Get current commit short hash
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        
        # Check if we're at the tag
        tag_commit = subprocess.check_output(
            ['git', 'rev-list', '-n', '1', tag],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()[:7]
        
        # Check for uncommitted changes
        has_changes = subprocess.call(
            ['git', 'diff-index', '--quiet', 'HEAD', '--'],
            stderr=subprocess.DEVNULL
        ) != 0
        
        # Build version string
        if commit == tag_commit:
            if has_changes:
                return f"{tag}-dev"
            return tag
        else:
            if has_changes:
                return f"{tag}-{commit}-dev"
            return f"{tag}-{commit}"
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("Could not determine version from git, using fallback")
        return "v0.0.0"  # Fallback version

__version__ = get_version()