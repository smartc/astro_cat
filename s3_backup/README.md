# S3 Backup System for FITS Cataloger

Automated backup of FITS imaging sessions to AWS S3 with Glacier lifecycle management.

## Overview

The S3 backup system creates uncompressed tar archives of entire imaging sessions and uploads them to AWS S3. Archives are organized by year and automatically transitioned to Glacier storage for cost-effective long-term retention.

### Key Features

- **Session-based archives**: All FITS files from one imaging session in a single tar file
- **Uncompressed archives**: Faster archiving with negligible cost increase (~$1.50/year)
- **Year-based organization**: Archives organized by year for easy management
- **Lifecycle management**: Automatic transition to Glacier Deep Archive
- **Database tracking**: Full backup status and history in SQLite
- **Verification**: Automated verification of uploaded archives
- **Progress tracking**: Visual progress bars for long operations
- **Resume capability**: Skip already-backed-up sessions

## Architecture

### Storage Structure

```
s3://bucket/
├── backups/
│   └── raw/
│       ├── 2020/
│       │   ├── SESSION_ID_1.tar
│       │   └── SESSION_ID_2.tar
│       ├── 2021/
│       ├── 2022/
│       └── ...
│   └── sessions/
│       └── 2020/
│           ├── SESSION_ID_1_notes.md
│           └── SESSION_ID_2_notes.md
```

### Archive Contents

Each session archive contains:
```
SESSION_ID.tar
└── SESSION_ID/
    ├── file1.fits
    ├── file2.fits
    └── ...
```

### Database Tables

- **s3_backup_archives**: Archive metadata and tracking
- **s3_backup_session_notes**: Session markdown file backups
- **s3_backup_log**: Operation audit log
- **s3_backup_stats**: Historical statistics

## Setup

### 1. AWS Prerequisites

1. **AWS CLI configured** with credentials:
   ```bash
   aws configure
   ```

2. **Create S3 bucket**:
   ```bash
   aws s3 mb s3://your-bucket-name --region ca-west-1
   ```

3. **Enable versioning** (optional but recommended):
   ```bash
   aws s3api put-bucket-versioning \
     --bucket your-bucket-name \
     --versioning-configuration Status=Enabled
   ```

4. **Create lifecycle rules**:
   ```bash
   # See lifecycle_policy.json example below
   aws s3api put-bucket-lifecycle-configuration \
     --bucket your-bucket-name \
     --lifecycle-configuration file://lifecycle_policy.json
   ```

### 2. Python Dependencies

Add to `requirements.txt`:
```
boto3>=1.34.0
```

Install:
```bash
pip install boto3
```

### 3. Configuration

1. **Initialize config**:
   ```bash
   python -m s3_backup.cli init-config
   ```

2. **Edit s3_config.json**:
   ```json
   {
     "enabled": true,
     "aws_region": "ca-west-1",
     "buckets": {
       "primary": "your-bucket-name"
     }
   }
   ```

3. **Create database tables**:
   ```bash
   # Tables are created automatically on first run
   python -m s3_backup.cli status
   ```

## Usage

### Analyze Sessions

Before starting, analyze your sessions to understand sizes:

```bash
# Run the analysis script
python analyze_session_sizes.py

# Example output:
#   YEAR: 2024
#   Sessions: 45 | Files: 12,543 | Total Size: 234.56 GB
#   Average session size: 5.21 GB
#   Upload time estimate: 12h 34m
```

### Upload Sessions

**Upload a single session**:
```bash
python -m s3_backup.cli upload --session-id SESSION_ID
```

**Upload all sessions from a year**:
```bash
python -m s3_backup.cli upload --year 2024
```

**Upload limited number** (test with small batch first):
```bash
python -m s3_backup.cli upload --limit 5
```

**Upload with options**:
```bash
# Keep local archives (don't delete after upload)
python -m s3_backup.cli upload --no-cleanup

# Force re-upload existing archives
python -m s3_backup.cli upload --no-skip-existing
```

### Verify Backups

**Verify all archives**:
```bash
python -m s3_backup.cli verify --all
```

**Verify specific session**:
```bash
python -m s3_backup.cli verify --session-id SESSION_ID
```

### Check Status

**Overall backup status**:
```bash
python -m s3_backup.cli status
```

**List sessions**:
```bash
# All sessions
python -m s3_backup.cli list-sessions

# Specific year
python -m s3_backup.cli list-sessions --year 2024

# Only non-backed-up sessions
python -m s3_backup.cli list-sessions --not-backed-up
```

## Lifecycle Management

### S3 Lifecycle Policy Example

Save as `lifecycle_policy.json`:

```json
{
  "Rules": [
    {
      "Id": "ArchiveFastToDeepArchive",
      "Status": "Enabled",
      "Filter": {
        "Tag": {
          "Key": "archive",
          "Value": "fast"
        }
      },
      "Transitions": [
        {
          "Days": 7,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ]
    },
    {
      "Id": "ArchiveNormalToDeepArchive",
      "Status": "Enabled",
      "Filter": {
        "Tag": {
          "Key": "archive",
          "Value": "normal"
        }
      },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ]
    },
    {
      "Id": "ArchiveDelayedToGlacier",
      "Status": "Enabled",
      "Filter": {
        "Tag": {
          "Key": "archive",
          "Value": "delayed"
        }
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER_FLEXIBLE_RETRIEVAL"
        }
      ]
    },
    {
      "Id": "BackupToDeepArchiveImmediate",
      "Status": "Enabled",
      "Filter": {
        "Tag": {
          "Key": "backup",
          "Value": "deep-archive"
        }
      },
      "Transitions": [
        {
          "Days": 0,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ]
    }
  ]
}
```

Apply:
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-bucket-name \
  --lifecycle-configuration file://lifecycle_policy.json
```

### Storage Classes & Costs (ca-west-1)

| Storage Class | Cost/GB/Month | Retrieval Time | Use Case |
|--------------|---------------|----------------|----------|
| STANDARD | $0.023 | Instant | Initial upload |
| GLACIER_FLEXIBLE | $0.0036 | 3-5 hours | Processing sessions |
| DEEP_ARCHIVE | $0.00099 | 12 hours | Raw data long-term |

## Recommended Workflow

### Initial Backup

1. **Analyze first**:
   ```bash
   python analyze_session_sizes.py
   ```

2. **Test with small batch**:
   ```bash
   python -m s3_backup.cli upload --limit 5 --year 2024
   ```

3. **Verify test uploads**:
   ```bash
   python -m s3_backup.cli verify --all
   python -m s3_backup.cli status
   ```

4. **Upload by year** (oldest first):
   ```bash
   # Upload year by year during off-hours
   python -m s3_backup.cli upload --year 2020  # overnight
   python -m s3_backup.cli upload --year 2021  # next night
   # etc.
   ```

5. **Verify everything**:
   ```bash
   python -m s3_backup.cli verify --all
   ```

### Ongoing Maintenance

After migration of new sessions:
```bash
# Upload new sessions
python -m s3_backup.cli upload --not-backed-up

# Or set up cron job (weekly):
0 2 * * 0 cd /path/to/fits_cataloger && python -m s3_backup.cli upload --not-backed-up
```

## Integration with Main CLI

To integrate with `main.py`, add this to your CLI:

```python
# In main.py

@cli.group()
@click.pass_context
def s3(ctx):
    """S3 backup operations."""
    pass

# Import and register s3 commands
from s3_backup.cli import cli as s3_cli
for command in s3_cli.commands.values():
    s3.add_command(command)
```

Then use:
```bash
python main.py s3 status
python main.py s3 upload --year 2024
```

## Troubleshooting

### Error: "Bucket not found"

- Verify bucket name in `s3_config.json`
- Check AWS region matches
- Verify AWS CLI credentials: `aws s3 ls`

### Error: "Access denied"

Check IAM permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:HeadObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

### Slow uploads

- Check bandwidth limit in `s3_config.json`
- Adjust `max_concurrency` for multipart uploads
- Consider uploading during off-peak hours
- Use `--limit` to upload in batches

### Archive verification failed

- Re-run verification: `python -m s3_backup.cli verify --session-id SESSION_ID`
- Check S3 console to verify object exists
- Verify ETag in database matches S3

## Cost Estimation

### Storage Costs (Example: 827 GB library - uncompressed)

**Initial (STANDARD storage)**:
- 827 GB @ $0.023/GB/month = ~$19/month

**After lifecycle transitions (Deep Archive)**:
- 827 GB @ $0.00099/GB/month = ~$0.82/month (~$9.75/year)

**Data transfer**:
- Upload: FREE
- Download: $0.09/GB after first 100GB/month

### Total First Year Cost Estimate

- Month 1: $19 (STANDARD)
- Transition to Deep Archive: immediate (with lifecycle rule)
- Months 2-12: ~$0.82/month = ~$9
- **Total: ~$28 for first year**
- **Years 2+: ~$10/year**

*Note: Uncompressed archives are ~$1.50/year more than compressed, but save significant time during archiving.*

## Restoring from Backup

**Note**: Restore functionality is planned for future release.

Manual restore process:
```bash
# 1. Request restore from Glacier (via AWS Console or CLI)
aws s3api restore-object \
  --bucket your-bucket-name \
  --key backups/raw/2024/SESSION_ID.tar \
  --restore-request Days=7,GlacierJobParameters={Tier=Standard}

# 2. Wait 3-5 hours for Standard tier

# 3. Download
aws s3 cp s3://your-bucket-name/backups/raw/2024/SESSION_ID.tar ./

# 4. Extract
tar -xf SESSION_ID.tar
```

## Future Enhancements

- [ ] Web interface for backup management
- [ ] Automated restore functionality
- [ ] Processing session backups
- [ ] Final output selective backups
- [ ] Backup verification scheduling
- [ ] Email notifications
- [ ] Cost tracking dashboard
- [ ] Automated backup after migration
- [ ] Multi-region replication

## Support

For issues or questions:
1. Check logs: `fits_cataloger.log`
2. Verify configuration: `s3_config.json`
3. Test AWS access: `aws s3 ls s3://your-bucket-name/`
4. Review S3 backup logs in database: `s3_backup_log` table