#!/usr/bin/env bash

################################################################################
# S3 Backup Bucket Setup Script
#
# This script automates the setup of an S3 bucket for the astro_cat s3_backup
# module, including:
# - AWS CLI installation verification and installation
# - S3 bucket creation with proper configuration
# - Lifecycle policy application for cost optimization
# - Optional bucket versioning
# - Setup validation
#
# Usage: ./setup_s3_bucket.sh
################################################################################

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'  # Using cyan instead of dark blue for better contrast
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIFECYCLE_POLICY_FILE="${SCRIPT_DIR}/lifecycle_policy.json"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${CYAN}===================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}===================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to prompt for yes/no
prompt_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="${prompt} [Y/n]: "
    else
        prompt="${prompt} [y/N]: "
    fi

    read -r -p "$prompt" response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy]$ ]]
}

# Function to validate AWS region
validate_aws_region() {
    local region="$1"
    # Basic validation - just check format
    if [[ ! "$region" =~ ^[a-z]{2}-[a-z]+-[0-9]{1}$ ]]; then
        return 1
    fi
    return 0
}

# Function to validate S3 bucket name
validate_bucket_name() {
    local bucket="$1"

    # Check length
    if [[ ${#bucket} -lt 3 || ${#bucket} -gt 63 ]]; then
        print_error "Bucket name must be between 3 and 63 characters"
        return 1
    fi

    # Check format
    if [[ ! "$bucket" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]]; then
        print_error "Bucket name must start and end with lowercase letter or number"
        print_error "Can only contain lowercase letters, numbers, hyphens, and periods"
        return 1
    fi

    # Check for consecutive periods
    if [[ "$bucket" =~ \.\. ]]; then
        print_error "Bucket name cannot contain consecutive periods"
        return 1
    fi

    # Check for IP address format
    if [[ "$bucket" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        print_error "Bucket name cannot be formatted as an IP address"
        return 1
    fi

    return 0
}

# Function to generate default bucket name
generate_default_bucket_name() {
    # Generate 12-character random hex ID
    local random_id
    random_id=$(openssl rand -hex 6)
    echo "fits-cataloger-backup-${random_id}"
}

################################################################################
# AWS CLI Installation
################################################################################

check_and_install_aws_cli() {
    print_header "Step 1: Checking AWS CLI Installation"

    if command_exists aws; then
        local current_version
        current_version=$(aws --version 2>&1 | cut -d' ' -f1 | cut -d'/' -f2)
        print_success "AWS CLI is already installed (version: $current_version)"

        # Check if it's AWS CLI v2
        if [[ "$current_version" =~ ^2\. ]]; then
            print_success "AWS CLI v2 detected - you have the latest major version"
            return 0
        else
            print_warning "AWS CLI v1 detected. Version 2 is recommended."
            if prompt_yes_no "Would you like to upgrade to AWS CLI v2?" "n"; then
                install_aws_cli_v2
            else
                print_info "Continuing with AWS CLI v1..."
                return 0
            fi
        fi
    else
        print_warning "AWS CLI is not installed"
        if prompt_yes_no "Would you like to install AWS CLI v2 now?" "y"; then
            install_aws_cli_v2
        else
            print_error "AWS CLI is required. Please install it manually and re-run this script."
            print_info "Installation guide: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
            exit 1
        fi
    fi
}

install_aws_cli_v2() {
    print_info "Installing AWS CLI v2..."

    local os_type
    os_type=$(uname -s)

    case "$os_type" in
        Linux)
            install_aws_cli_linux
            ;;
        Darwin)
            install_aws_cli_macos
            ;;
        *)
            print_error "Unsupported operating system: $os_type"
            print_info "Please install AWS CLI manually: https://aws.amazon.com/cli/"
            exit 1
            ;;
    esac
}

install_aws_cli_linux() {
    print_info "Detected Linux system"

    # Check for required tools
    if ! command_exists curl; then
        print_error "curl is required but not installed. Please install curl first."
        exit 1
    fi

    if ! command_exists unzip; then
        print_error "unzip is required but not installed. Please install unzip first."
        exit 1
    fi

    # Create temporary directory
    local temp_dir
    temp_dir=$(mktemp -d)
    cd "$temp_dir" || exit 1

    print_info "Downloading AWS CLI v2..."
    if curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; then
        print_success "Download complete"
    else
        print_error "Failed to download AWS CLI"
        rm -rf "$temp_dir"
        exit 1
    fi

    print_info "Extracting archive..."
    unzip -q awscliv2.zip

    print_info "Installing AWS CLI (may require sudo)..."
    if sudo ./aws/install; then
        print_success "AWS CLI v2 installed successfully"
    else
        print_error "Installation failed"
        rm -rf "$temp_dir"
        exit 1
    fi

    # Cleanup
    cd - > /dev/null || exit 1
    rm -rf "$temp_dir"

    # Verify installation
    if command_exists aws; then
        local version
        version=$(aws --version 2>&1)
        print_success "Verification: $version"
    else
        print_error "Installation appeared to succeed but 'aws' command not found"
        print_info "You may need to restart your shell or update your PATH"
        exit 1
    fi
}

install_aws_cli_macos() {
    print_info "Detected macOS system"

    # Check for Homebrew
    if command_exists brew; then
        print_info "Installing AWS CLI via Homebrew..."
        brew install awscli
        print_success "AWS CLI installed successfully"
    else
        print_info "Homebrew not found. Installing using official installer..."

        local temp_dir
        temp_dir=$(mktemp -d)
        cd "$temp_dir" || exit 1

        print_info "Downloading AWS CLI v2..."
        curl -s "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"

        print_info "Installing AWS CLI (may require sudo)..."
        sudo installer -pkg AWSCLIV2.pkg -target /

        cd - > /dev/null || exit 1
        rm -rf "$temp_dir"

        print_success "AWS CLI v2 installed successfully"
    fi
}

################################################################################
# AWS Configuration
################################################################################

check_aws_configuration() {
    print_header "Step 2: Checking AWS Configuration"

    if aws sts get-caller-identity &>/dev/null; then
        local account_id
        local user_arn
        account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
        user_arn=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)

        print_success "AWS credentials are configured"
        print_info "Account ID: $account_id"
        print_info "User/Role: $user_arn"

        return 0
    else
        print_warning "AWS credentials are not configured or invalid"
        print_info ""
        print_info "Please configure AWS CLI with your credentials:"
        print_info "  $ aws configure"
        print_info ""
        print_info "You will need:"
        print_info "  - AWS Access Key ID"
        print_info "  - AWS Secret Access Key"
        print_info "  - Default region (recommended: us-west-2)"
        print_info "  - Default output format (recommended: json)"
        print_info ""

        if prompt_yes_no "Would you like to configure AWS credentials now?" "y"; then
            echo ""
            print_info "Please enter your AWS credentials:"
            echo ""

            # Prompt for access key
            read -r -p "AWS Access Key ID: " aws_access_key
            if [[ -z "$aws_access_key" ]]; then
                print_error "Access Key ID is required"
                exit 1
            fi

            # Prompt for secret key (hidden input with visual feedback)
            read -r -s -p "AWS Secret Access Key: " aws_secret_key
            # Show asterisks as feedback
            if [[ -n "$aws_secret_key" ]]; then
                echo " $(printf '*%.0s' {1..40})"
            else
                echo ""
            fi
            if [[ -z "$aws_secret_key" ]]; then
                print_error "Secret Access Key is required"
                exit 1
            fi

            # Prompt for region with default
            echo ""
            read -r -p "Default region name [us-west-2]: " aws_region
            aws_region=${aws_region:-us-west-2}

            # Prompt for output format with default
            read -r -p "Default output format [json]: " aws_output
            aws_output=${aws_output:-json}

            # Configure credentials and settings
            aws configure set aws_access_key_id "$aws_access_key"
            aws configure set aws_secret_access_key "$aws_secret_key"
            aws configure set region "$aws_region"
            aws configure set output "$aws_output"

            print_success "Set default region to $aws_region"
            print_success "Set default output format to $aws_output"

            # Verify after configuration
            if aws sts get-caller-identity &>/dev/null; then
                print_success "AWS credentials configured successfully"
                return 0
            else
                print_error "AWS credentials verification failed"
                exit 1
            fi
        else
            print_error "AWS credentials are required. Please configure and re-run this script."
            exit 1
        fi
    fi
}

################################################################################
# Bucket Configuration
################################################################################

get_bucket_configuration() {
    print_header "Step 3: Bucket Configuration"

    # Generate suggested bucket name
    local suggested_name
    suggested_name=$(generate_default_bucket_name)

    # Get bucket name
    while true; do
        echo -e "${CYAN}Enter S3 bucket name${NC}"
        echo -e "${CYAN}[Press Enter for: $suggested_name]:${NC}"
        read -r BUCKET_NAME
        BUCKET_NAME=${BUCKET_NAME:-$suggested_name}

        if validate_bucket_name "$BUCKET_NAME"; then
            break
        fi
    done

    # Get region
    while true; do
        echo -e "\n${CYAN}Enter AWS region (e.g., us-west-2, us-east-1, ca-west-1, eu-west-1):${NC}"
        echo -e "${CYAN}[Press Enter for us-west-2]:${NC}"
        read -r AWS_REGION
        AWS_REGION=${AWS_REGION:-us-west-2}

        if validate_aws_region "$AWS_REGION"; then
            break
        else
            print_error "Invalid region format. Examples: us-west-2, us-east-1, ca-west-1, eu-west-1"
        fi
    done

    # Show default lifecycle policy details
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}Default Lifecycle Policy (Tag-Based)${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}How it works:${NC}"
    echo -e "  The s3_backup module tags files with ${GREEN}archive_policy${NC} and ${GREEN}backup_policy${NC}."
    echo -e "  S3 lifecycle rules automatically transition files based on these tags."
    echo ""
    echo -e "${CYAN}Archive Policies (when to archive):${NC}"
    echo -e "  ${GREEN}fast${NC}:     7 days  - For raw data you won't need again"
    echo -e "  ${GREEN}standard${NC}: 30 days  - For processed files you might reference"
    echo -e "  ${GREEN}delayed${NC}:  90 days  - For processing notes and logs"
    echo ""
    echo -e "${CYAN}Backup Policies (how to archive):${NC}"
    echo -e "  ${GREEN}deep${NC}:     Direct to DEEP_ARCHIVE (cheapest, slower retrieval)"
    echo -e "  ${GREEN}flexible${NC}: GLACIER first, then DEEP_ARCHIVE (easier medium-term access)"
    echo ""
    echo -e "${CYAN}Example combinations:${NC}"
    echo -e "  ${GREEN}fast/deep${NC}:       7 days  → DEEP_ARCHIVE (raw FITS files)"
    echo -e "  ${GREEN}standard/deep${NC}:   30 days  → DEEP_ARCHIVE (final processed images)"
    echo -e "  ${GREEN}delayed/flexible${NC}: 90 days  → GLACIER → 180 days → DEEP_ARCHIVE (notes)"
    echo ""
    echo -e "${CYAN}Versioning cleanup (if enabled):${NC}"
    echo -e "  ${GREEN}•${NC} Old RAW file versions:       Deleted after 1 day"
    echo -e "  ${GREEN}•${NC} Old PROCESSED file versions: Deleted after 1 day"
    echo -e "  ${GREEN}•${NC} Old DATABASE versions:       Keep 5 newest, delete rest after 90 days"
    echo ""
    echo -e "${CYAN}Other cleanup:${NC}"
    echo -e "  ${GREEN}•${NC} Abort incomplete multipart uploads after 3 days"
    echo -e "  ${GREEN}•${NC} Remove expired delete markers (cleanup deleted files)"
    echo ""
    echo -e "${YELLOW}Cost savings:${NC} DEEP_ARCHIVE storage costs ~90% less than STANDARD"
    echo -e "                (~\$0.00099/GB/month vs ~\$0.023/GB/month)"
    echo ""

    # Apply lifecycle policy
    if prompt_yes_no "Apply this lifecycle policy? (Recommended)" "y"; then
        APPLY_LIFECYCLE=true
    else
        APPLY_LIFECYCLE=false
    fi

    # Enable versioning
    echo ""
    echo -e "${YELLOW}Note:${NC} Versioning keeps old versions of files, which can increase costs."
    echo -e "       Most users don't need this for backup archives."
    echo ""
    if prompt_yes_no "Enable bucket versioning?" "n"; then
        ENABLE_VERSIONING=true
    else
        ENABLE_VERSIONING=false
    fi

    # Summary
    echo -e "\n${CYAN}Configuration Summary:${NC}"
    echo -e "  Bucket Name: ${GREEN}$BUCKET_NAME${NC}"
    echo -e "  Region: ${GREEN}$AWS_REGION${NC}"
    echo -e "  Versioning: ${GREEN}$ENABLE_VERSIONING${NC}"
    echo -e "  Lifecycle Policy: ${GREEN}$APPLY_LIFECYCLE${NC}"
    echo ""

    if ! prompt_yes_no "Proceed with this configuration?" "y"; then
        print_info "Setup cancelled by user"
        exit 0
    fi
}

################################################################################
# S3 Bucket Creation
################################################################################

create_s3_bucket() {
    print_header "Step 4: Creating S3 Bucket"

    # Check if bucket already exists
    if aws s3 ls "s3://$BUCKET_NAME" &>/dev/null; then
        print_warning "Bucket '$BUCKET_NAME' already exists"

        # Check if it's in the correct region
        local bucket_region
        bucket_region=$(aws s3api get-bucket-location --bucket "$BUCKET_NAME" --output text 2>/dev/null || echo "unknown")

        if [[ "$bucket_region" == "None" ]]; then
            bucket_region="us-east-1"  # AWS returns 'None' for us-east-1
        fi

        if [[ "$bucket_region" == "$AWS_REGION" ]]; then
            print_success "Bucket exists in the correct region ($AWS_REGION)"

            if ! prompt_yes_no "Continue with existing bucket?" "y"; then
                print_info "Setup cancelled by user"
                exit 0
            fi
            return 0
        else
            print_error "Bucket exists but in different region: $bucket_region (expected: $AWS_REGION)"
            print_error "Please choose a different bucket name or region"
            exit 1
        fi
    fi

    print_info "Creating bucket '$BUCKET_NAME' in region '$AWS_REGION'..."

    # Create bucket (us-east-1 doesn't need location constraint)
    if [[ "$AWS_REGION" == "us-east-1" ]]; then
        if aws s3 mb "s3://$BUCKET_NAME" 2>/dev/null; then
            print_success "Bucket created successfully"
        else
            print_error "Failed to create bucket"
            print_info "Common issues:"
            print_info "  - Bucket name already taken globally"
            print_info "  - Insufficient IAM permissions"
            print_info "  - Invalid bucket name format"
            exit 1
        fi
    else
        if aws s3 mb "s3://$BUCKET_NAME" --region "$AWS_REGION" 2>/dev/null; then
            print_success "Bucket created successfully"
        else
            print_error "Failed to create bucket"
            print_info "Common issues:"
            print_info "  - Bucket name already taken globally"
            print_info "  - Insufficient IAM permissions"
            print_info "  - Invalid bucket name format"
            exit 1
        fi
    fi
}

################################################################################
# Bucket Versioning
################################################################################

configure_versioning() {
    if [[ "$ENABLE_VERSIONING" != "true" ]]; then
        print_info "Skipping versioning configuration"
        return 0
    fi

    print_header "Step 5: Configuring Bucket Versioning"

    print_info "Enabling versioning on bucket '$BUCKET_NAME'..."

    if aws s3api put-bucket-versioning \
        --bucket "$BUCKET_NAME" \
        --region "$AWS_REGION" \
        --versioning-configuration Status=Enabled 2>/dev/null; then
        print_success "Bucket versioning enabled"
    else
        print_error "Failed to enable versioning"
        print_warning "Continuing anyway - you can enable it manually later"
    fi
}

################################################################################
# Lifecycle Policy
################################################################################

configure_lifecycle_policy() {
    # Temporarily disable exit on error for this function to handle errors gracefully
    set +e

    if [[ "$APPLY_LIFECYCLE" != "true" ]]; then
        print_info "Skipping lifecycle policy configuration"
        set -e
        return 0
    fi

    print_header "Step 6: Configuring Lifecycle Policy"

    # Check if lifecycle policy file exists
    if [[ ! -f "$LIFECYCLE_POLICY_FILE" ]]; then
        print_error "Lifecycle policy file not found: $LIFECYCLE_POLICY_FILE"
        print_warning "Skipping lifecycle policy configuration"
        print_info "Expected location: $LIFECYCLE_POLICY_FILE"
        set -e
        return 1
    fi

    print_info "Applying lifecycle policy from: $LIFECYCLE_POLICY_FILE"
    print_info "Bucket: $BUCKET_NAME"
    print_info "Region: $AWS_REGION"
    print_info ""

    # Show what we're about to apply (with better error handling)
    if command_exists jq; then
        print_info "Policy contents:"
        if jq -C '.' "$LIFECYCLE_POLICY_FILE" 2>/dev/null; then
            : # jq succeeded, output already shown
        else
            cat "$LIFECYCLE_POLICY_FILE"
        fi | sed 's/^/  /' || true
        echo ""
    fi

    # Try to apply the lifecycle configuration and capture error output
    print_info "Executing: aws s3api put-bucket-lifecycle-configuration..."
    local error_output
    error_output=$(aws s3api put-bucket-lifecycle-configuration \
        --bucket "$BUCKET_NAME" \
        --lifecycle-configuration "file://$LIFECYCLE_POLICY_FILE" \
        --region "$AWS_REGION" 2>&1)
    local exit_code=$?

    print_info "Command exit code: $exit_code"

    if [[ $exit_code -eq 0 ]]; then
        print_success "Lifecycle policy command completed successfully"

        # Verify the policy was actually applied
        print_info "Verifying lifecycle policy was applied..."
        sleep 2  # Give AWS a moment to propagate

        local verify_output
        verify_output=$(aws s3api get-bucket-lifecycle-configuration \
            --bucket "$BUCKET_NAME" \
            --region "$AWS_REGION" 2>&1)
        local verify_code=$?

        if [[ $verify_code -eq 0 ]]; then
            local rule_count
            if command_exists jq; then
                rule_count=$(echo "$verify_output" | jq -r '.Rules | length' 2>/dev/null)
                if [[ -z "$rule_count" ]]; then
                    rule_count="unknown"
                fi
            else
                rule_count="unknown"
            fi

            print_success "Lifecycle policy verified! ($rule_count rules active)"

            if command_exists jq && [[ "$rule_count" != "unknown" ]]; then
                echo ""
                print_info "Active rules:"
                echo "$verify_output" | jq -r '.Rules[] | "  • \(.Id): \(.Status)"' 2>/dev/null || echo "  (Could not parse rules)"
                echo ""
            fi
        else
            print_warning "Could not verify lifecycle policy"
            echo -e "${YELLOW}Verification error:${NC}"
            echo "$verify_output" | sed 's/^/  /'
            echo ""
        fi
    else
        print_error "Failed to apply lifecycle policy (exit code: $exit_code)"
        echo -e "${RED}Error details:${NC}"
        echo "$error_output" | sed 's/^/  /'
        echo ""
        print_warning "Continuing anyway - you can apply it manually later"
        print_info ""
        print_info "Manual command:"
        print_info "  cd $SCRIPT_DIR"
        print_info "  aws s3api put-bucket-lifecycle-configuration \\"
        print_info "    --bucket $BUCKET_NAME \\"
        print_info "    --region $AWS_REGION \\"
        print_info "    --lifecycle-configuration file://lifecycle_policy.json"
        print_info ""
        print_info "Or using the s3_backup CLI:"
        print_info "  python -m s3_backup.cli configure-lifecycle --bucket $BUCKET_NAME"
        set -e
        return 1
    fi

    # Re-enable exit on error
    set -e
}

################################################################################
# Validation
################################################################################

validate_setup() {
    print_header "Step 7: Validating Setup"

    local all_good=true

    # Check bucket exists
    print_info "Checking bucket existence..."
    if aws s3 ls "s3://$BUCKET_NAME" &>/dev/null; then
        print_success "Bucket is accessible"
    else
        print_error "Cannot access bucket"
        all_good=false
    fi

    # Check versioning status
    if [[ "$ENABLE_VERSIONING" == "true" ]]; then
        print_info "Checking versioning status..."
        local version_status
        version_status=$(aws s3api get-bucket-versioning --bucket "$BUCKET_NAME" --region "$AWS_REGION" --query Status --output text 2>/dev/null)

        if [[ "$version_status" == "Enabled" ]]; then
            print_success "Versioning is enabled"
        else
            print_warning "Versioning is not enabled (status: $version_status)"
        fi
    fi

    # Check lifecycle policy
    if [[ "$APPLY_LIFECYCLE" == "true" ]]; then
        print_info "Checking lifecycle policy..."
        if aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET_NAME" --region "$AWS_REGION" &>/dev/null; then
            local rule_count
            rule_count=$(aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET_NAME" --region "$AWS_REGION" --query 'length(Rules)' --output text 2>/dev/null)
            print_success "Lifecycle policy is active ($rule_count rules)"
        else
            print_warning "No lifecycle policy configured"
        fi
    fi

    # Test write permission
    print_info "Testing write permissions..."
    local test_file="test-$(date +%s).txt"
    if echo "test" | aws s3 cp - "s3://$BUCKET_NAME/$test_file" &>/dev/null; then
        print_success "Write test successful"
        # Cleanup test file
        aws s3 rm "s3://$BUCKET_NAME/$test_file" &>/dev/null || true
    else
        print_error "Write test failed - check IAM permissions"
        all_good=false
    fi

    echo ""
    if [[ "$all_good" == "true" ]]; then
        print_success "All validation checks passed!"
    else
        print_warning "Some validation checks failed - please review above"
    fi
}

################################################################################
# Generate s3_config.json
################################################################################

generate_s3_config() {
    print_header "Step 8: Generating Configuration File"

    local config_file="${SCRIPT_DIR}/s3_config.json"

    # Check if config already exists
    if [[ -f "$config_file" ]]; then
        print_warning "Configuration file already exists: $config_file"
        if prompt_yes_no "Overwrite existing s3_config.json?" "n"; then
            print_info "Backing up existing config to s3_config.json.backup"
            cp "$config_file" "${config_file}.backup"
        else
            print_info "Keeping existing configuration file"
            return 0
        fi
    fi

    print_info "Creating s3_config.json with your bucket details..."

    # Generate the config file
    cat > "$config_file" << EOF
{
  "enabled": true,
  "aws_region": "$AWS_REGION",

  "buckets": {
    "primary": "$BUCKET_NAME",
    "backup": null
  },

  "s3_paths": {
    "raw_archives": "backups/raw",
    "session_notes": "backups/sessions",
    "processing_notes": "backups/processing",
    "final_outputs": "backups/final",
    "database_backups": "backups/database"
  },

  "backup_rules": {
    "raw_lights": {
      "archive_policy": "fast",
      "backup_policy": "deep",
      "archive_days": 7,
      "storage_class": "STANDARD"
    },
    "raw_calibration": {
      "archive_policy": "fast",
      "backup_policy": "deep",
      "archive_days": 7,
      "storage_class": "STANDARD"
    },
    "imaging_sessions": {
      "archive_policy": "standard",
      "backup_policy": "deep",
      "archive_days": 30,
      "storage_class": "STANDARD"
    },
    "processing_sessions": {
      "archive_policy": "delayed",
      "backup_policy": "flexible",
      "archive_days": 90,
      "storage_class": "STANDARD"
    }
  },

  "upload_settings": {
    "multipart_threshold_mb": 100,
    "multipart_chunksize_mb": 25,
    "max_concurrency": 4,
    "use_threads": true,
    "max_bandwidth_mbps": null
  },

  "restore_settings": {
    "default_tier": "Standard",
    "default_days": 7,
    "restore_path": "/path/to/restore"
  },

  "archive_settings": {
    "compression_level": 0,
    "use_pigz": false,
    "verify_after_upload": true,
    "keep_archive_index": true,
    "max_archive_size_gb": 50,
    "temp_dir": ".tmp/backup_archives"
  },

  "retry_settings": {
    "max_retries": 3,
    "initial_backoff_seconds": 2,
    "max_backoff_seconds": 60,
    "backoff_multiplier": 2
  },

  "logging": {
    "log_uploads": true,
    "log_verifications": true,
    "log_restores": true,
    "verbose": false
  },

  "cost_tracking": {
    "track_costs": true,
    "storage_cost_per_gb_per_month": {
      "STANDARD": 0.023,
      "STANDARD_IA": 0.013,
      "GLACIER_IR": 0.004,
      "GLACIER_FLEXIBLE": 0.004,
      "DEEP_ARCHIVE": 0.00099
    },
    "data_transfer_cost_per_gb": {
      "upload": 0.0,
      "download": 0.09
    }
  },

  "notifications": {
    "email_on_complete": false,
    "email_address": null,
    "email_on_error": true
  }
}
EOF

    if [[ -f "$config_file" ]]; then
        print_success "Configuration file created: $config_file"
        print_info "Bucket: $BUCKET_NAME"
        print_info "Region: $AWS_REGION"
        print_info ""
        print_info "You can customize the configuration by editing this file."
        return 0
    else
        print_error "Failed to create configuration file"
        return 1
    fi
}

################################################################################
# Next Steps
################################################################################

print_next_steps() {
    print_header "Setup Complete!"

    echo -e "${GREEN}Your S3 bucket is ready for use with the s3_backup module!${NC}"
    echo ""
    echo -e "${CYAN}What was configured:${NC}"
    echo "  ✓ S3 bucket: $BUCKET_NAME"
    echo "  ✓ Region: $AWS_REGION"
    echo "  ✓ Lifecycle policy: Applied"
    if [[ "$ENABLE_VERSIONING" == "true" ]]; then
        echo "  ✓ Versioning: Enabled"
    fi
    echo "  ✓ Configuration file: s3_config.json created"
    echo ""
    echo -e "${CYAN}Next steps:${NC}"
    echo ""
    echo "1. (Optional) Customize s3_config.json:"
    echo "   $ cd $SCRIPT_DIR"
    echo "   $ nano s3_config.json"
    echo ""
    echo "   The file has been pre-configured with your bucket details."
    echo "   You can adjust upload settings, archive policies, etc."
    echo ""
    echo "2. Verify the setup:"
    echo "   $ python -m s3_backup.cli status"
    echo ""
    echo "4. View lifecycle configuration:"
    echo "   $ python -m s3_backup.cli show-lifecycle"
    echo ""
    echo "5. Start backing up your imaging sessions:"
    echo "   $ python -m s3_backup.cli backup --session-id <session_id>"
    echo ""
    echo -e "${CYAN}Useful commands:${NC}"
    echo "  • List bucket contents: aws s3 ls s3://$BUCKET_NAME --region $AWS_REGION"
    echo "  • View bucket info: aws s3api head-bucket --bucket $BUCKET_NAME --region $AWS_REGION"
    echo "  • Check lifecycle: aws s3api get-bucket-lifecycle-configuration --bucket $BUCKET_NAME --region $AWS_REGION"
    echo ""
    echo -e "${YELLOW}Documentation:${NC}"
    echo "  • s3_backup README: $SCRIPT_DIR/README.md"
    echo "  • AWS S3 docs: https://docs.aws.amazon.com/s3/"
    echo ""
}

################################################################################
# Main Script
################################################################################

main() {
    clear
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                                                                ║"
    echo "║           S3 Backup Bucket Setup Script                       ║"
    echo "║           for astro_cat s3_backup module                      ║"
    echo "║                                                                ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Run setup steps
    check_and_install_aws_cli
    check_aws_configuration
    get_bucket_configuration
    create_s3_bucket
    configure_versioning
    configure_lifecycle_policy
    validate_setup
    generate_s3_config
    print_next_steps

    print_success "Script completed successfully!"
}

# Run main function
main "$@"
