#!/bin/bash
# Cleanup script to remove migration artifacts and old documentation

set -e

echo "=========================================="
echo "CLEANUP: Migration Artifacts Removal"
echo "=========================================="
echo ""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to repo root
cd "$(dirname "$0")/.."

echo "Working directory: $(pwd)"
echo ""

# Create backup list
BACKUP_FILE=".cleanup_backup_list.txt"
echo "# Files removed on $(date)" > "$BACKUP_FILE"

# Files to remove
FILES_TO_REMOVE=(
    # Documentation - Completed phases
    "FK_FIX_NEEDED.md"
    "PERFORMANCE_FIX.md"
    "PHASE2_TESTING.md"
    "PHASE3_COMPATIBILITY.md"
    "PHASE3_MIGRATION.md"
    "PHASE3_TESTING_CHECKLIST.md"
    "PHASE4_CLEANUP_PLAN.md"
    "PHASE4_STATUS.md"

    # Scripts - One-time migrations
    "scripts/fix_foreign_keys.py"
    "scripts/fix_foreign_keys_comprehensive.py"
    "scripts/fix_performance_post_migration.py"
    "scripts/migrate_schema_phase3.py"
    "scripts/phase4_auto_update.py"
    "scripts/test_phase3_migration.py"

    # Test files - Old tests
    "test_phase2_models.py"

    # Root directory - Old migrations/fixes
    "migrate_processed_catalog.py"
    "fix_s3_data.py"
)

echo "Files to be removed:"
echo "===================="
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        echo "  - $file"
    fi
done
echo ""

# Count existing files
COUNT=0
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        COUNT=$((COUNT + 1))
    fi
done

if [ $COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ No files to remove - already clean!${NC}"
    exit 0
fi

echo "Total files to remove: $COUNT"
echo ""

# Ask for confirmation
read -p "Remove these files? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Cancelled - no files removed${NC}"
    exit 0
fi

# Remove files
echo "Removing files..."
REMOVED=0
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        echo "$file" >> "$BACKUP_FILE"
        git rm "$file" 2>/dev/null || rm "$file"
        echo -e "  ${GREEN}✓${NC} Removed: $file"
        REMOVED=$((REMOVED + 1))
    fi
done

echo ""
echo "=========================================="
echo "CLEANUP COMPLETE"
echo "=========================================="
echo "Files removed: $REMOVED"
echo "Backup list: $BACKUP_FILE"
echo ""
echo "Files kept for reference:"
echo "  ✓ PHASE4_COMPLETE.md - Final migration summary"
echo "  ✓ README.md - Main documentation"
echo "  ✓ test_phase4_models.py - Current test suite"
echo "  ✓ scripts/verify_phase3.py - Verification tool"
echo "  ✓ scripts/diagnose_db_size.py - Diagnostic tool"
echo "  ✓ scripts/remove_duplicate_indexes.py - Maintenance tool"
echo ""
echo -e "${GREEN}✓ Repository cleaned up successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Commit: git commit -m 'Remove migration artifacts and old documentation'"
echo "  3. Push: git push"
