"""Manage S3 bucket lifecycle rules for astro_cat backups."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manage S3 bucket lifecycle policies."""

    def __init__(self, bucket_name: str, region: str = 'us-east-1'):
        """Initialize lifecycle manager.

        Args:
            bucket_name: S3 bucket name
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)

    def apply_lifecycle_policy(self, policy_file: Optional[Path] = None) -> bool:
        """Apply lifecycle policy to S3 bucket.

        Args:
            policy_file: Path to lifecycle policy JSON file.
                        If None, uses default lifecycle_policy.json

        Returns:
            True if successful, False otherwise
        """
        if policy_file is None:
            # Use default policy file in same directory
            policy_file = Path(__file__).parent / 'lifecycle_policy.json'

        try:
            # Load policy from file
            with open(policy_file, 'r') as f:
                policy = json.load(f)

            logger.info(f"Applying lifecycle policy from {policy_file}")
            logger.info(f"Bucket: {self.bucket_name}")
            logger.info(f"Rules: {len(policy.get('Rules', []))}")

            # Apply policy to bucket
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration=policy
            )

            logger.info("✓ Lifecycle policy applied successfully")
            return True

        except FileNotFoundError:
            logger.error(f"Policy file not found: {policy_file}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in policy file: {e}")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"Failed to apply lifecycle policy: {error_code} - {error_msg}")
            return False

    def get_current_policy(self) -> Optional[Dict]:
        """Get current lifecycle policy from bucket.

        Returns:
            Dictionary with lifecycle policy, or None if no policy exists
        """
        try:
            response = self.s3_client.get_bucket_lifecycle_configuration(
                Bucket=self.bucket_name
            )
            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchLifecycleConfiguration':
                logger.info("No lifecycle policy currently configured")
                return None
            else:
                logger.error(f"Failed to get lifecycle policy: {error_code}")
                return None

    def delete_lifecycle_policy(self) -> bool:
        """Delete lifecycle policy from bucket.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_bucket_lifecycle(Bucket=self.bucket_name)
            logger.info("✓ Lifecycle policy deleted")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Failed to delete lifecycle policy: {error_code}")
            return False

    def show_current_policy(self) -> None:
        """Display current lifecycle policy in readable format."""
        policy = self.get_current_policy()

        if policy is None:
            print("\n❌ No lifecycle policy configured for this bucket\n")
            return

        print("\n" + "="*80)
        print("CURRENT LIFECYCLE POLICY")
        print("="*80)
        print(f"Bucket: {self.bucket_name}")
        print(f"Region: {self.region}")
        print()

        rules = policy.get('Rules', [])
        for i, rule in enumerate(rules, 1):
            print(f"Rule {i}: {rule.get('ID', rule.get('Id', 'Unnamed'))}")
            print(f"  Status: {rule.get('Status', 'Unknown')}")

            # Show filter
            filter_config = rule.get('Filter', {})
            if 'Prefix' in filter_config:
                print(f"  Prefix: {filter_config['Prefix']}")
            if 'Tag' in filter_config:
                tag = filter_config['Tag']
                print(f"  Tag: {tag.get('Key')}={tag.get('Value')}")

            # Show transitions
            transitions = rule.get('Transitions', [])
            if transitions:
                print("  Transitions:")
                for transition in transitions:
                    days = transition.get('Days', 'N/A')
                    storage_class = transition.get('StorageClass', 'Unknown')
                    print(f"    - After {days} days → {storage_class}")

            # Show expiration
            expiration = rule.get('Expiration', {})
            if expiration:
                if 'Days' in expiration:
                    print(f"  Expiration: After {expiration['Days']} days")

            print()

        print("="*80)
        print()

    def create_custom_policy(
        self,
        raw_days: int = 1,
        processed_days: int = 30,
        database_days: int = 7,
        notes_days_ia: int = 30,
        notes_days_glacier: int = 90
    ) -> Dict:
        """Create a custom lifecycle policy with specified transition days.

        Args:
            raw_days: Days before raw backups move to Deep Archive
            processed_days: Days before processed files move to Glacier
            database_days: Days before database backups move to Deep Archive
            notes_days_ia: Days before notes move to Standard-IA
            notes_days_glacier: Days before notes move to Glacier

        Returns:
            Dictionary with lifecycle policy
        """
        policy = {
            "Rules": [
                {
                    "Id": "TransitionRawBackupsToDeepArchive",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "backups/raw/"},
                    "Transitions": [
                        {"Days": raw_days, "StorageClass": "DEEP_ARCHIVE"}
                    ]
                },
                {
                    "Id": "TransitionProcessedToGlacier",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "backups/processed/"},
                    "Transitions": [
                        {"Days": processed_days, "StorageClass": "GLACIER_FLEXIBLE_RETRIEVAL"}
                    ]
                },
                {
                    "Id": "TransitionDatabaseBackupsToDeepArchive",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "backups/database/"},
                    "Transitions": [
                        {"Days": database_days, "StorageClass": "DEEP_ARCHIVE"}
                    ]
                },
                {
                    "Id": "TransitionNotesToStandardIA",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "backups/notes/"},
                    "Transitions": [
                        {"Days": notes_days_ia, "StorageClass": "STANDARD_IA"},
                        {"Days": notes_days_glacier, "StorageClass": "GLACIER_FLEXIBLE_RETRIEVAL"}
                    ]
                }
            ]
        }
        return policy


def estimate_costs(total_gb: float, storage_class: str = 'DEEP_ARCHIVE', region: str = 'us-east-1') -> Dict[str, float]:
    """Estimate monthly and annual storage costs.

    Args:
        total_gb: Total storage in gigabytes
        storage_class: S3 storage class
        region: AWS region

    Returns:
        Dictionary with cost estimates
    """
    # Costs per GB/month (approximate, varies by region)
    costs_per_gb = {
        'STANDARD': 0.023,
        'STANDARD_IA': 0.0125,
        'GLACIER_FLEXIBLE_RETRIEVAL': 0.0036,
        'GLACIER_IR': 0.0040,
        'DEEP_ARCHIVE': 0.00099
    }

    cost_per_gb = costs_per_gb.get(storage_class, 0.023)
    monthly_cost = total_gb * cost_per_gb
    annual_cost = monthly_cost * 12

    return {
        'storage_gb': total_gb,
        'storage_class': storage_class,
        'cost_per_gb_month': cost_per_gb,
        'monthly_cost': monthly_cost,
        'annual_cost': annual_cost
    }


if __name__ == '__main__':
    # Example usage
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python lifecycle_manager.py <bucket-name> [region]")
        print("\nExample:")
        print("  python lifecycle_manager.py my-backup-bucket us-east-1")
        sys.exit(1)

    bucket = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else 'us-east-1'

    manager = LifecycleManager(bucket, region)

    print("\nShowing current lifecycle policy...")
    manager.show_current_policy()

    print("\nTo apply the default lifecycle policy, run:")
    print(f"  python -m s3_backup.cli configure-lifecycle --bucket {bucket}")
