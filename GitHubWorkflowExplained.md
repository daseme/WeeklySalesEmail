# Weekly Sales Report Workflow: How It Works

## Overview

This document explains how our automated sales report system works. The system uses GitHub's "workflow" feature to automatically generate and distribute sales reports on a regular schedule. Think of it as a robot assistant that handles repetitive tasks for us without manual intervention.

![Weekly Sales Report Workflow Diagram](./sales-workflow-svg.svg "Visual representation of the sales report workflow process")
*Figure 1: Visual representation of the sales report workflow process*

## When Does It Run?

The workflow runs in two ways:

1. **Automatically**: Every Monday at 2:00 AM UTC (note: the actual workflow shows Tuesday in the code with `* * *2`)
2. **Manually**: Anyone with proper permissions can trigger it through the GitHub interface by clicking a "Run workflow" button

When running it manually, you can select "test mode" which will send reports only to test email addresses instead of the real recipients.

## What Happens Behind the Scenes?

Here's what happens step-by-step when the workflow runs:

### 1. Setting Up the Workspace

The workflow first creates a clean, temporary workspace and installs all the necessary tools:
- It makes a fresh copy of our code repository
- It installs Python 3.12
- It installs all the required Python packages listed in our requirements.txt file

### 2. Handling Dropbox Authentication

This step is particularly important and addresses a specific challenge:

**The Dropbox Challenge**: Dropbox security only allows temporary access tokens that expire quickly, which would normally require someone to manually update them.

**Our Solution**: The workflow automatically refreshes the token each time it runs:
- It takes our securely stored Dropbox "refresh token" (a long-term credential)
- It contacts Dropbox's authentication service and requests a new short-term access token
- It securely stores this new token for the current run only

This means we don't need to manually update tokens - the system handles this security requirement automatically.

### 3. Getting Data from Dropbox

Once authenticated, the workflow:
- Downloads the necessary sales data files from our Dropbox folder
- Uses a Python script (`team_dropbox_download.py`) to manage this process
- Will stop if any file download fails

### 4. Setting Configuration for the Report

The workflow adjusts some configuration settings to ensure the report generator uses the right file paths for the current environment.

### 5. Generating and Sending the Report

Finally, the workflow:
- Runs our main report generation script
- The script analyzes the sales data, creates reports, and emails them to the appropriate recipients
- If in test mode, it only sends to test email addresses

## What Could Go Wrong?

Some common issues that might occur:

1. **Dropbox Token Issues**: If our Dropbox application permissions change or the refresh token expires, the workflow will display an error message about token refresh failure.

2. **File Access Problems**: If the sales data files aren't in the expected location in Dropbox, or if our permissions change, the download step might fail.

3. **Email Delivery Issues**: If there are problems with our email service (SendGrid), reports might not be delivered.

## Required Secrets

For security, the workflow uses "secrets" (encrypted values stored in GitHub) rather than hardcoding sensitive information:

- **Email Information**: API keys and email addresses for sending reports
- **Dropbox Credentials**: Three important pieces:
  - `DROPBOX_APP_KEY` & `DROPBOX_APP_SECRET`: Identifies our application to Dropbox
  - `DROPBOX_REFRESH_TOKEN`: A long-lived credential that lets us request temporary access tokens
  - `DROPBOX_TEAM_MEMBER_ID`: Identifies which team member's files we need to access

## Setting Up For New Team Members

If you're new to the team and need to work with this workflow:

1. **Access Rights**: Make sure you have appropriate access to both the GitHub repository and the Dropbox folders
2. **Understanding the Code**: The main report generation happens in `main.py`
3. **Testing Changes**: Always use the manual trigger with test mode enabled when testing changes
4. **Dropbox Integration**: If you need to update the Dropbox connection, you'll need to work with both the Dropbox Developer Console and update the GitHub secrets

## Troubleshooting Tips

If the workflow fails:

1. Check the workflow logs in GitHub Actions to see which step failed
2. For Dropbox authentication issues, verify that our app still has the proper permissions in the Dropbox Developer Console
3. If files are missing, check the relevant Dropbox folders
4. For email problems, verify SendGrid settings and API keys

## Visual Workflow Reference

For a more detailed visual reference of this process, refer to Figure 1 at the beginning of this document. The diagram illustrates how each component connects and the exact sequence of operations that occur during the execution of the workflow.

---

*Last Updated: March 31, 2025*