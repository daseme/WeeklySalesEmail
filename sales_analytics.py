from typing import Dict, List
from dataclasses import dataclass
import pandas as pd
from datetime import datetime


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
        current_year = str(datetime.now().year)[2:]
        quarter_columns = [f"{current_year}Q{q}" for q in range(1, 5)]
        
        # Get AE's data and ensure numeric values
        ae_data = sales_data_df[sales_data_df.AE1 == ae_name].copy()
        for col in quarter_columns:
            ae_data[col] = pd.to_numeric(ae_data[col], errors='coerce').fillna(0)

        # Calculate quarterly totals for assigned revenue
        assigned_data = ae_data[ae_data['Sector'] != 'AAA - UNASSIGNED']
        quarterly_totals = {
            col: assigned_data[col].sum()
            for col in quarter_columns
        }

        # Calculate quarterly totals for unassigned revenue
        unassigned_data = ae_data[ae_data['Sector'] == 'AAA - UNASSIGNED']
        unassigned_totals = {
            col: unassigned_data[col].sum()
            for col in quarter_columns
        }

        # Calculate other stats
        total_customers = len(assigned_data['Customer'].unique())
        total_assigned_revenue = sum(quarterly_totals.values())
        avg_per_customer = total_assigned_revenue / total_customers if total_customers > 0 else 0

        return SalesStats(
            total_customers=total_customers,
            total_assigned_revenue=total_assigned_revenue,
            quarterly_totals=quarterly_totals,
            avg_per_customer=avg_per_customer,
            unassigned_totals=unassigned_totals
        )

    def calculate_management_stats(self, sales_data: pd.DataFrame) -> ManagementStats:
        """
        Calculate management level statistics

        Args:
            sales_data: DataFrame containing all sales data

        Returns:
            ManagementStats object with calculated statistics
        """
        # Get current year for dynamic quarter columns
        current_year = str(datetime.now().year)[2:]
        quarter_columns = [f"{current_year}Q{q}" for q in range(1, 5)]
        
        # Create a copy of the data and ensure numeric values
        df = sales_data.copy()
        for col in quarter_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Split data into assigned and unassigned
        assigned_data = df[df['Sector'] != 'AAA - UNASSIGNED']
        unassigned_data = df[df['Sector'] == 'AAA - UNASSIGNED']

        # Calculate totals
        total_revenue = assigned_data[quarter_columns].sum().sum()
        total_unassigned_revenue = unassigned_data[quarter_columns].sum().sum()
        total_customers = len(assigned_data['Customer'].unique())

        # Process individual AE data
        ae_data = []
        for ae_name in df['AE1'].unique():
            if not ae_name:  # Skip empty AE names
                continue
                
            ae_stats = self.calculate_sales_stats(df, ae_name)
            ae_quarters = [
                {
                    'name': f'Q{q}',
                    'assigned': ae_stats.quarterly_totals[f'{current_year}Q{q}'],
                    'unassigned': ae_stats.unassigned_totals[f'{current_year}Q{q}']
                }
                for q in range(1, 5)
            ]

            ae_data.append({
                'name': ae_name,
                'total_assigned_revenue': ae_stats.total_assigned_revenue,
                'total_customers': ae_stats.total_customers,
                'quarters': ae_quarters
            })

        # Sort AE data by total revenue
        ae_data.sort(key=lambda x: x['total_assigned_revenue'], reverse=True)

        return ManagementStats(
            total_revenue=total_revenue,
            total_unassigned_revenue=total_unassigned_revenue,
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
        current_year = str(datetime.now().year)[2:]
        
        # Required columns
        required_columns = ["AE1", "Customer", "Sector"]
        quarter_columns = [f"{current_year}Q{q}" for q in range(1, 5)]
        all_required = required_columns + quarter_columns

        # Check for missing columns
        missing_columns = [col for col in all_required if col not in sales_data_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in sales data: {', '.join(missing_columns)}")

        # Validate numeric columns (quarters)
        for col in quarter_columns:
            try:
                pd.to_numeric(sales_data_df[col], errors='raise')
            except (ValueError, TypeError):
                raise ValueError(f"Column {col} must contain numeric values")

        # Validate required string columns
        if sales_data_df["Customer"].isna().any():
            raise ValueError("Found missing values in Customer column")
            
        # Validate sector values
        if not all(sales_data_df["Sector"].isin(['AAA - UNASSIGNED']) | (sales_data_df["Sector"] != 'AAA - UNASSIGNED')):
            raise ValueError("Invalid values found in Sector column")