from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass, field
from datetime import datetime
import logging
import traceback
import base64


@dataclass
class QuarterData:
    """Container for quarterly budget and performance data"""

    name: str
    assigned: float
    unassigned: float
    budget: float
    completion_percentage: float
    previous_year_assigned: float = 0.0
    previous_year_unassigned: float = 0.0
    year_over_year_change: float = 0.0


@dataclass
class SalesStats:
    """Container for sales statistics"""

    total_customers: int
    total_assigned_revenue: float
    total_unassigned_revenue: float  # Added missing field
    quarterly_totals: Dict[str, float]
    avg_per_customer: float
    unassigned_totals: Dict[str, float]
    quarterly_data: List[QuarterData]
    previous_year_customers: int = 0
    total_previous_year_revenue: float = 0.0
    total_year_over_year_change: float = 0.0


@dataclass
class ManagementStats:
    """Container for management rollup statistics"""

    total_revenue: float
    total_unassigned_revenue: float
    total_customers: int
    ae_data: List[Dict]
    total_previous_year_revenue: float = 0.0
    total_previous_year_unassigned: float = 0.0
    total_year_over_year_change: float = 0.0
    previous_year_customers: int = 0
    company_quarters: List[Dict] = field(default_factory=list)
    company_total_budget: float = 0.0
    company_completion_percentage: float = 0.0


class EmailTemplateRenderer:
    """Handles email template rendering with enhanced budget visualization"""

    def __init__(self, templates_dir: Path):
        """Initialize the template renderer with the specified templates directory"""
        self.logger = logging.getLogger(__name__)
        self.templates_dir = Path(templates_dir)
        self.logo_base64 = ""

        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {self.templates_dir}")

        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)), autoescape=True
        )

        self._load_css()
        self._load_logo()

    def _format_currency(self, amount: float) -> str:
        """Format number as currency string"""
        return f"{int(round(amount)):,}"

    def _load_css(self) -> None:
        """Load CSS styles"""
        try:
            css_path = self.templates_dir / "styles.css"
            if not css_path.exists():
                raise FileNotFoundError(f"CSS file not found at: {css_path}")

            with open(css_path, "r", encoding="utf-8") as f:
                self.css_styles = f.read().strip()

        except Exception as e:
            self.logger.error(f"Error loading CSS file: {str(e)}")
            raise

    def _load_logo(self) -> None:
        """Load and encode company logo"""
        try:
            logo_path = self.templates_dir / "logo.png"
            if not logo_path.exists():
                return

            with open(logo_path, "rb") as f:
                logo_data = f.read()
                self.logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode('utf-8')}"

        except Exception as e:
            self.logger.error(f"Error loading logo file: {str(e)}")
            raise

    def _format_budget_data(self, quarterly_data: List[QuarterData]) -> List[Dict]:
        """Format quarterly budget data for template rendering"""
        return [
            {
                "name": q.name,
                "assigned": self._format_currency(q.assigned),
                "assigned_raw": q.assigned,  # Raw value for comparisons
                "unassigned": self._format_currency(q.unassigned),
                "budget": self._format_currency(q.budget),
                "completion_percentage": round(q.completion_percentage),
                "bar_width": f"{round(q.completion_percentage)}%",
                "previous_year_assigned": q.previous_year_assigned,  # Raw value for comparisons
                "previous_year_assigned_display": self._format_currency(
                    q.previous_year_assigned
                ),
                "year_over_year_change": q.year_over_year_change,
            }
            for q in quarterly_data
        ]

    def _format_company_quarters(self, company_quarters: List[Dict]) -> List[Dict]:
        """Ensure consistent number formatting for company quarters."""
        return [
            {
                "name": q["name"],
                "assigned": self._format_currency(q["assigned"]),
                "unassigned": self._format_currency(q["unassigned"]),
                "budget": self._format_currency(q["budget"]),
                "completion_percentage": round(q["completion_percentage"]),
                "previous_year_assigned": self._format_currency(
                    q["previous_year_assigned"]
                ),
                "year_over_year_change": round(q["year_over_year_change"], 1),
            }
            for q in company_quarters
        ]

    def _calculate_totals(self, quarterly_data: List[QuarterData]) -> Dict:
        """Calculate total values across all quarters"""
        total_assigned = sum(q.assigned for q in quarterly_data)
        total_unassigned = sum(q.unassigned for q in quarterly_data)
        total_budget = sum(q.budget for q in quarterly_data)
        total_previous_year = sum(q.previous_year_assigned for q in quarterly_data)
        total_percentage = (
            (total_assigned / total_budget * 100) if total_budget > 0 else 0
        )

        # Calculate year-over-year change for totals
        total_yoy_change = (
            ((total_assigned - total_previous_year) / total_previous_year * 100)
            if total_previous_year > 0
            else 0
        )

        return {
            "assigned": self._format_currency(total_assigned),
            "unassigned": self._format_currency(total_unassigned),
            "budget": self._format_currency(total_budget),
            "completion_percentage": round(total_percentage),
            "bar_width": f"{round(total_percentage)}%",
            "previous_year_assigned": total_previous_year,  # Raw value for comparisons
            "previous_year_assigned_display": self._format_currency(
                total_previous_year
            ),
            "year_over_year_change": total_yoy_change,
        }

    def _format_ae_data(self, ae_data: List[Dict]) -> List[Dict]:
        """Format AE data for management report template"""
        formatted_data = []
        for ae in ae_data:
            # Calculate totals for each AE
            total_budget = sum(float(quarter["budget"]) for quarter in ae["quarters"])
            total_unassigned = sum(
                float(quarter["unassigned"]) for quarter in ae["quarters"]
            )

            # Ensure numeric values for comparisons
            total_assigned_revenue = float(ae["total_assigned_revenue"])
            previous_year_revenue = float(ae.get("previous_year_revenue", 0))
            previous_year_revenue_raw = float(
                ae.get("previous_year_revenue_raw", previous_year_revenue)
            )
            year_over_year_change = float(ae.get("year_over_year_change", 0))
            total_customers = int(ae["total_customers"])
            previous_year_customers = int(ae.get("previous_year_customers", 0))

            total_completion_percentage = round(
                (total_assigned_revenue / total_budget * 100) if total_budget > 0 else 0
            )

            formatted_ae = {
                "name": ae["name"],
                # Raw values for comparisons
                "total_assigned_revenue_raw": total_assigned_revenue,
                "previous_year_revenue_raw": previous_year_revenue_raw,
                "previous_year_revenue": previous_year_revenue,  # Keep both for compatibility
                "year_over_year_change": year_over_year_change,
                "total_customers": total_customers,
                "previous_year_customers": previous_year_customers,
                # Formatted values for display
                "total_assigned_revenue": self._format_currency(total_assigned_revenue),
                "avg_per_customer": self._format_currency(
                    total_assigned_revenue / total_customers
                    if total_customers > 0
                    else 0
                ),
                "total_unassigned": self._format_currency(total_unassigned),
                "total_budget": self._format_currency(total_budget),
                "previous_year_revenue_display": self._format_currency(
                    previous_year_revenue
                ),
                "total_completion_percentage": total_completion_percentage,
                "quarters": [
                    {
                        "name": quarter["name"],
                        # Raw values for comparisons
                        "assigned_raw": float(quarter["assigned"]),
                        "previous_year_assigned_raw": float(
                            quarter.get("previous_year_assigned", 0)
                        ),
                        "year_over_year_change": float(
                            quarter.get("year_over_year_change", 0)
                        ),
                        # Formatted values for display
                        "assigned": self._format_currency(float(quarter["assigned"])),
                        "unassigned": self._format_currency(
                            float(quarter["unassigned"])
                        ),
                        "budget": self._format_currency(float(quarter["budget"])),
                        "previous_year_assigned": float(
                            quarter.get("previous_year_assigned", 0)
                        ),  # Keep as number for comparison
                        "previous_year_assigned_display": self._format_currency(
                            float(quarter.get("previous_year_assigned", 0))
                        ),
                        "previous_year_unassigned": float(
                            quarter.get("previous_year_unassigned", 0)
                        ),
                        "previous_year_unassigned_display": self._format_currency(
                            float(quarter.get("previous_year_unassigned", 0))
                        ),
                        "completion_percentage": round(
                            (
                                float(quarter["assigned"])
                                / float(quarter["budget"])
                                * 100
                            )
                            if float(quarter["budget"]) > 0
                            else 0
                        ),
                    }
                    for quarter in ae["quarters"]
                ],
                # Add annual totals with both raw and formatted values
                "annual_totals": {
                    "name": "Annual Total",
                    # Raw values for comparisons
                    "assigned_raw": total_assigned_revenue,
                    "unassigned_raw": total_unassigned,
                    "budget_raw": total_budget,
                    "previous_year_assigned_raw": previous_year_revenue_raw,
                    "year_over_year_change": year_over_year_change,
                    # Formatted values for display
                    "assigned": self._format_currency(total_assigned_revenue),
                    "unassigned": self._format_currency(total_unassigned),
                    "budget": self._format_currency(total_budget),
                    "previous_year_assigned": self._format_currency(
                        previous_year_revenue
                    ),
                    "completion_percentage": total_completion_percentage,
                },
            }
            formatted_data.append(formatted_ae)
        return formatted_data

    def render_sales_report(self, ae_name: str, stats: SalesStats) -> str:
        """Render the sales report email template with enhanced budget visualization"""
        try:
            self.logger.debug(f"Starting template render for AE: {ae_name}")
            template = self.env.get_template("sales_report.html")

            # Format quarterly data and calculate totals
            formatted_quarters = self._format_budget_data(stats.quarterly_data)
            totals = self._calculate_totals(stats.quarterly_data)

            context = {
                "ae_name": ae_name,
                "report_date": datetime.now().strftime("%m-%d-%Y"),
                "quarters": formatted_quarters,
                "totals": totals,
                "overview_stats": {
                    "total_customers": stats.total_customers,
                    "total_assigned": self._format_currency(
                        stats.total_assigned_revenue
                    ),
                    "total_assigned_raw": stats.total_assigned_revenue,  # Raw value for comparisons
                    "avg_per_customer": self._format_currency(stats.avg_per_customer),
                    "previous_year_customers": stats.previous_year_customers,
                    "total_previous_year_revenue_display": self._format_currency(
                        stats.total_previous_year_revenue
                    ),
                    "total_previous_year_revenue": stats.total_previous_year_revenue,  # Raw value for comparisons
                    "total_year_over_year_change": stats.total_year_over_year_change,
                },
                "css_styles": self.css_styles,
                "logo_base64": self.logo_base64,
            }

            return template.render(**context)

        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    def render_management_report(self, stats: ManagementStats) -> str:
        try:
            template = self.env.get_template("management_report.html")

            # Format AE data first
            formatted_ae_data = self._format_ae_data(stats.ae_data)

            # Ensure company_quarters is correctly formatted
            formatted_company_quarters = [
                {
                    "name": quarter["name"],
                    "assigned": self._format_currency(quarter.get("assigned", 0)),
                    "unassigned": self._format_currency(quarter.get("unassigned", 0)),
                    "budget": self._format_currency(quarter.get("budget", 0)),
                    "completion_percentage": round(
                        quarter.get("completion_percentage", 0)
                    ),
                    "previous_year_assigned": self._format_currency(
                        quarter.get("previous_year_assigned", 0)
                    ),
                    "previous_year_assigned_raw": quarter.get(
                        "previous_year_assigned", 0
                    ),  # Keep raw value for logic
                    "previous_year_assigned_display": self._format_currency(
                        quarter.get("previous_year_assigned", 0)
                    ),
                    "year_over_year_change": round(
                        quarter.get("year_over_year_change", 0), 1
                    ),
                }
                for quarter in stats.company_quarters
            ]

            context = {
                "total_revenue": self._format_currency(stats.total_revenue),
                "total_previous_year_revenue": self._format_currency(
                    stats.total_previous_year_revenue
                ),
                "total_previous_year_revenue_raw": stats.total_previous_year_revenue,  # Keep raw value
                "total_previous_year_revenue_display": self._format_currency(
                    stats.total_previous_year_revenue
                ),
                "total_year_over_year_change": round(
                    stats.total_year_over_year_change, 1
                ),
                "total_customers": int(stats.total_customers),
                "previous_year_customers": int(stats.previous_year_customers),
                "company_quarters": formatted_company_quarters,
                "company_total_budget": self._format_currency(
                    stats.company_total_budget
                ),
                "company_completion_percentage": round(
                    stats.company_completion_percentage
                ),
                "total_unassigned_revenue": self._format_currency(
                    stats.total_unassigned_revenue
                ),
                "ae_data": formatted_ae_data,
            }

            return template.render(**context)

        except Exception as e:
            self.logger.error(f"Error rendering management template: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
