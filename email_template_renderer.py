from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
from datetime import datetime
import logging
import traceback
import base64

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
    total_customers: int
    ae_data: List[Dict]

class EmailTemplateRenderer:
    def __init__(self, templates_dir: Path):
        self.logger = logging.getLogger(__name__)
        self.templates_dir = Path(templates_dir)
        self.logo_base64 = ""  # Default empty string
        
        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {self.templates_dir}")
            
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True
        )
        
        self._load_css()
        self._load_logo()
    
    def _load_css(self):
        try:
            css_path = self.templates_dir / 'styles.css'
            if not css_path.exists():
                raise FileNotFoundError(f"CSS file not found at: {css_path}")
            
            with open(css_path, 'r', encoding='utf-8') as f:
                self.css_styles = f.read().strip()
                self.logger.debug(f"CSS length: {len(self.css_styles)}")
                
        except Exception as e:
            self.logger.error(f"Error loading CSS file: {str(e)}")
            raise

    def _load_logo(self):
        try:
            logo_path = self.templates_dir / 'logo.png'
            self.logger.debug(f"Looking for logo at: {logo_path}")
            
            if not logo_path.exists():
                self.logger.warning(f"Logo file not found at: {logo_path}")
                return
                
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
                # Changed to use generic image MIME type
                self.logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode('utf-8')}"
                self.logger.debug(f"Logo loaded successfully, base64 length: {len(self.logo_base64)}")
                    
        except Exception as e:
            self.logger.error(f"Error loading logo file: {str(e)}")
            raise
    
    def _format_overview_stats(self, stats: SalesStats) -> List[Dict]:
        """Format overview statistics for template"""
        result = [
            {
                'label': 'Active Customers',
                'value': stats.total_customers
            },
            {
                'label': 'Total Assigned Revenue',
                'value': self._format_currency(stats.total_assigned_revenue)
            },
            {
                'label': 'Avg Revenue per Customer',
                'value': self._format_currency(stats.avg_per_customer)
            }
        ]
        self.logger.debug(f"Formatted overview stats: {result}")
        return result

    def _format_quarterly_cards(self, stats: SalesStats, current_year: int) -> List[Dict]:
        """Format quarterly statistics cards for template"""
        result = [
            {
                'title': f'{current_year} Quarterly Overview',
                'quarters': self._format_quarterly_stats(stats.quarterly_totals)
            },
            {
                'title': 'Unassigned Revenue',
                'quarters': self._format_quarterly_stats(stats.unassigned_totals)
            }
        ]
        self.logger.debug(f"Formatted quarterly cards: {result}")
        return result
    
    def _format_quarterly_stats(self, quarterly_totals: Dict[str, float]) -> List[Dict]:
        """Format quarterly statistics for template"""
        result = [
            {
                'quarter': quarter,
                'amount': self._format_currency(amount)
            }
            for quarter, amount in sorted(quarterly_totals.items())
        ]
        self.logger.debug(f"Formatted quarterly stats: {result}")
        return result
    
    def render_management_report(self, stats: ManagementStats) -> str:
        """Render the management rollup report template"""
        try:
            template = self.env.get_template('management_report.html')
            
            context = {
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'total_revenue': self._format_currency(stats.total_revenue),
                'total_customers': stats.total_customers,
                'ae_data': self._format_ae_data(stats.ae_data),
                'logo_base64': self.logo_base64
            }
            
            return template.render(**context)
            
        except Exception as e:
            self.logger.error(f"Error rendering management template: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    def _format_ae_data(self, ae_data: List[Dict]) -> List[Dict]:
        """Format AE data for template"""
        formatted_data = []
        for ae in ae_data:
            formatted_ae = {
                'name': ae['name'],
                'total_assigned_revenue': self._format_currency(ae['total_assigned_revenue']),
                'total_customers': ae['total_customers'],
                'quarters': [
                    {
                        'name': quarter['name'],
                        'assigned': self._format_currency(quarter['assigned']),
                        'unassigned': self._format_currency(quarter['unassigned'])
                    }
                    for quarter in ae['quarters']
                ]
            }
            formatted_data.append(formatted_ae)
        return formatted_data

    def render_sales_report(self, ae_name: str, stats: SalesStats) -> str:
        """Render the sales report email template"""
        try:
            self.logger.debug(f"Starting template render for AE: {ae_name}")
            template = self.env.get_template('sales_report.html')
            current_year = datetime.now().year
            
            overview_stats = self._format_overview_stats(stats)
            quarterly_cards = self._format_quarterly_cards(stats, current_year)
            
            context = {
                'ae_name': ae_name,
                'current_year': current_year,
                'overview_stats': overview_stats,
                'quarterly_cards': quarterly_cards,
                'css_styles': self.css_styles,
                'logo_base64': self.logo_base64
            }
            
            rendered_content = template.render(**context)
            self.logger.debug(f"Template rendered successfully. Length: {len(rendered_content)}")
            
            return rendered_content
            
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    @staticmethod
    def _format_currency(amount: float) -> str:
        """Format number as currency string"""
        return f"{amount:,.2f}"