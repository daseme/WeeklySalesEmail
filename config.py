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
    management_recipients: List[str]
    ae_budgets: Dict[str, AEBudget]
    test_mode: bool = False
    test_email: str = None

    @classmethod
    def load_from_json(cls, config_path: str) -> "Config":
        with open(config_path, "r") as f:
            config_data = json.load(f)

        ae_budgets = {
            name: AEBudget(**budget_data)
            for name, budget_data in config_data["ae_budgets"].items()
        }

        email_recipients = cls._load_email_recipients(config_data["ae_list"])
        
        # Load management recipients
        management_recipients = [
            "kurt.olmstead@crossingstv.com",
            "daniel.sakaya@crossingstv.com"
        ]
        if config_data.get("test_mode", False):
            management_recipients = [os.getenv("TEST_EMAIL", "kurt.olmstead@crossingstv.com")]

        return cls(
            root_path=config_data["root_path"],
            reports_folder=config_data["reports_folder"],
            vba_path=config_data["vba_path"],
            sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
            sender_email=os.getenv("SENDER_EMAIL", "portaladmin@crossingstv.com"),
            email_recipients=email_recipients,
            management_recipients=management_recipients,
            ae_budgets=ae_budgets,
            test_mode=config_data.get("test_mode", False),
            test_email=os.getenv("TEST_EMAIL", "kurt.olmstead@crossingstv.com"),
        )

    @staticmethod
    def _load_email_recipients(ae_list: List[str]) -> Dict[str, List[str]]:
        email_recipients = {}
        for ae in ae_list:
            env_key = f"AE_EMAILS_{ae.upper()}"
            emails_str = os.getenv(env_key, "")
            if emails_str:
                email_recipients[ae] = [email.strip() for email in emails_str.split(",")]
            else:
                email_recipients[ae] = []
        return email_recipients

    @classmethod
    def load_default(cls, test_mode: bool = False) -> "Config":
        #root = Path("C:/Users/kurt/Crossings TV Dropbox/kurt olmstead/Financial")
        root = Path("C:/Users/kurto/Crossings TV Dropbox/kurt olmstead/Financial")

        sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")
        test_email = os.getenv("TEST_EMAIL", "kurt.olmstead@crossingstv.com")
        sender_email = os.getenv("SENDER_EMAIL", "portaladmin@crossingstv.com")

        if not sendgrid_api_key and not test_mode:
            raise ValueError("SendGrid API key not found in environment variables")

        ae_list = ["Charmaine", "WorldLink", "Riley"]
        email_recipients = {}
        
        if test_mode:
            email_recipients = {ae: [test_email] for ae in ae_list}
        else:
            email_recipients = cls._load_email_recipients(ae_list)

        management_recipients = [test_email] if test_mode else [
            "kurt.olmstead@crossingstv.com",
            "daniel.sakaya@crossingstv.com"
        ]

        return cls(
            root_path=str(root),
            reports_folder=str(root / "Sales/WeeklyReports/reports"),
            vba_path=str(root / "Sales/WeeklyReports/vbaProject.bin"),
            sendgrid_api_key=sendgrid_api_key,
            sender_email=sender_email,
            email_recipients=email_recipients,
            management_recipients=management_recipients,
            ae_budgets={
                "Charmaine": AEBudget(440684, 499694, 482675, 589823),
                "Riley": AEBudget(274375, 205875, 888509, 935867),
                "WorldLink": AEBudget(136251, 152100, 134550, 162099),
            },
            test_mode=test_mode,
            test_email=test_email,
        )

    def get_forecast_path(self) -> str:
        return str(Path(self.root_path) / "Forecast/*.xlsx")

    def validate(self) -> bool:
        """Validate the configuration settings"""
        if not os.path.exists(self.root_path):
            raise ValueError(f"Root path does not exist: {self.root_path}")

        if not os.path.exists(self.vba_path):
            raise ValueError(f"VBA project file does not exist: {self.vba_path}")

        os.makedirs(self.reports_folder, exist_ok=True)

        if not self.sendgrid_api_key and not self.test_mode:
            raise ValueError("SendGrid API key is not set")

        if not self.sender_email or "@" not in self.sender_email:
            raise ValueError(f"Invalid sender email: {self.sender_email}")

        # Validate test mode settings
        if self.test_mode:
            # Validate AE recipients in test mode
            for ae, recipients in self.email_recipients.items():
                if recipients != [self.test_email]:
                    raise ValueError(f"Test mode recipients for {ae} contain non-test emails")
            
            # Validate management recipients in test mode
            if self.management_recipients != [self.test_email]:
                raise ValueError("Test mode management recipients contain non-test emails")
                
        # Validate production mode settings
        else:
            # Validate AE recipients
            for ae, recipients in self.email_recipients.items():
                if not recipients:
                    raise ValueError(f"No email recipients specified for {ae}")
                for email in recipients:
                    if "@" not in email:
                        raise ValueError(f"Invalid email address for {ae}: {email}")
            
            # Validate management recipients
            if not self.management_recipients:
                raise ValueError("No management recipients specified")
            for email in self.management_recipients:
                if "@" not in email:
                    raise ValueError(f"Invalid management email address: {email}")

        # Validate budgets
        if not self.ae_budgets:
            raise ValueError("No AE budgets specified")

        for ae in self.email_recipients.keys():
            if ae not in self.ae_budgets:
                raise ValueError(f"No budget specified for AE: {ae}")

        return True

    def get_quarter_columns(self) -> List[str]:
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
   "ae_list": ["Charmaine", "WorldLink", "Riley"],
   "management_recipients": [
       "kurt.olmstead@crossingstv.com",
       "daniel.sakaya@crossingstv.com"
   ],
   "ae_budgets": {
       "Charmaine": {"q1": 440684, "q2": 499694, "q3": 482675, "q4": 589823},
       "Riley": {"q1": 274375, "q2": 205875, "q3": 888509, "q4": 935867}, 
       "WorldLink": {"q1": 136251, "q2": 152100, "q3": 134550, "q4": 162099},
   },
}
