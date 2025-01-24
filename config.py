from dataclasses import dataclass
from typing import Dict, List
import os
from pathlib import Path
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class AEBudget:
    """Represents the quarterly budget for an Account Executive"""
    q1: float
    q2: float
    q3: float
    q4: float

@dataclass
class AccountExecutive:
    """Represents an Account Executive's configuration"""
    enabled: bool
    budgets: AEBudget

@dataclass
class Config:
    """Main configuration class for the sales report application"""
    root_path: str
    reports_folder: str
    vba_path: str
    sendgrid_api_key: str
    sender_email: str
    email_recipients: Dict[str, List[str]]
    management_recipients: List[str]
    account_executives: Dict[str, AccountExecutive]
    test_mode: bool = False
    test_email: str = None

    @property
    def active_aes(self) -> List[str]:
        """Get list of enabled AEs"""
        return [name for name, ae in self.account_executives.items() if ae.enabled]

    def get_forecast_path(self) -> str:
        """Return the path pattern for forecast files"""
        return str(Path(self.root_path) / "Forecast/*.xlsx")

    def validate(self) -> bool:
        """Validate the configuration settings"""
        # Validate paths
        if not os.path.exists(self.root_path):
            raise ValueError(f"Root path does not exist: {self.root_path}")
        if not os.path.exists(self.vba_path):
            raise ValueError(f"VBA project file does not exist: {self.vba_path}")
        os.makedirs(self.reports_folder, exist_ok=True)

        # Validate email settings
        if not self.sendgrid_api_key and not self.test_mode:
            raise ValueError("SendGrid API key is not set")
        if not self.sender_email or "@" not in self.sender_email:
            raise ValueError(f"Invalid sender email: {self.sender_email}")

        # Validate AEs
        if not self.account_executives:
            raise ValueError("No Account Executives configured")
        if not any(ae.enabled for ae in self.account_executives.values()):
            raise ValueError("No enabled Account Executives found")

        # Validate test mode settings
        if self.test_mode:
            if self.management_recipients != [self.test_email]:
                raise ValueError("Test mode management recipients contain non-test emails")
            # Validate AE recipients in test mode
            for ae in self.active_aes:
                if self.email_recipients.get(ae, []) != [self.test_email]:
                    raise ValueError(f"Test mode recipients for {ae} contain non-test emails")
        else:
            # Validate management recipients in production mode
            if not self.management_recipients:
                raise ValueError("No management recipients specified")
            for email in self.management_recipients:
                if "@" not in email:
                    raise ValueError(f"Invalid management email address: {email}")
            # Validate AE recipients in production mode
            for ae in self.active_aes:
                recipients = self.email_recipients.get(ae, [])
                if not recipients:
                    raise ValueError(f"No email recipients specified for {ae}")
                for email in recipients:
                    if "@" not in email:
                        raise ValueError(f"Invalid email address for {ae}: {email}")

        return True

    @classmethod
    def load_from_json(cls, config_path: str) -> "Config":
        """Load configuration from a JSON file"""
        with open(config_path, "r") as f:
            config_data = json.load(f)

        # Load AEs and their budgets
        account_executives = {}
        if "account_executives" in config_data:  # Add this check
            for name, ae_data in config_data["account_executives"].items():
                account_executives[name] = AccountExecutive(
                    enabled=ae_data["enabled"],
                    budgets=AEBudget(**ae_data["budgets"])
                )

        # Create instance
        instance = cls(
            root_path=config_data.get("root_path", ""),
            reports_folder=config_data.get("reports_folder", ""),
            vba_path=config_data.get("vba_path", ""),
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            sender_email=os.getenv("SENDER_EMAIL", "portaladmin@crossingstv.com"),
            email_recipients={},
            management_recipients=config_data.get("management_recipients", []),
            account_executives=account_executives,
            test_mode=config_data.get("test_mode", False),
            test_email=os.getenv("TEST_EMAIL", "test@example.com")
        )

        # Load email recipients for enabled AEs
        enabled_aes = [name for name, ae in account_executives.items() if ae.enabled]
        instance.email_recipients = instance._load_email_recipients(enabled_aes)  # This should work now

        return instance
    
    def _load_email_recipients(self, ae_list: List[str]) -> Dict[str, List[str]]:
        """Load email recipients from environment variables"""
        email_recipients = {}
        for ae in ae_list:
            env_key = f"AE_EMAILS_{ae.upper().replace(' ', '_')}"
            emails_str = os.getenv(env_key, "")
            if emails_str:
                email_recipients[ae] = [email.strip() for email in emails_str.split(",")]
            else:
                email_recipients[ae] = []
        return email_recipients