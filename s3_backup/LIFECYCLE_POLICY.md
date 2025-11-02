# S3 Lifecycle Policy for s3_backup Module

This document explains the tag-based lifecycle policy used by the s3_backup module for cost-effective long-term storage of astrophotography data.

## Overview

The lifecycle policy uses **S3 object tags** to automatically transition files through different storage classes based on their type and access requirements. This provides flexible, automated cost optimization without requiring rigid folder structures.

## How It Works

### 1. File Tagging

When the s3_backup module uploads files to S3, it applies two tags:

- **`archive_policy`**: Defines *when* to archive (fast/standard/delayed)
- **`backup_policy`**: Defines *how* to archive (deep/flexible)

### 2. Automatic Transitions

S3 lifecycle rules monitor these tags and automatically transition files to cheaper storage classes:

```
STANDARD → GLACIER → DEEP_ARCHIVE
(Active)   (Medium)  (Long-term, cheapest)
```

## Archive Policies (When to Archive)

| Policy | Days | Use Case |
|--------|------|----------|
| **fast** | 7 | Raw FITS files you won't reprocess |
| **standard** | 30 | Final processed images you might reference |
| **delayed** | 90 | Processing notes, logs, intermediate files |

## Backup Policies (How to Archive)

| Policy | Transition Path | Use Case |
|--------|----------------|----------|
| **deep** | Direct to DEEP_ARCHIVE | Maximum cost savings, infrequent access |
| **flexible** | GLACIER → DEEP_ARCHIVE (+90 days) | Easier medium-term retrieval |

## Tag Combinations & Rules

The lifecycle policy includes 6 tag-based rules covering all combinations:

### Fast/Deep (Raw Data)
- **Transition**: 7 days → DEEP_ARCHIVE
- **Example**: Raw FITS files from imaging sessions
- **Cost**: ~$0.00099/GB/month after 7 days

### Standard/Deep (Final Outputs)
- **Transition**: 30 days → DEEP_ARCHIVE
- **Example**: Final processed images, stacked files
- **Cost**: ~$0.00099/GB/month after 30 days

### Delayed/Deep (Long-term Storage)
- **Transition**: 90 days → DEEP_ARCHIVE
- **Example**: Processing logs, calibration records
- **Cost**: ~$0.00099/GB/month after 90 days

### Fast/Flexible (Quick Archive, Medium-term Access)
- **Transition**: 7 days → GLACIER, then 97 days → DEEP_ARCHIVE
- **Example**: Files you might need to restore within ~3 months
- **Cost**: ~$0.004/GB/month (GLACIER), then ~$0.00099/GB/month

### Standard/Flexible (Balanced Access)
- **Transition**: 30 days → GLACIER, then 120 days → DEEP_ARCHIVE
- **Example**: Session notes, processing configurations
- **Cost**: ~$0.004/GB/month (GLACIER), then ~$0.00099/GB/month

### Delayed/Flexible (Extended Medium-term)
- **Transition**: 90 days → GLACIER, then 180 days → DEEP_ARCHIVE
- **Example**: Documentation, analysis notes
- **Cost**: ~$0.004/GB/month (GLACIER), then ~$0.00099/GB/month

## Versioning Management

If bucket versioning is enabled, the policy manages old file versions:

| File Type | Expiration Rule | Reason |
|-----------|----------------|--------|
| **RAW files** | Delete after 1 day | Large files, unlikely to need old versions |
| **PROCESSED files** | Delete after 1 day | Large files, can be regenerated |
| **DATABASE files** | Keep 5 newest, delete rest after 90 days | Small but important, keep history |

## Cleanup Rules

### Incomplete Multipart Uploads
- **Action**: Abort after 3 days
- **Reason**: Failed uploads waste storage space and cost money

### Expired Delete Markers
- **Action**: Remove automatically
- **Reason**: Clean up artifacts from deleted versioned objects

### Minimum Object Size
- **Setting**: 128KB minimum for transitions
- **Reason**: Tiny files cost more to manage than to store in STANDARD

## Cost Comparison

| Storage Class | Cost/GB/month | Retrieval Cost | Retrieval Time |
|--------------|---------------|----------------|----------------|
| STANDARD | $0.023 | Free | Instant |
| GLACIER | $0.004 | $0.01/GB | 1-5 minutes |
| DEEP_ARCHIVE | $0.00099 | $0.02/GB | 12 hours |

**Example Savings** (1TB of data for 1 year):
- STANDARD: $276/year
- GLACIER: $48/year
- DEEP_ARCHIVE: $12/year

**Savings: ~95% with DEEP_ARCHIVE!**

## Configuration

### Default Policy

The default lifecycle policy is in `lifecycle_policy.json` and uses these timings:

```
fast:     7 days
standard: 30 days
delayed:  90 days
flexible: +90 days to DEEP_ARCHIVE
```

### Custom Policy

Generate a custom policy with different timings:

```bash
cd s3_backup/
python generate_lifecycle_policy.py \
  --fast-days 14 \
  --standard-days 60 \
  --delayed-days 120 \
  --flexible-to-deep-days 180 \
  -o my_custom_policy.json
```

View all customization options:

```bash
python generate_lifecycle_policy.py --help
python generate_lifecycle_policy.py --show-defaults
```

### Apply Custom Policy

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket YOUR_BUCKET_NAME \
  --region YOUR_REGION \
  --lifecycle-configuration file://my_custom_policy.json
```

## How s3_backup Uses Tags

The s3_backup module automatically applies tags based on your `s3_config.json` configuration:

```json
{
  "backup_rules": {
    "raw_lights": {
      "archive_policy": "fast",
      "backup_policy": "deep"
    },
    "imaging_sessions": {
      "archive_policy": "standard",
      "backup_policy": "deep"
    },
    "processing_sessions": {
      "archive_policy": "delayed",
      "backup_policy": "flexible"
    }
  }
}
```

You can customize these per content type to match your workflow.

## Monitoring

Check active lifecycle rules:

```bash
aws s3api get-bucket-lifecycle-configuration \
  --bucket YOUR_BUCKET_NAME \
  --region YOUR_REGION
```

View object tags:

```bash
aws s3api get-object-tagging \
  --bucket YOUR_BUCKET_NAME \
  --key path/to/file.tar
```

Check object storage class:

```bash
aws s3api head-object \
  --bucket YOUR_BUCKET_NAME \
  --key path/to/file.tar \
  --query StorageClass
```

## Best Practices

### When to Use Each Archive Policy

- **fast**: Use for data you'll never reprocess (raw FITS from mediocre nights)
- **standard**: Use for final products you might reference (best images, master calibrations)
- **delayed**: Use for documentation you might need (processing notes, logs)

### When to Use Each Backup Policy

- **deep**: Maximum savings, use when you're confident you won't need the data soon
- **flexible**: Balanced approach, easier to retrieve if needed within 3-6 months

### Versioning Considerations

- **Enable versioning** if you want protection against accidental deletions
- **Disable versioning** if you want to minimize costs (old versions = extra storage)
- The version expiration rules keep your costs under control if versioning is enabled

### Cost Optimization Tips

1. **Tag accurately**: Mistagged files won't follow the right lifecycle path
2. **Review periodically**: Check what's actually being archived
3. **Adjust timings**: Use `generate_lifecycle_policy.py` to match your workflow
4. **Monitor storage classes**: Use AWS Cost Explorer to track savings

## Troubleshooting

### Files Not Transitioning

1. Check object tags are set correctly:
   ```bash
   aws s3api get-object-tagging --bucket BUCKET --key FILE
   ```

2. Verify lifecycle rules are active:
   ```bash
   aws s3api get-bucket-lifecycle-configuration --bucket BUCKET
   ```

3. Remember: Transitions happen at midnight UTC and may take 24-48 hours

### Unexpected Costs

1. Check for failed multipart uploads:
   ```bash
   aws s3api list-multipart-uploads --bucket BUCKET
   ```

2. Review noncurrent versions:
   ```bash
   aws s3api list-object-versions --bucket BUCKET
   ```

3. Verify minimum object size setting (don't archive tiny files)

## Further Reading

- [AWS S3 Lifecycle Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [S3 Storage Classes](https://aws.amazon.com/s3/storage-classes/)
- [S3 Pricing](https://aws.amazon.com/s3/pricing/)
- [Object Tagging](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-tagging.html)
