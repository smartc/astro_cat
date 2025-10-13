#!/usr/bin/env python3
import boto3
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from config import load_config
from models import DatabaseManager
from s3_backup.models import S3BackupArchive, Base
from s3_backup.manager import S3BackupConfig

# --- Configuration ---
CONFIG_PATH = "config.json"
S3_CONFIG_PATH = "s3_config.json"

# --- Initialize AWS + DB ---
config, cameras, telescopes, filter_mappings = load_config(CONFIG_PATH)
db_manager = DatabaseManager(config.database.connection_string)
Session = sessionmaker(bind=db_manager.engine)
db = Session()

s3_config = S3BackupConfig(S3_CONFIG_PATH)
s3 = boto3.client("s3", region_name=s3_config.region)
bucket = s3_config.bucket
prefix = s3_config.config["s3_paths"]["raw_archives"]

# --- List all S3 archives ---
objects = []
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        if key.endswith(".tar") or key.endswith(".tar.gz"):
            objects.append(key)

print(f"Found {len(objects)} archives in S3")

# --- Insert missing DB rows ---
added = 0
for key in objects:
    # Example key: backups/raw/2024/20240712_ABC123.tar
    try:
        parts = Path(key).parts
        year = int(parts[-2])
        session_id = Path(parts[-1]).stem.split(".")[0]

        # Skip if already exists
        if db.query(S3BackupArchive).filter_by(session_id=session_id).first():
            continue

        head = s3.head_object(Bucket=bucket, Key=key)
        size = head["ContentLength"]
        etag = head["ETag"].strip('"')
        storage_class = head.get("StorageClass", "STANDARD")

        archive = S3BackupArchive(
            session_id=session_id,
            session_year=year,
            s3_bucket=bucket,
            s3_key=key,
            s3_region=s3_config.region,
            s3_etag=etag,
            compressed_size_bytes=size,
            current_storage_class=storage_class,
            verified=True,
            verification_method="etag",
            uploaded_at=head["LastModified"],
        )
        db.add(archive)
        added += 1

    except Exception as e:
        print(f"⚠️  Failed for {key}: {e}")

db.commit()
print(f"✅ Added {added} missing records to database")

db.close()
db_manager.close()
