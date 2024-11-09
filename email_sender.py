import os
import base64
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
import sendgrid
from sendgrid.helpers.mail import (
    Mail,
    Email,
    To,
    Content,
    Attachment,
    FileContent,
    FileType,
    FileName,
    Disposition,
    ContentId,
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


class EmailSender:
    """Handles email creation and sending operations"""

    def __init__(self, config: Config, template_renderer: EmailTemplateRenderer):
        """
        Initialize with configuration and template renderer

        Args:
            config: Application configuration object
            template_renderer: Template rendering object
        """
        self.config = config
        self.template_renderer = template_renderer
        self.sg = sendgrid.SendGridAPIClient(api_key=config.sendgrid_api_key)

    def send_report(self, ae_name: str, stats: SalesStats, report_path: str) -> bool:
        """
        Send email with report attachment to specified recipients

        Args:
            ae_name: Name of the Account Executive
            stats: Sales statistics for the AE
            report_path: Path to the Excel report file

        Returns:
            Boolean indicating success/failure
        """
        try:
            recipients = self._get_recipients(ae_name)
            mail = self._create_mail_object(ae_name, recipients, stats)
            self._add_attachment(mail, report_path)

            response = self.sg.send(mail)

            if response.status_code not in [200, 201, 202]:
                raise Exception(
                    f"Error sending email. Status code: {response.status_code}"
                )

            print(f"Email sent successfully to {ae_name}'s team!")
            return True

        except Exception as e:
            print(f"Error sending email to {ae_name}: {str(e)}")
            return False

    def _get_recipients(self, ae_name: str) -> List[str]:
        """
        Get recipient list for the AE

        Args:
            ae_name: Name of the Account Executive

        Returns:
            List of email addresses

        Raises:
            ValueError: If no recipients found for AE
        """
        recipients = self.config.email_recipients.get(ae_name, [])
        if not recipients:
            raise ValueError(f"No recipients found for {ae_name}")
        return recipients

    def _create_mail_object(
        self, ae_name: str, recipients: List[str], stats: SalesStats
    ) -> Mail:
        """
        Create the mail object with content

        Args:
            ae_name: Name of the Account Executive
            recipients: List of email addresses
            stats: Sales statistics object

        Returns:
            SendGrid Mail object
        """
        current_year = datetime.now().year
        subject = f"{ae_name} - Your {current_year} Biweekly Sales Tool"
        html_content = self.template_renderer.render_sales_report(ae_name, stats)

        mail = Mail(
            from_email=Email(self.config.sender_email),
            subject=subject,
            html_content=html_content,
        )

        for recipient in recipients:
            mail.add_to(To(recipient))

        return mail

    def _add_attachment(self, mail: Mail, file_path: str):
        """
        Add Excel file as attachment to email

        Args:
            mail: SendGrid Mail object
            file_path: Path to attachment file

        Raises:
            RuntimeError: If error occurs during attachment process
        """
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
            raise RuntimeError(f"Error adding attachment: {str(e)}") from e
