from dataclasses import dataclass
from typing import Dict, List
import os
from pathlib import Path
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AEBudget:
    """Represents the quarterly budget for an Account Executive"""

    q1: float
    q2: float
    q3: float
    q4: float


@dataclass
class Config:
    """Main configuration class for the sales report application"""

    root_path: str
    reports_folder: str
    vba_path: str
    sendgrid_api_key: str
    sender_email: str
    email_recipients: Dict[str, List[str]]
    ae_budgets: Dict[str, AEBudget]
    test_mode: bool = False
    test_email: str = "kurt.olmstead@crossingstv.com"

    @classmethod
    def load_from_json(cls, config_path: str) -> "Config":
        """
        Load configuration from a JSON file

        Args:
            config_path: Path to the JSON configuration file

        Returns:
            Config object with settings loaded from JSON
        """
        with open(config_path, "r") as f:
            config_data = json.load(f)

        # Convert budget dictionaries to AEBudget objects
        ae_budgets = {
            name: AEBudget(**budget_data)
            for name, budget_data in config_data["ae_budgets"].items()
        }

        return cls(
            root_path=config_data["root_path"],
            reports_folder=config_data["reports_folder"],
            vba_path=config_data["vba_path"],
            sendgrid_api_key=config_data["sendgrid_api_key"],
            sender_email=config_data["sender_email"],
            email_recipients=config_data["email_recipients"],
            ae_budgets=ae_budgets,
            test_mode=config_data.get("test_mode", False),
        )

    @classmethod
    def load_default(cls, test_mode: bool = False) -> "Config":
        """
        Load default configuration settings

        Args:
            test_mode: If True, only sends emails to test_email address

        Returns:
            Config object with default settings
        """
        root = Path("C:/Users/kurt/Crossings TV Dropbox/kurt olmstead/Financial")

        # Production email lists
        prod_recipients = {
            "Charmaine": [
                "kurt.olmstead@crossingstv.com",
                "aki.li@crossingstv.com",
                "daniel.sakaya@crossingstv.com",
                "katherine.lynch@crossingstv.com",
                "mariela.lahoz@crossingstv.com",
                "charmaine.lane@crossingstv.com",
            ],
            "WorldLink": [
                "kurt.olmstead@crossingstv.com",
                "aki.li@crossingstv.com",
                "daniel.sakaya@crossingstv.com",
                "mariela.lahoz@crossingstv.com",
                "katherine.lynch@crossingstv.com",
            ],
            "Riley": [
                "kurt.olmstead@crossingstv.com",
                "aki.li@crossingstv.com",
                "daniel.sakaya@crossingstv.com",
                "katherine.lynch@crossingstv.com",
                "mariela.lahoz@crossingstv.com",
            ],
        }

        # Test mode email lists - only send to test email
        test_recipients = {
            "Charmaine": ["kurt.olmstead@crossingstv.com"],
            "WorldLink": ["kurt.olmstead@crossingstv.com"],
            "Riley": ["kurt.olmstead@crossingstv.com"],
        }

        # Load SendGrid API key from environment variable
        sendgrid_api_key = os.getenv(
            "SENDGRID_API_KEY",
            "",
        )
        if not sendgrid_api_key and not test_mode:
            raise ValueError("SendGrid API key not found in environment variables")

        return cls(
            root_path=str(root),
            reports_folder=str(root / "Sales/WeeklyReports/reports"),
            vba_path=str(root / "Sales/WeeklyReports/vbaProject.bin"),
            sendgrid_api_key=sendgrid_api_key,
            sender_email="portaladmin@crossingstv.com",
            email_recipients=test_recipients if test_mode else prod_recipients,
            ae_budgets={
                "Charmaine": AEBudget(440684, 499694, 482675, 589823),
                "Riley": AEBudget(274375, 205875, 888509, 935867),
                "WorldLink": AEBudget(136251, 152100, 134550, 162099),
            },
            test_mode=test_mode,
        )

    def get_forecast_path(self) -> str:
        """
        Get the path to forecast Excel files

        Returns:
            String path to forecast files
        """
        return str(Path(self.root_path) / "Forecast/*.xlsx")

    def validate(self) -> bool:
        """
        Validate the configuration settings

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If any configuration settings are invalid
        """
        # Validate paths
        if not os.path.exists(self.root_path):
            raise ValueError(f"Root path does not exist: {self.root_path}")

        if not os.path.exists(self.vba_path):
            raise ValueError(f"VBA project file does not exist: {self.vba_path}")

        # Ensure reports folder exists
        os.makedirs(self.reports_folder, exist_ok=True)

        # Validate API key
        if not self.sendgrid_api_key and not self.test_mode:
            raise ValueError("SendGrid API key is not set")

        # Validate email addresses
        if not self.sender_email or "@" not in self.sender_email:
            raise ValueError(f"Invalid sender email: {self.sender_email}")

        if self.test_mode:
            # In test mode, verify all recipients lists contain only test_email
            for ae, recipients in self.email_recipients.items():
                if recipients != [self.test_email]:
                    raise ValueError(
                        f"Test mode recipients for {ae} contain non-test emails"
                    )
        else:
            # In production mode, verify all recipient email addresses
            for ae, recipients in self.email_recipients.items():
                if not recipients:
                    raise ValueError(f"No email recipients specified for {ae}")
                for email in recipients:
                    if "@" not in email:
                        raise ValueError(f"Invalid email address for {ae}: {email}")

        # Validate budgets
        if not self.ae_budgets:
            raise ValueError("No AE budgets specified")

        for ae in self.email_recipients.keys():
            if ae not in self.ae_budgets:
                raise ValueError(f"No budget specified for AE: {ae}")

        return True

    def get_quarter_columns(self) -> List[str]:
        """
        Get list of quarter column names for current year

        Returns:
            List of quarter column names (e.g., ['24Q1', '24Q2', '24Q3', '24Q4'])
        """
        year = str(datetime.now().year)[2:]
        return [f"{year}Q{i}" for i in range(1, 5)]


# Example configuration structure for reference
EXAMPLE_CONFIG = {
    "root_path": "C:/Users/kurt/Crossings TV Dropbox/kurt olmstead/Financial",
    "reports_folder": "C:/Users/kurt/Crossings TV Dropbox/kurt olmstead/Financial/Sales/WeeklyReports/reports",
    "vba_path": "C:/Users/kurt/Crossings TV Dropbox/kurt olmstead/Financial/Sales/WeeklyReports/vbaProject.bin",
    "sendgrid_api_key": "YOUR_API_KEY_HERE",
    "sender_email": "portaladmin@crossingstv.com",
    "test_mode": False,
    "email_recipients": {
        "Charmaine": ["kurt.olmstead@crossingstv.com"],
        "WorldLink": ["kurt.olmstead@crossingstv.com"],
        "Riley": ["kurt.olmstead@crossingstv.com"],
    },
    "ae_budgets": {
        "Charmaine": {"q1": 440684, "q2": 499694, "q3": 482675, "q4": 589823},
        "Riley": {"q1": 274375, "q2": 205875, "q3": 888509, "q4": 935867},
        "WorldLink": {"q1": 136251, "q2": 152100, "q3": 134550, "q4": 162099},
    },
}
