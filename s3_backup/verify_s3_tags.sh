#!/bin/bash
# Script to verify S3 object tags are set correctly for lifecycle rules

BUCKET="fits-cataloger-backup-cs-7a3f"
PREFIX="backups/raw/"

echo "=========================================="
echo "S3 Tag Verification Script"
echo "=========================================="
echo ""
echo "Bucket: $BUCKET"
echo "Checking files under: $PREFIX"
echo ""

# List recent objects
echo "Finding most recent uploaded files..."
OBJECTS=$(aws s3api list-objects-v2 \
  --bucket "$BUCKET" \
  --prefix "$PREFIX" \
  --query 'sort_by(Contents, &LastModified)[-5:].Key' \
  --output text)

if [ -z "$OBJECTS" ]; then
    echo "❌ No objects found in bucket under $PREFIX"
    echo ""
    echo "Have you uploaded any archives yet?"
    echo "Run: python -m s3_backup.cli upload --limit 1 --year 2017"
    exit 1
fi

echo "✓ Found objects to check"
echo ""

# Check each object's tags
for KEY in $OBJECTS; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Object: $KEY"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get tags
    TAGS=$(aws s3api get-object-tagging \
        --bucket "$BUCKET" \
        --key "$KEY" \
        2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to get tags for this object"
        continue
    fi
    
    # Parse tags
    ARCHIVE_POLICY=$(echo "$TAGS" | jq -r '.TagSet[] | select(.Key=="archive_policy") | .Value')
    BACKUP_POLICY=$(echo "$TAGS" | jq -r '.TagSet[] | select(.Key=="backup_policy") | .Value')
    
    # Check if tags exist
    if [ -z "$ARCHIVE_POLICY" ] || [ "$ARCHIVE_POLICY" == "null" ]; then
        echo "❌ MISSING: archive_policy tag"
        ARCHIVE_OK=false
    else
        echo "✓ archive_policy: $ARCHIVE_POLICY"
        ARCHIVE_OK=true
    fi
    
    if [ -z "$BACKUP_POLICY" ] || [ "$BACKUP_POLICY" == "null" ]; then
        echo "❌ MISSING: backup_policy tag"
        BACKUP_OK=false
    else
        echo "✓ backup_policy: $BACKUP_POLICY"
        BACKUP_OK=true
    fi
    
    # Check storage class
    STORAGE_CLASS=$(aws s3api head-object \
        --bucket "$BUCKET" \
        --key "$KEY" \
        --query 'StorageClass' \
        --output text 2>/dev/null)
    
    if [ -z "$STORAGE_CLASS" ] || [ "$STORAGE_CLASS" == "None" ]; then
        STORAGE_CLASS="STANDARD"
    fi
    
    echo "  Storage Class: $STORAGE_CLASS"
    
    # Get last modified date
    LAST_MODIFIED=$(aws s3api head-object \
        --bucket "$BUCKET" \
        --key "$KEY" \
        --query 'LastModified' \
        --output text 2>/dev/null)
    
    echo "  Uploaded: $LAST_MODIFIED"
    
    # Determine expected transition
    if [ "$ARCHIVE_OK" == "true" ] && [ "$BACKUP_OK" == "true" ]; then
        case "${ARCHIVE_POLICY}_${BACKUP_POLICY}" in
            "fast_deep")
                echo "  → Will transition to DEEP_ARCHIVE after 7 days"
                ;;
            "standard_deep")
                echo "  → Will transition to DEEP_ARCHIVE after 30 days"
                ;;
            "delayed_deep")
                echo "  → Will transition to DEEP_ARCHIVE after 90 days"
                ;;
            "fast_flexible")
                echo "  → Will transition to GLACIER_FLEXIBLE_RETRIEVAL after 7 days"
                echo "  → Then to DEEP_ARCHIVE after 97 days total"
                ;;
            "standard_flexible")
                echo "  → Will transition to GLACIER_FLEXIBLE_RETRIEVAL after 30 days"
                echo "  → Then to DEEP_ARCHIVE after 120 days total"
                ;;
            "delayed_flexible")
                echo "  → Will transition to GLACIER_FLEXIBLE_RETRIEVAL after 90 days"
                echo "  → Then to DEEP_ARCHIVE after 180 days total"
                ;;
            *)
                echo "  ⚠️  Unknown policy combination: ${ARCHIVE_POLICY}_${BACKUP_POLICY}"
                ;;
        esac
    else
        echo "  ❌ Lifecycle rules will NOT apply - tags missing!"
    fi
    
    echo ""
done

echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "If all tags show ✓, your lifecycle rules will work correctly."
echo "If any tags show ❌, re-upload those files with updated code."
echo ""
echo "To check lifecycle rule configuration:"
echo "  aws s3api get-bucket-lifecycle-configuration --bucket $BUCKET"
echo ""
