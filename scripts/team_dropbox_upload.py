#!/usr/bin/env python3
"""
Dropbox uploader for team token using select-user header.
Uploads generated report files and logs to Dropbox.
"""

import os
import sys
import logging
import json
import requests
import datetime
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("team_dropbox_upload")

# Constants
CONFIG_FILE = "config.json"
DATA_DIR = "data"
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
LOGS_DIR = os.path.join(REPORTS_DIR, "logs")


def load_config():
    """Load configuration from config.json file"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise


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


def create_folder(token, team_member_id, path):
    """Create a folder using select-user header"""
    logger.info(f"Creating folder: {path}")

    url = "https://api.dropboxapi.com/2/files/create_folder_v2"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Dropbox-API-Select-User": team_member_id,
    }
    data = {"path": path, "autorename": False}

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            logger.info(f"Created folder: {path}")
            return True
        elif "path/conflict" in response.text:
            logger.info(f"Folder already exists: {path}")
            return True
        else:
            logger.error(
                f"Error creating folder {path}: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        logger.error(f"Error creating folder {path}: {e}")
        return False


def upload_file(token, team_member_id, local_path, dropbox_path):
    """Upload a file using select-user header"""
    logger.info(f"Uploading {local_path} to {dropbox_path}")

    url = "https://content.dropboxapi.com/2/files/upload"
    headers = {
        "Authorization": f"Bearer {token}",
        "Dropbox-API-Arg": json.dumps(
            {
                "path": dropbox_path,
                "mode": "overwrite",
                "autorename": True,
                "mute": False,
            }
        ),
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Select-User": team_member_id,
    }

    try:
        with open(local_path, "rb") as f:
            file_data = f.read()

            response = requests.post(url, headers=headers, data=file_data)

            if response.status_code == 200:
                logger.info(f"Upload complete: {dropbox_path}")
                return True
            else:
                logger.error(
                    f"Error uploading {local_path}: {response.status_code} - {response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Error uploading {local_path}: {e}")
        return False


def ensure_folder_exists(token, team_member_id, path):
    """Ensure a folder and all its parent folders exist"""
    # Split the path into components
    parts = path.strip("/").split("/")

    # Start from the root
    current_path = ""

    # Create each folder in the path
    for part in parts:
        if not part:
            continue
        current_path = f"{current_path}/{part}"
        if not create_folder(token, team_member_id, current_path):
            return False

    return True


def upload_reports(token, team_member_id, config):
    """Upload generated report files to Dropbox"""
    # Define the Dropbox destination path for reports
    dropbox_reports_path = config.get(
        "dropbox_reports_folder", "/Financial/Sales/WeeklyReports/reports"
    )

    # Add date suffix to avoid overwriting previous reports
    today = datetime.datetime.now().strftime("%Y%m%d")
    dropbox_destination = f"{dropbox_reports_path}/run_{today}"

    # Ensure the destination folder exists
    if not ensure_folder_exists(token, team_member_id, dropbox_destination):
        logger.error(f"Could not create destination folder: {dropbox_destination}")
        return False

    # Upload all files in the reports directory (excluding logs directory)
    success = True
    for item in os.listdir(REPORTS_DIR):
        local_path = os.path.join(REPORTS_DIR, item)
        if os.path.isfile(local_path) and not item.startswith("."):
            dropbox_path = f"{dropbox_destination}/{item}"
            file_success = upload_file(token, team_member_id, local_path, dropbox_path)
            success = success and file_success

    return success


def upload_logs(token, team_member_id, config):
    """Upload log files to Dropbox"""
    # Define the Dropbox destination path for logs
    dropbox_logs_path = config.get(
        "dropbox_logs_folder", "/Financial/Sales/WeeklyReports/reports/logs"
    )

    # Only upload if logs directory exists
    if not os.path.exists(LOGS_DIR):
        logger.warning("Logs directory not found, nothing to upload")
        return True

    # Ensure the logs folder exists
    if not ensure_folder_exists(token, team_member_id, dropbox_logs_path):
        logger.error(f"Could not create logs folder: {dropbox_logs_path}")
        return False

    # Upload all log files
    success = True
    for item in os.listdir(LOGS_DIR):
        local_path = os.path.join(LOGS_DIR, item)
        if os.path.isfile(local_path) and not item.startswith("."):
            dropbox_path = f"{dropbox_logs_path}/{item}"
            file_success = upload_file(token, team_member_id, local_path, dropbox_path)
            success = success and file_success

    return success


def main():
    """Main function"""
    try:
        logger.info("Starting Dropbox upload process")

        # Load configuration
        config = load_config()

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

        # Upload reports and logs
        reports_success = upload_reports(token, team_member_id, config)
        logs_success = upload_logs(token, team_member_id, config)

        # Check overall success
        if reports_success and logs_success:
            logger.info("All files uploaded successfully")
            return 0
        else:
            logger.error("Some files failed to upload")
            return 1

    except Exception as e:
        logger.error(f"Error in upload process: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
