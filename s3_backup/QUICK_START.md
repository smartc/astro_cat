# Quick Start Guide - S3 Backup

Get your FITS library backed up to S3 in 5 simple steps.

## Prerequisites

- AWS account with S3 access (see main README for account setup guide)
- Your FITS Cataloger database populated

**Note:** The automated setup script can handle AWS CLI installation, credential configuration, and bucket creation for you. See Step 2 below.

## Step 1: Install Dependencies

```bash
cd ~/projects/astro_cat
source venv/bin/activate
pip install boto3
```

## Step 2: Setup AWS S3 and Bucket

### Option A: Automated Setup (Recommended)

Use the helper script to automatically configure everything:

```bash
# From the main project directory:
./s3_backup/setup_s3_bucket.sh

# Or from the s3_backup directory:
cd s3_backup/
./setup_s3_bucket.sh
```

The script will:
- ✓ Check/install AWS CLI v2 if needed
- ✓ Configure AWS credentials (if not already configured)
- ✓ Create the S3 bucket with a generated name
- ✓ Apply tag-based lifecycle rules for cost optimization
- ✓ Optionally enable bucket versioning
- ✓ Generate `s3_config.json` with your bucket details
- ✓ Validate the complete setup

**After running the script, skip to Step 3.**

### Option B: Manual Configuration

If you prefer manual setup or already have a bucket:

```bash
# Copy template
cp s3_config.json.template s3_config.json

# Edit with your settings
nano s3_config.json
```

**Minimum required settings:**
```json
{
  "enabled": true,
  "aws_region": "ca-west-1",
  "buckets": {
    "primary": "your-bucket-name"
  },
  "archive_settings": {
    "compression_level": 0
  }
}
```

**Prerequisites for manual setup:**
- AWS CLI installed and configured (`aws configure`)
- S3 bucket already created

## Step 3: Analyze Your Library

```bash
python analyze_session_sizes.py
```

This shows:
- Sessions by year
- File counts and sizes
- Upload time estimates
- Total storage needed

**Your results:**
- 248 sessions
- 827 GB total
- ~26-28 hours upload time
- ~$10/year storage cost

## Step 4: Test with Small Batch

```bash
# Upload 3 sessions from 2017
python -m s3_backup.cli upload --limit 3 --year 2017

# Verify they uploaded correctly
python -m s3_backup.cli verify --all

# Check status
python -m s3_backup.cli status
```

**What to expect:**
```
Creating archive: /tmp/astrocat_archives/20170811_4B772986.tar
  Session: 20170811_4B772986
  Files: 31
  Compression: None (uncompressed tar)
✓ Archive created: /tmp/astrocat_archives/20170811_4B772986.tar
  Files added: 31
  Original size: 969.28 MB
  Archive size: 969.28 MB
  Uncompressed archive

Uploading archive to S3...
  Source: /tmp/astrocat_archives/20170811_4B772986.tar
  Destination: s3://your-bucket-name/backups/raw/2017/20170811_4B772986.tar
✓ Upload complete
  ETag: abc123...
  Time: 45.3s
  Rate: 21.4 MB/s
```

**Verify cleanup worked:**
```bash
# Check temp directory - should not grow
du -sh /tmp/astrocat_archives/
# Should show: directory does not exist (cleaned up)
```

## Step 5: Upload Everything

### Option A: Upload by Year (Recommended)

Upload during off-hours, one year per session:

```bash
# Oldest first
python -m s3_backup.cli upload --year 2017  # ~13 min
python -m s3_backup.cli upload --year 2018  # ~4 min
python -m s3_backup.cli upload --year 2019  # ~44 min
python -m s3_backup.cli upload --year 2020  # ~1h 46m
python -m s3_backup.cli upload --year 2021  # ~5h 40m
python -m s3_backup.cli upload --year 2022  # ~7h 20m
python -m s3_backup.cli upload --year 2023  # ~3h 42m
python -m s3_backup.cli upload --year 2024  # ~3h 36m
python -m s3_backup.cli upload --year 2025  # ~3h 44m
```

**Schedule:** One large year per night during sleep/work

### Option B: Upload Everything

```bash
# Upload all sessions (runs for ~26-28 hours)
nohup python -m s3_backup.cli upload > backup.log 2>&1 &

# Monitor progress
tail -f backup.log

# Or check status
python -m s3_backup.cli status
```

## Verification

After uploads complete:

```bash
# Verify all archives
python -m s3_backup.cli verify --all

# Check final status
python -m s3_backup.cli status
```

**Expected output:**
```
================================================================================
S3 BACKUP STATUS
================================================================================

Bucket: s3://your-bucket-name
Region: ca-west-1

Sessions:
  Total in database: 248
  Backed up: 248
  Not backed up: 0
  Backup percentage: 100.0%

Archive Statistics:
  Total files backed up: 25,027
  Original size: 827.14 GB
  Archive size: 827.14 GB
  Space saved: 0 B (uncompressed)
  
Storage Classes:
  STANDARD: 248 archives

================================================================================
```

## Check S3 Console

1. Log into AWS Console
2. Navigate to S3 → Your bucket
3. Browse to `backups/raw/2024/`
4. Verify `.tar` files exist
5. Check object tags: `archive=fast`, `backup=deep-archive`

## Setup Lifecycle Rules

**If you used the automated setup script:** Lifecycle rules are already configured! Skip this section or use the commands below to verify the configuration.

**If you used manual configuration:** Apply lifecycle policy to transition to Glacier Deep Archive for maximum cost savings:

### Verify or Configure Lifecycle Rules

```bash
# View the applied configuration
python -m s3_backup.cli show-lifecycle

# Estimate your cost savings
python -m s3_backup.cli estimate-costs

# Or configure lifecycle rules manually (if not using setup script):
python -m s3_backup.cli configure-lifecycle
```

**Result:** Files automatically move to Deep Archive storage based on their tags (7-90 days), reducing cost from $19/month to <$1/month.

### Manual Method (Alternative)

If you prefer to use AWS CLI directly:

```bash
# Apply the included lifecycle policy template
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-bucket-name \
  --lifecycle-configuration file://s3_backup/lifecycle_policy.json
```

Or create a custom policy:

```bash
# Create custom policy file
cat > lifecycle_policy.json << 'EOF'
{
  "Rules": [
    {
      "Id": "TransitionToDeepArchive",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "backups/"
      },
      "Transitions": [
        {
          "Days": 1,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ]
    }
  ]
}
EOF

# Apply policy
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-bucket-name \
  --lifecycle-configuration file://lifecycle_policy.json
```

## Ongoing Maintenance

After initial backup, weekly check for new sessions:

```bash
# Upload any new sessions
python -m s3_backup.cli upload

# Or add to crontab for automatic weekly backup
0 2 * * 0 cd /path/to/astro_cat && source venv/bin/activate && python -m s3_backup.cli upload >> /var/log/astrocat_backup.log 2>&1
```

## Troubleshooting

### "Bucket not found"
```bash
# Verify bucket exists
aws s3 ls s3://your-bucket-name/

# Check region
aws s3api get-bucket-location --bucket your-bucket-name
```

### "No space left on device"
```bash
# Check temp space
df -h /tmp

# Use different temp location if needed
export TMPDIR=/path/to/larger/disk
python -m s3_backup.cli upload --year 2021
```

### Upload is slow
```bash
# Check network speed
speedtest-cli

# Monitor upload in real-time
python -m s3_backup.cli upload --year 2017 | tee upload.log
```

### Verify cleanup is working
```bash
# Before upload
du -sh /tmp/astrocat_archives/ 2>/dev/null || echo "Directory does not exist"

# During upload (in another terminal)
watch -n 5 'du -sh /tmp/astrocat_archives/ 2>/dev/null || echo "No active uploads"'

# After upload
du -sh /tmp/astrocat_archives/ 2>/dev/null || echo "Cleaned up successfully"
```

## Summary

✅ **Installed:** boto3  
✅ **Configured:** s3_config.json with your bucket  
✅ **Tested:** 3 sessions uploaded and verified  
✅ **Uploaded:** All 248 sessions to S3  
✅ **Verified:** All archives confirmed in S3  
✅ **Lifecycle:** Rules applied for cost optimization  

**Your backup is complete!**

**Annual cost:** ~$10/year  
**Peace of mind:** Priceless 🎉

## Next Steps

- Set up weekly cron job for new sessions
- Document your AWS credentials securely
- Test restore procedure (optional)
- Consider enabling S3 versioning for database backups

## Need Help?

Check the detailed documentation:
- `s3_backup/README.md` - Full documentation
- `COMPRESSION_GUIDE.md` - Archive strategy details
- `INTEGRATION_GUIDE.md` - Integration with main app