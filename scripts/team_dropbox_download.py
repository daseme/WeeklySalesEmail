#!/usr/bin/env python3
"""
Dropbox downloader for team token using select-user header.
Downloads required files from Dropbox to the local filesystem.
"""

import os
import sys
import logging
import json
import requests
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("team_dropbox_download")

# Constants
CONFIG_FILE = "config.json"
DATA_DIR = "data"
REQUIRED_DIRS = [
    "data/reports",
    "data/reports/logs",
    "data/forecast",
    "data/email_templates",
]


def load_config():
    """Load configuration from config.json file"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise


def create_local_directories():
    """Create local directory structure for data"""
    for dir_path in REQUIRED_DIRS:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")


def get_token_and_team_member_id():
    """Get the token and team member ID from environment variables"""
    # Load environment variables from .env if it exists
    load_dotenv()

    token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    team_member_id = os.environ.get(
        "DROPBOX_TEAM_MEMBER_ID", "dbmid:AACRH2RkF_4U4f9kEEGcmzLfwC6a9Z1JLIw"
    )  # Default to Kurt's ID

    if not token:
        raise ValueError("DROPBOX_ACCESS_TOKEN not found in environment variables")

    return token, team_member_id


def list_folder(token, team_member_id, path):
    """List contents of a folder using select-user header"""
    logger.info(f"Listing folder: {path}")

    url = "https://api.dropboxapi.com/2/files/list_folder"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Dropbox-API-Select-User": team_member_id,
    }
    data = {"path": path}

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            result = response.json()
            entries = result.get("entries", [])
            logger.info(f"Found {len(entries)} items in {path}")
            return entries
        else:
            logger.error(
                f"Error listing {path}: {response.status_code} - {response.text}"
            )
            return []

    except Exception as e:
        logger.error(f"Error listing {path}: {e}")
        return []


def download_file(token, team_member_id, dropbox_path, local_path):
    """Download a file using select-user header"""
    logger.info(f"Downloading {dropbox_path} to {local_path}")

    url = "https://content.dropboxapi.com/2/files/download"
    headers = {
        "Authorization": f"Bearer {token}",
        "Dropbox-API-Arg": json.dumps({"path": dropbox_path}),
        "Dropbox-API-Select-User": team_member_id,
    }

    try:
        # Ensure target directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Download to a temporary file first to avoid partial downloads
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            response = requests.post(url, headers=headers, stream=True)

            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp.write(chunk)

                # Move the temporary file to the final destination
                shutil.move(temp.name, local_path)
                logger.info(f"Download complete: {local_path}")
                return True
            else:
                logger.error(
                    f"Error downloading {dropbox_path}: {response.status_code} - {response.text}"
                )
                os.unlink(temp.name)  # Delete the temporary file
                return False

    except Exception as e:
        logger.error(f"Error downloading {dropbox_path}: {e}")
        return False


def get_latest_forecast_file(token, team_member_id, config):
    """Find the most recent forecast file in Dropbox"""
    forecast_path = config.get("dropbox_forecast_path", "/Financial/Forecast")

    # List all files in the forecast directory
    entries = list_folder(token, team_member_id, forecast_path)

    # Filter Excel files and exclude temporary files
    excel_files = [
        entry
        for entry in entries
        if entry.get("name", "").endswith(".xlsx")
        and not entry.get("name", "").startswith("~")
    ]

    if not excel_files:
        logger.error(f"No forecast Excel files found in {forecast_path}")
        return None

    # Sort files by server_modified time (newest first)
    excel_files.sort(key=lambda x: x.get("server_modified", ""), reverse=True)

    # Get the path of the newest file
    latest_file = excel_files[0]
    file_path = latest_file.get("path_display", "")
    logger.info(f"Found latest forecast file: {latest_file.get('name')}")

    return file_path


def download_latest_forecast(token, team_member_id, config):
    """Download the latest forecast file"""
    latest_file = get_latest_forecast_file(token, team_member_id, config)
    if not latest_file:
        return False

    local_path = os.path.join(DATA_DIR, "forecast", os.path.basename(latest_file))
    return download_file(token, team_member_id, latest_file, local_path)


def download_vba_file(token, team_member_id, config):
    """Download the VBA project file"""
    vba_path = config.get(
        "dropbox_vba_path", "/Financial/Sales/WeeklyReports/vbaProject.bin"
    )
    local_path = os.path.join(DATA_DIR, "vbaProject.bin")
    return download_file(token, team_member_id, vba_path, local_path)


# In team_dropbox_download.py, find the download_email_templates function
# And add a check at the beginning:


def download_email_templates(token, team_member_id, config):
    """Download email templates and assets"""
    # Check if we should use repository templates instead
    if os.environ.get("USE_REPO_TEMPLATES", "").lower() == "true":
        logger.info("Using templates from repository instead of Dropbox")
        # Copy from repo's email_templates directory to data/email_templates
        repo_templates_dir = "email_templates"
        local_template_dir = os.path.join(DATA_DIR, "WeeklySalesEmail", "email_templates")


        # Create templates directory
        os.makedirs(local_template_dir, exist_ok=True)

        # Copy all files from repo templates to data directory
        for item in os.listdir(repo_templates_dir):
            if os.path.isfile(os.path.join(repo_templates_dir, item)):
                shutil.copy(
                    os.path.join(repo_templates_dir, item),
                    os.path.join(local_template_dir, item),
                )
        logger.info(f"Copied templates from repository to {local_template_dir}")
        return True

    # Original code continues here...
    """Download email templates and assets"""
    template_path = config.get(
        "dropbox_templates_path", "/Financial/Sales/WeeklySalesEmail/email_templates"
    )
    local_template_dir = os.path.join(DATA_DIR, "WeeklySalesEmail", "email_templates")

    # Create templates directory
    os.makedirs(local_template_dir, exist_ok=True)

    # List all files in the templates directory
    entries = list_folder(token, team_member_id, template_path)

    if not entries:
        logger.error(f"No template files found in {template_path}")
        return False

    # Download each template file
    success = True
    for entry in entries:
        file_path = entry.get("path_display", "")
        file_name = entry.get("name", "")
        if file_path and file_name:
            local_path = os.path.join(local_template_dir, file_name)
            file_success = download_file(token, team_member_id, file_path, local_path)
            success = success and file_success

    return success


def main():
    """Main function"""
    try:
        logger.info("Starting Dropbox download process")

        # Load configuration
        config = load_config()

        # Create local directories
        create_local_directories()

        # Get token and team member ID
        token, team_member_id = get_token_and_team_member_id()
        logger.info(f"Using team member ID: {team_member_id}")

        # Update config paths to use direct paths instead of kurt olmstead prefix
        config["dropbox_forecast_path"] = "/Financial/Forecast"
        config["dropbox_vba_path"] = "/Financial/Sales/WeeklyReports/vbaProject.bin"
        config["dropbox_templates_path"] = (
            "/Financial/Sales/WeeklySalesEmail/email_templates"
        )
        config["dropbox_reports_folder"] = "/Financial/Sales/WeeklyReports/reports"
        config["dropbox_logs_folder"] = "/Financial/Sales/WeeklyReports/reports/logs"

        # Download required files
        success = download_latest_forecast(token, team_member_id, config)
        success = download_vba_file(token, team_member_id, config) and success
        success = download_email_templates(token, team_member_id, config) and success

        # Check overall success
        if success:
            logger.info("All files downloaded successfully")
            return 0
        else:
            logger.error("Some files failed to download")
            return 1

    except Exception as e:
        logger.error(f"Error in download process: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
