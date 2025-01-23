from pathlib import Path
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
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

@dataclass
class SalesStats:
    """Container for sales statistics"""
    total_customers: int
    total_assigned_revenue: float
    quarterly_totals: Dict[str, float]
    avg_per_customer: float
    unassigned_totals: Dict[str, float]
    quarterly_data: List[QuarterData]

@dataclass
class ManagementStats:
    """Container for management rollup statistics"""
    total_revenue: float
    total_unassigned_revenue: float
    total_customers: int
    ae_data: List[Dict]

class EmailTemplateRenderer:
    """Handles email template rendering with enhanced budget visualization"""

    def __init__(self, templates_dir: Path):
        """Initialize the template renderer with the specified templates directory
        
        Args:
            templates_dir: Path to the directory containing email templates
            
        Raises:
            ValueError: If templates directory doesn't exist
        """
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
    
    def _load_css(self) -> None:
        """Load CSS styles from the templates directory
        
        Raises:
            FileNotFoundError: If CSS file is not found
            Exception: For other loading errors
        """
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

    def _load_logo(self) -> None:
        """Load and encode company logo as base64
        
        Raises:
            Exception: For logo loading or encoding errors
        """
        try:
            logo_path = self.templates_dir / 'logo.png'
            self.logger.debug(f"Looking for logo at: {logo_path}")
            
            if not logo_path.exists():
                self.logger.warning(f"Logo file not found at: {logo_path}")
                return
                
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
                self.logo_base64 = f"data:image/png;base64,{base64.b64encode(logo_data).decode('utf-8')}"
                self.logger.debug(f"Logo loaded successfully, base64 length: {len(self.logo_base64)}")
                    
        except Exception as e:
            self.logger.error(f"Error loading logo file: {str(e)}")
            raise

    def _format_budget_data(self, quarterly_data: List[QuarterData]) -> List[Dict]:
        """Format quarterly budget data for template rendering
        
        Args:
            quarterly_data: List of QuarterData objects containing performance metrics
            
        Returns:
            List of dictionaries with formatted data for template rendering
        """
        return [{
            'name': q.name,
            'assigned': self._format_currency(q.assigned),
            'unassigned': self._format_currency(q.unassigned),
            'budget': self._format_currency(q.budget),
            'completion_percentage': round(q.completion_percentage),
            'bar_width': f"{round(q.completion_percentage)}%"
        } for q in quarterly_data]

    def _calculate_totals(self, quarterly_data: List[QuarterData]) -> Dict:
        """Calculate total values across all quarters
        
        Args:
            quarterly_data: List of QuarterData objects to total
            
        Returns:
            Dictionary containing formatted totals and overall completion percentage
        """
        total_assigned = sum(q.assigned for q in quarterly_data)
        total_unassigned = sum(q.unassigned for q in quarterly_data)
        total_budget = sum(q.budget for q in quarterly_data)
        total_percentage = (total_assigned / total_budget * 100) if total_budget > 0 else 0
        
        return {
            'assigned': self._format_currency(total_assigned),
            'unassigned': self._format_currency(total_unassigned),
            'budget': self._format_currency(total_budget),
            'completion_percentage': round(total_percentage),
            'bar_width': f"{round(total_percentage)}%"
        }
    
    def _format_ae_data(self, ae_data: List[Dict]) -> List[Dict]:
        """Format AE data for management report template"""
        formatted_data = []
        for ae in ae_data:
            # Calculate totals for each AE
            total_budget = sum(quarter['budget'] for quarter in ae['quarters'])
            total_unassigned = sum(quarter['unassigned'] for quarter in ae['quarters'])
            total_completion_percentage = round((ae['total_assigned_revenue'] / total_budget * 100) if total_budget > 0 else 0)
            avg_per_customer = round(ae['total_assigned_revenue'] / ae['total_customers']) if ae['total_customers'] > 0 else 0

            formatted_ae = {
                'name': ae['name'],
                'total_assigned_revenue': self._format_currency(ae['total_assigned_revenue']),
                'total_customers': ae['total_customers'],
                'avg_per_customer': self._format_currency(avg_per_customer),
                'total_unassigned': self._format_currency(total_unassigned),
                'total_budget': self._format_currency(total_budget),
                'total_completion_percentage': total_completion_percentage,
                'quarters': [
                    {
                        'name': quarter['name'],
                        'assigned': self._format_currency(quarter['assigned']),
                        'unassigned': self._format_currency(quarter['unassigned']),
                        'budget': self._format_currency(quarter['budget']),
                        'completion_percentage': round((quarter['assigned'] / quarter['budget'] * 100) if quarter['budget'] > 0 else 0)
                    }
                    for quarter in ae['quarters']
                ]
            }
            formatted_data.append(formatted_ae)
        return formatted_data

    def render_sales_report(self, ae_name: str, stats: SalesStats) -> str:
        """Render the sales report email template with enhanced budget visualization
        
        Args:
            ae_name: Name of the Account Executive
            stats: SalesStats object containing performance metrics
            
        Returns:
            Rendered HTML content as string
            
        Raises:
            Exception: For template rendering errors
        """
        try:
            self.logger.debug(f"Starting template render for AE: {ae_name}")
            template = self.env.get_template('sales_report.html')
            
            # Format quarterly data and calculate totals
            formatted_quarters = self._format_budget_data(stats.quarterly_data)
            totals = self._calculate_totals(stats.quarterly_data)
            
            context = {
                'ae_name': ae_name,
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'quarters': formatted_quarters,
                'totals': totals,
                'overview_stats': {
                    'total_customers': stats.total_customers,
                    'total_assigned': self._format_currency(stats.total_assigned_revenue),
                    'avg_per_customer': self._format_currency(stats.avg_per_customer)
                },
                'css_styles': self.css_styles,
                'logo_base64': self.logo_base64
            }
            
            return template.render(**context)
                
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
    
    def render_management_report(self, stats: ManagementStats) -> str:
        """Render the management rollup report template"""
        try:
            template = self.env.get_template('management_report.html')
            
            # Add debug logging
            self.logger.debug(f"AE Data being passed to template: {stats.ae_data}")
            
            context = {
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'total_revenue': self._format_currency(stats.total_revenue),
                'total_unassigned_revenue': self._format_currency(stats.total_unassigned_revenue),
                'total_customers': stats.total_customers,
                'ae_data': self._format_ae_data(stats.ae_data),  # Make sure this contains the expected data
                'logo_base64': self.logo_base64
            }
            
            self.logger.debug(f"Formatted AE Data: {context['ae_data']}")
            
            return template.render(**context)
            
        except Exception as e:
            self.logger.error(f"Error rendering management template: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    @staticmethod
    def _format_currency(amount: float) -> str:
        """Format number as currency string with no decimal places
        
        Args:
            amount: Float value to format
            
        Returns:
            Formatted string with thousands separators
        """
        return f"{int(round(amount)):,}"