import os
import base64
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
import logging
import sendgrid
from sendgrid.helpers.mail import (
    Mail, Email, To, Content, Attachment,
    FileContent, FileType, FileName, 
    Disposition, ContentId
)
from config import Config
from email_template_renderer import EmailTemplateRenderer


@dataclass
class SalesStats:
    """Container for sales statistics"""
    total_customers: int
    total_assigned_revenue: float
    quarterly_totals: Dict[str, float]
    avg_per_customer: float
    unassigned_totals: Dict[str, float]


@dataclass
class ManagementStats:
    """Container for management rollup statistics"""
    total_revenue: float
    total_unassigned_revenue: float
    total_customers: int
    ae_data: List[Dict]


class EmailSender:
    def __init__(self, config: Config, template_renderer: EmailTemplateRenderer):
        """Initialize with configuration and template renderer"""
        self.config = config
        self.template_renderer = template_renderer
        logger = logging.getLogger(__name__)
        api_key = config.sendgrid_api_key
        logger.debug(f"API Key starts with: {api_key[:5]}... and is {len(api_key)} characters long")
        self.sg = sendgrid.SendGridAPIClient(api_key=api_key)


    def send_report(self, ae_name: str, stats: SalesStats, report_path: str) -> bool:
        """Send email with report attachment to specified recipients"""
        logger = logging.getLogger(__name__)
        try:
            # Verify AE is enabled before sending
            ae_config = self.config.account_executives.get(ae_name)
            if not ae_config or not ae_config.enabled:
                raise ValueError(f"AE {ae_name} is not enabled or doesn't exist")

            recipients = self._get_recipients(ae_name)
            mail = self._create_mail_object(ae_name, recipients, stats)
            self._add_attachment(mail, report_path)

            response = self.sg.send(mail)
            if response.status_code not in [200, 201, 202]:
                raise Exception(f"Error sending email. Status code: {response.status_code}")

            logger.info(f"Email sent successfully to {ae_name}'s team!")
            return True

        except Exception as e:
            logger.error(f"Error sending email to {ae_name}: {str(e)}")
            return False


    def send_management_report(self, stats: ManagementStats) -> bool:
        """Send management rollup report"""
        logger = logging.getLogger(__name__)
        try:
            recipients = self.config.management_recipients
            if isinstance(recipients, list) and len(recipients) == 1:
                # Split the comma-separated string into a list of emails
                recipients = recipients[0].split(',')

            if not recipients:
                raise ValueError("No management recipients configured")

            logger.info(f"Preparing management report for recipients: {recipients}")
            mail = self._create_management_mail(stats, recipients)
            logger.info(f"Sending management report with subject: {mail.subject}")
            response = self.sg.send(mail)

            if response.status_code not in [200, 201, 202]:
                raise Exception(f"Error sending management email. Status code: {response.status_code}")

            logger.info(f"Management rollup email sent successfully to {recipients}!")
            return True

        except Exception as e:
            logger.error(f"Error sending management email: {str(e)}")
            return False


    def _get_recipients(self, ae_name: str) -> List[str]:
        """Get recipient list for the AE"""
        recipients = self.config.email_recipients.get(ae_name, [])
        if not recipients:
            raise ValueError(f"No recipients found for {ae_name}")
        return recipients

    def _create_mail_object(self, ae_name: str, recipients: List[str], stats: SalesStats) -> Mail:
        """Create mail object for individual AE report"""
        current_year = datetime.now().year
        subject = f"{ae_name} - Your {current_year} Weekly Sales Report"
        html_content = Content(
            "text/html",
            self.template_renderer.render_sales_report(ae_name, stats)
        )

        mail = Mail(
            from_email=Email(self.config.sender_email),
            subject=subject,
            to_emails=[To(email) for email in recipients],
            html_content=html_content
        )

        return mail

    def _create_management_mail(self, stats: ManagementStats, recipients: List[str]) -> Mail:
        """Create mail object for management report."""
        subject = f"Weekly Sales Management Report - {datetime.now().strftime('%Y-%m-%d')}"
        html_content = self.template_renderer.render_management_report(stats)

        mail = Mail(
            from_email=self.config.sender_email,  # Keep this as it was originally
            to_emails=recipients,  # Keep this as a list of strings
            subject=subject,
            html_content=html_content
        )

        # Attach the logo
        self._attach_logo(mail)

        return mail


    def _add_attachment(self, mail: Mail, file_path: str) -> None:
        """Add Excel file as attachment to email"""
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                encoded = base64.b64encode(data).decode()

            attachment = Attachment()
            attachment.file_content = FileContent(encoded)
            attachment.file_type = FileType(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            attachment.file_name = FileName(os.path.basename(file_path))
            attachment.disposition = Disposition("attachment")
            attachment.content_id = ContentId("Excel_Report")

            mail.add_attachment(attachment)

        except Exception as e:
            raise RuntimeError(f"Error adding attachment: {str(e)}")
        
    def _attach_logo(self, mail: Mail) -> None:
        """Attach company logo as an inline image."""
        logger = logging.getLogger(__name__)
        logo_path = self.config.logo_path

        if not os.path.exists(logo_path):
            logger.warning(f"Logo file not found at {logo_path}, skipping attachment.")
            return

        try:
            with open(logo_path, "rb") as img:
                encoded_logo = base64.b64encode(img.read()).decode()

            attachment = Attachment(
                file_content=FileContent(encoded_logo),
                file_type=FileType("image/png"),
                file_name=FileName("company_logo.png"),
                disposition=Disposition("inline"),
                content_id=ContentId("company_logo")
            )

            mail.add_attachment(attachment)

        except Exception as e:
            logger.error(f"Error attaching logo: {str(e)}")