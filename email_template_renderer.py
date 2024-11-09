from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
from datetime import datetime
import logging
import traceback

@dataclass
class SalesStats:
    """Container for sales statistics"""
    total_customers: int
    total_assigned_revenue: float
    quarterly_totals: Dict[str, float]
    avg_per_customer: float
    unassigned_totals: Dict[str, float]

class EmailTemplateRenderer:
    """Handles email template rendering"""
    
    def __init__(self, templates_dir: Path):
        """Initialize the template renderer"""
        self.logger = logging.getLogger(__name__)
        self.templates_dir = Path(templates_dir)
        self.logger.debug(f"Initializing EmailTemplateRenderer with templates_dir: {self.templates_dir}")
        
        # Verify templates directory exists
        if not self.templates_dir.exists():
            error_msg = f"Templates directory not found: {self.templates_dir}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Initialize Jinja environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True
        )
        
        # Load CSS file
        try:
            css_path = self.templates_dir / 'styles.css'
            self.logger.debug(f"Looking for CSS file at: {css_path}")
            
            if not css_path.exists():
                error_msg = f"CSS file not found at: {css_path}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
                
            with open(css_path, 'r', encoding='utf-8') as f:
                self.css_styles = f.read().strip()  # Added strip() to remove any extra whitespace
                # Log first few characters of CSS for verification
                self.logger.debug(f"CSS file loaded. First 100 characters: {self.css_styles[:100]}")
                self.logger.debug(f"CSS length: {len(self.css_styles)}")
                
        except Exception as e:
            self.logger.error(f"Error loading CSS file: {str(e)}")
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
                'quarters': self._format_quarterly_stats(stats.quarterly_totals)  # Changed 'items' to 'quarters'
            },
            {
                'title': 'Unassigned Revenue',
                'quarters': self._format_quarterly_stats(stats.unassigned_totals)  # Changed 'items' to 'quarters'
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
    
    def render_sales_report(self, ae_name: str, stats: SalesStats) -> str:
        """Render the sales report email template"""
        try:
            self.logger.debug(f"Starting template render for AE: {ae_name}")
            template = self.env.get_template('sales_report.html')
            current_year = datetime.now().year
            
            # Calculate formatted stats first
            overview_stats = self._format_overview_stats(stats)
            quarterly_cards = self._format_quarterly_cards(stats, current_year)
            
            # Add debug logging for CSS
            self.logger.debug(f"CSS preview before rendering: {self.css_styles[:100]}...")
            
            # Create context with pre-calculated values
            context = {
                'ae_name': ae_name,
                'current_year': current_year,
                'overview_stats': overview_stats,
                'quarterly_cards': quarterly_cards,
                'css_styles': self.css_styles
            }
            
            self.logger.debug("Template context:")
            for key, value in context.items():
                self.logger.debug(f"{key}: {value if key != 'css_styles' else f'length: {len(value)}'}")
            
            # Render template
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
        return f"${amount:,.2f}"