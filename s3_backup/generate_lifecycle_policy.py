#!/usr/bin/env python3
"""
Generate custom S3 lifecycle policy for the s3_backup module.

This script creates a lifecycle policy JSON file with configurable timing
for archive transitions. The policy uses tag-based rules that work with
the s3_backup module's archive_policy and backup_policy tags.
"""

import json
import argparse
from pathlib import Path


def generate_lifecycle_policy(
    fast_days: int = 7,
    standard_days: int = 30,
    delayed_days: int = 90,
    flexible_to_deep_days: int = 90,
    raw_version_expire_days: int = 1,
    processed_version_expire_days: int = 1,
    database_version_expire_days: int = 90,
    database_keep_versions: int = 5,
    multipart_abort_days: int = 3,
    min_object_size: str = "all_storage_classes_128K"
) -> dict:
    """
    Generate a lifecycle policy configuration.

    Args:
        fast_days: Days before transitioning 'fast' archive policy files
        standard_days: Days before transitioning 'standard' archive policy files
        delayed_days: Days before transitioning 'delayed' archive policy files
        flexible_to_deep_days: Days after GLACIER before moving to DEEP_ARCHIVE for 'flexible' policy
        raw_version_expire_days: Days to keep old versions of RAW files
        processed_version_expire_days: Days to keep old versions of PROCESSED files
        database_version_expire_days: Days to keep old versions of DATABASE files
        database_keep_versions: Number of newest DATABASE versions to always keep
        multipart_abort_days: Days before aborting incomplete multipart uploads
        min_object_size: Minimum object size for transitions (e.g., "all_storage_classes_128K")

    Returns:
        Dictionary representing the lifecycle policy
    """

    policy = {
        "TransitionDefaultMinimumObjectSize": min_object_size,
        "Rules": []
    }

    # Tag-based archival rules for each combination of archive_policy and backup_policy

    # Fast/Deep: Quick transition to DEEP_ARCHIVE
    policy["Rules"].append({
        "ID": "Archive - Fast/Deep",
        "Filter": {
            "And": {
                "Tags": [
                    {"Key": "archive_policy", "Value": "fast"},
                    {"Key": "backup_policy", "Value": "deep"}
                ]
            }
        },
        "Status": "Enabled",
        "Transitions": [
            {"Days": fast_days, "StorageClass": "DEEP_ARCHIVE"}
        ],
        "NoncurrentVersionTransitions": [
            {"NoncurrentDays": fast_days, "StorageClass": "DEEP_ARCHIVE"}
        ]
    })

    # Standard/Deep: Medium-term transition to DEEP_ARCHIVE
    policy["Rules"].append({
        "ID": "Archive - Standard/Deep",
        "Filter": {
            "And": {
                "Tags": [
                    {"Key": "archive_policy", "Value": "standard"},
                    {"Key": "backup_policy", "Value": "deep"}
                ]
            }
        },
        "Status": "Enabled",
        "Transitions": [
            {"Days": standard_days, "StorageClass": "DEEP_ARCHIVE"}
        ],
        "NoncurrentVersionTransitions": [
            {"NoncurrentDays": standard_days, "StorageClass": "DEEP_ARCHIVE"}
        ]
    })

    # Delayed/Deep: Long-term transition to DEEP_ARCHIVE
    policy["Rules"].append({
        "ID": "Archive - Delayed/Deep",
        "Filter": {
            "And": {
                "Tags": [
                    {"Key": "archive_policy", "Value": "delayed"},
                    {"Key": "backup_policy", "Value": "deep"}
                ]
            }
        },
        "Status": "Enabled",
        "Transitions": [
            {"Days": delayed_days, "StorageClass": "DEEP_ARCHIVE"}
        ],
        "NoncurrentVersionTransitions": [
            {"NoncurrentDays": delayed_days, "StorageClass": "DEEP_ARCHIVE"}
        ]
    })

    # Fast/Flexible: GLACIER first, then DEEP_ARCHIVE
    policy["Rules"].append({
        "ID": "Archive - Fast/Flexible",
        "Filter": {
            "And": {
                "Tags": [
                    {"Key": "archive_policy", "Value": "fast"},
                    {"Key": "backup_policy", "Value": "flexible"}
                ]
            }
        },
        "Status": "Enabled",
        "Transitions": [
            {"Days": fast_days, "StorageClass": "GLACIER"},
            {"Days": fast_days + flexible_to_deep_days, "StorageClass": "DEEP_ARCHIVE"}
        ],
        "NoncurrentVersionTransitions": [
            {"NoncurrentDays": fast_days, "StorageClass": "GLACIER"},
            {"NoncurrentDays": fast_days + flexible_to_deep_days, "StorageClass": "DEEP_ARCHIVE"}
        ]
    })

    # Standard/Flexible: GLACIER first, then DEEP_ARCHIVE
    policy["Rules"].append({
        "ID": "Archive - Standard/Flexible",
        "Filter": {
            "And": {
                "Tags": [
                    {"Key": "archive_policy", "Value": "standard"},
                    {"Key": "backup_policy", "Value": "flexible"}
                ]
            }
        },
        "Status": "Enabled",
        "Transitions": [
            {"Days": standard_days, "StorageClass": "GLACIER"},
            {"Days": standard_days + flexible_to_deep_days, "StorageClass": "DEEP_ARCHIVE"}
        ],
        "NoncurrentVersionTransitions": [
            {"NoncurrentDays": standard_days, "StorageClass": "GLACIER"},
            {"NoncurrentDays": standard_days + flexible_to_deep_days, "StorageClass": "DEEP_ARCHIVE"}
        ]
    })

    # Delayed/Flexible: GLACIER first, then DEEP_ARCHIVE
    policy["Rules"].append({
        "ID": "Archive - Delayed/Flexible",
        "Filter": {
            "And": {
                "Tags": [
                    {"Key": "archive_policy", "Value": "delayed"},
                    {"Key": "backup_policy", "Value": "flexible"}
                ]
            }
        },
        "Status": "Enabled",
        "Transitions": [
            {"Days": delayed_days, "StorageClass": "GLACIER"},
            {"Days": delayed_days + flexible_to_deep_days, "StorageClass": "DEEP_ARCHIVE"}
        ],
        "NoncurrentVersionTransitions": [
            {"NoncurrentDays": delayed_days, "StorageClass": "GLACIER"},
            {"NoncurrentDays": delayed_days + flexible_to_deep_days, "StorageClass": "DEEP_ARCHIVE"}
        ]
    })

    # Version expiration rules (prefix-based)

    # Expire old RAW file versions quickly (they're large and unlikely to need recovery)
    policy["Rules"].append({
        "ID": "Expire non-current versions for RAW",
        "Filter": {
            "Prefix": "backups/raw/"
        },
        "Status": "Enabled",
        "NoncurrentVersionExpiration": {
            "NoncurrentDays": raw_version_expire_days
        }
    })

    # Expire old PROCESSED file versions quickly (they're large and can be regenerated)
    policy["Rules"].append({
        "ID": "Expire noncurrent versions for PROCESSED",
        "Filter": {
            "Prefix": "backups/processed/"
        },
        "Status": "Enabled",
        "NoncurrentVersionExpiration": {
            "NoncurrentDays": processed_version_expire_days
        }
    })

    # Keep a few DATABASE versions longer (they're small but important)
    policy["Rules"].append({
        "ID": "Expire noncurrent DATABASE files",
        "Filter": {
            "Prefix": "backups/database/"
        },
        "Status": "Enabled",
        "NoncurrentVersionExpiration": {
            "NoncurrentDays": database_version_expire_days,
            "NewerNoncurrentVersions": database_keep_versions
        }
    })

    # Cleanup rules

    # Clean up incomplete multipart uploads and expired delete markers
    policy["Rules"].append({
        "ID": "Cleanup deleted files and incomplete uploads",
        "Filter": {},
        "Status": "Enabled",
        "Expiration": {
            "ExpiredObjectDeleteMarker": True
        },
        "AbortIncompleteMultipartUpload": {
            "DaysAfterInitiation": multipart_abort_days
        }
    })

    return policy


def main():
    parser = argparse.ArgumentParser(
        description="Generate custom S3 lifecycle policy for s3_backup module",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--fast-days",
        type=int,
        default=7,
        help="Days before transitioning 'fast' archive policy files"
    )
    parser.add_argument(
        "--standard-days",
        type=int,
        default=30,
        help="Days before transitioning 'standard' archive policy files"
    )
    parser.add_argument(
        "--delayed-days",
        type=int,
        default=90,
        help="Days before transitioning 'delayed' archive policy files"
    )
    parser.add_argument(
        "--flexible-to-deep-days",
        type=int,
        default=90,
        help="Days after GLACIER before moving to DEEP_ARCHIVE for 'flexible' policy"
    )
    parser.add_argument(
        "--raw-version-expire-days",
        type=int,
        default=1,
        help="Days to keep old versions of RAW files"
    )
    parser.add_argument(
        "--processed-version-expire-days",
        type=int,
        default=1,
        help="Days to keep old versions of PROCESSED files"
    )
    parser.add_argument(
        "--database-version-expire-days",
        type=int,
        default=90,
        help="Days to keep old versions of DATABASE files"
    )
    parser.add_argument(
        "--database-keep-versions",
        type=int,
        default=5,
        help="Number of newest DATABASE versions to always keep"
    )
    parser.add_argument(
        "--multipart-abort-days",
        type=int,
        default=3,
        help="Days before aborting incomplete multipart uploads"
    )
    parser.add_argument(
        "--min-object-size",
        type=str,
        default="all_storage_classes_128K",
        help="Minimum object size for transitions"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path(__file__).parent / "lifecycle_policy.json",
        help="Output file path"
    )
    parser.add_argument(
        "--show-defaults",
        action="store_true",
        help="Show default values and exit"
    )

    args = parser.parse_args()

    if args.show_defaults:
        print("\nDefault Lifecycle Policy Configuration:")
        print("=" * 60)
        print(f"Fast archive:              {args.fast_days} days → DEEP_ARCHIVE")
        print(f"Standard archive:          {args.standard_days} days → DEEP_ARCHIVE")
        print(f"Delayed archive:           {args.delayed_days} days → DEEP_ARCHIVE")
        print(f"Flexible GLACIER→DEEP:     +{args.flexible_to_deep_days} days")
        print()
        print("Version Expiration:")
        print(f"  RAW files:               {args.raw_version_expire_days} day(s)")
        print(f"  PROCESSED files:         {args.processed_version_expire_days} day(s)")
        print(f"  DATABASE files:          {args.database_version_expire_days} days (keep {args.database_keep_versions} newest)")
        print()
        print(f"Multipart upload cleanup:  {args.multipart_abort_days} days")
        print(f"Minimum object size:       {args.min_object_size}")
        print("=" * 60)
        return

    # Generate the policy
    policy = generate_lifecycle_policy(
        fast_days=args.fast_days,
        standard_days=args.standard_days,
        delayed_days=args.delayed_days,
        flexible_to_deep_days=args.flexible_to_deep_days,
        raw_version_expire_days=args.raw_version_expire_days,
        processed_version_expire_days=args.processed_version_expire_days,
        database_version_expire_days=args.database_version_expire_days,
        database_keep_versions=args.database_keep_versions,
        multipart_abort_days=args.multipart_abort_days,
        min_object_size=args.min_object_size
    )

    # Write to file
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(policy, f, indent=2)

    print(f"✓ Lifecycle policy written to: {args.output}")
    print(f"  - 6 tag-based archival rules")
    print(f"  - 3 version expiration rules")
    print(f"  - 1 cleanup rule")
    print()
    print("To apply this policy to your bucket:")
    print(f"  aws s3api put-bucket-lifecycle-configuration \\")
    print(f"    --bucket YOUR_BUCKET_NAME \\")
    print(f"    --region YOUR_REGION \\")
    print(f"    --lifecycle-configuration file://{args.output}")


if __name__ == "__main__":
    main()
