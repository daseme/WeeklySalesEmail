from turtle import st
from typing import Dict, List
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
from email_sender import ManagementStats


@dataclass
class SalesStats:
    """Container for sales statistics"""

    total_customers: int
    total_assigned_revenue: float
    quarterly_totals: Dict[str, float]
    avg_per_customer: float
    unassigned_totals: Dict[str, float]


class SalesAnalytics:
    """Handles sales data analysis"""

    @staticmethod
    def calculate_sales_stats(sales_data_df: pd.DataFrame, ae_name: str) -> SalesStats:
        """
        Calculate sales statistics for an AE

        Args:
            sales_data_df: DataFrame containing sales data
            ae_name: Name of the Account Executive

        Returns:
            SalesStats object with calculated statistics
        """
        # Get current year for dynamic quarter columns
        current_year = datetime.now().year
        year_prefix = str(current_year)[
            2:
        ]  # Get last two digits e.g., "24" from "2024"

        # Get AE's data
        ae_data = sales_data_df[sales_data_df.AE1 == ae_name]

        # Calculate quarterly totals for assigned revenue
        quarterly_totals = {
            f"{year_prefix}Q{q}": ae_data[
                (ae_data[f"{year_prefix}Q{q}"] > 0)
                & (ae_data["Sector"] != "AAA - UNASSIGNED")
            ][f"{year_prefix}Q{q}"].sum()
            for q in range(1, 5)
        }

        # Calculate quarterly totals for unassigned revenue
        unassigned_totals = {
            f"{year_prefix}Q{q}": ae_data[
                (ae_data[f"{year_prefix}Q{q}"] > 0)
                & (ae_data["Sector"] == "AAA - UNASSIGNED")
            ][f"{year_prefix}Q{q}"].sum()
            for q in range(1, 5)
        }

        # Calculate other stats (excluding unassigned revenue)
        assigned_data = ae_data[ae_data["Sector"] != "AAA - UNASSIGNED"]
        total_customers = len(assigned_data.Customer.unique())
        total_assigned_revenue = sum(quarterly_totals.values())
        avg_per_customer = (
            total_assigned_revenue / total_customers if total_customers > 0 else 0
        )

        return SalesStats(
            total_customers=total_customers,
            total_assigned_revenue=total_assigned_revenue,
            quarterly_totals=quarterly_totals,
            avg_per_customer=avg_per_customer,
            unassigned_totals=unassigned_totals,
        )

    @dataclass
    class ManagementStats:
        """Container for management rollup statistics"""
        total_revenue: float
        total_customers: int
        ae_data: List[Dict]

    def calculate_management_stats(self, sales_data: pd.DataFrame) -> ManagementStats:
        """Calculate management level statistics"""
        # Get current year for dynamic quarter columns
        current_year = datetime.now().year
        year_prefix = str(current_year)[2:]  
        quarter_columns = [f"{year_prefix}Q{q}" for q in range(1, 5)]
        
        total_revenue = sales_data[sales_data['Sector'] != 'AAA - UNASSIGNED'][quarter_columns].sum().sum()
        total_customers = len(sales_data['Customer'].unique())
        
        ae_data = []
        for ae_name in sales_data['AE1'].unique():
            ae_stats = self.calculate_sales_stats(sales_data, ae_name)
            ae_quarters = []
            for q in range(1, 5):
                quarter = {
                    'name': f'Q{q}',
                    'assigned': ae_stats.quarterly_totals[f'{year_prefix}Q{q}'],
                    'unassigned': ae_stats.unassigned_totals[f'{year_prefix}Q{q}']
                }
                ae_quarters.append(quarter)
                
            ae_data.append({
                'name': ae_name,
                'total_assigned_revenue': ae_stats.total_assigned_revenue,
                'total_customers': ae_stats.total_customers,
                'quarters': ae_quarters
            })
        
        return ManagementStats(
            total_revenue=total_revenue,
            total_customers=total_customers,
            ae_data=ae_data
        )

    @staticmethod
    def validate_data(sales_data_df: pd.DataFrame) -> None:
        """
        Validate the sales data DataFrame structure and content

        Args:
            sales_data_df: DataFrame to validate

        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        current_year = datetime.now().year
        year_prefix = str(current_year)[2:]

        # Required columns
        required_columns = ["AE1", "Customer", "Sector"]
        quarter_columns = [f"{year_prefix}Q{q}" for q in range(1, 5)]
        all_required = required_columns + quarter_columns

        # Check for missing columns
        missing_columns = [
            col for col in all_required if col not in sales_data_df.columns
        ]
        if missing_columns:
            raise ValueError(
                f"Missing required columns in sales data: {', '.join(missing_columns)}"
            )

        # Validate numeric columns (quarters)
        for col in quarter_columns:
            if not pd.api.types.is_numeric_dtype(sales_data_df[col]):
                raise ValueError(f"Column {col} must contain numeric values")

        # Validate non-empty AE1 and Customer columns
        if sales_data_df["AE1"].isna().any():
            raise ValueError("Found missing values in AE1 column")
        if sales_data_df["Customer"].isna().any():
            raise ValueError("Found missing values in Customer column")
