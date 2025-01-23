from typing import Dict, List
import pandas as pd
from datetime import datetime
from config import Config
# Import the data structures directly from email_template_renderer
from email_template_renderer import QuarterData, SalesStats, ManagementStats

class SalesAnalytics:
    """Handles sales data analysis"""

    def __init__(self, config: Config):
        """Initialize with configuration"""
        self.config = config
        self.current_year = str(datetime.now().year)[2:]
        self.quarter_columns = [f"{self.current_year}Q{q}" for q in range(1, 5)]

    def calculate_sales_stats(self, sales_data_df: pd.DataFrame, ae_name: str) -> SalesStats:
        """Calculate enhanced sales statistics for an AE"""
        # Verify AE is enabled
        ae_config = self.config.account_executives.get(ae_name)
        if not ae_config or not ae_config.enabled:
            raise ValueError(f"AE {ae_name} is not enabled or doesn't exist")
        
        # Get AE's data and ensure numeric values
        ae_data = sales_data_df[sales_data_df.AE1 == ae_name].copy()
        for col in self.quarter_columns:
            ae_data[col] = pd.to_numeric(ae_data[col], errors='coerce').fillna(0)

        # Calculate quarterly data
        quarterly_data = []
        total_assigned = 0
        total_unassigned = 0
        total_budget = 0

        quarterly_totals = {}
        unassigned_totals = {}

        for q in range(1, 5):
            quarter_col = f"{self.current_year}Q{q}"
            budget_value = float(getattr(ae_config.budgets, f'q{q}'))
            
            # Calculate assigned and unassigned revenue
            assigned_revenue = ae_data[
                (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
                (ae_data[quarter_col] > 0)
            ][quarter_col].sum()
            
            unassigned_revenue = ae_data[
                (ae_data['Sector'] == 'AAA - UNASSIGNED') & 
                (ae_data[quarter_col] > 0)
            ][quarter_col].sum()

            # Calculate completion percentage
            completion_percentage = (assigned_revenue / budget_value * 100) if budget_value > 0 else 0

            quarterly_data.append(QuarterData(
                name=f"Q{q} {self.current_year}",
                assigned=assigned_revenue,
                unassigned=unassigned_revenue,
                budget=budget_value,
                completion_percentage=completion_percentage
            ))

            # Update totals
            total_assigned += assigned_revenue
            total_unassigned += unassigned_revenue
            total_budget += budget_value
            
            # Store quarterly values for the old format
            quarterly_totals[quarter_col] = assigned_revenue
            unassigned_totals[quarter_col] = unassigned_revenue

        # Calculate customer stats
        total_customers = len(ae_data[
            (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
            (ae_data[self.quarter_columns].sum(axis=1) > 0)
        ]['Customer'].unique())

        avg_per_customer = total_assigned / total_customers if total_customers > 0 else 0

        return SalesStats(
            total_customers=total_customers,
            total_assigned_revenue=total_assigned,
            quarterly_totals=quarterly_totals,
            avg_per_customer=avg_per_customer,
            unassigned_totals=unassigned_totals,
            quarterly_data=quarterly_data
        )

    def calculate_management_stats(self, sales_data: pd.DataFrame) -> ManagementStats:
        """Calculate management level statistics"""
        # Create a copy of the data and ensure numeric values
        df = sales_data.copy()
        for col in self.quarter_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Calculate overall totals
        assigned_data = df[df['Sector'] != 'AAA - UNASSIGNED']
        unassigned_data = df[df['Sector'] == 'AAA - UNASSIGNED']

        total_revenue = assigned_data[self.quarter_columns].sum().sum()
        total_unassigned_revenue = unassigned_data[self.quarter_columns].sum().sum()
        total_customers = len(assigned_data['Customer'].unique())

        # Process individual AE data
        ae_data = []
        for ae_name, ae_config in self.config.account_executives.items():
            if not ae_config.enabled:
                continue

            try:
                # Get stats for this AE
                ae_stats = self.calculate_sales_stats(df, ae_name)
                
                # Process quarterly data
                ae_quarters = []
                for q in range(1, 5):
                    quarter_col = f"{self.current_year}Q{q}"
                    budget_value = float(getattr(ae_config.budgets, f'q{q}'))
                    
                    # Find the matching quarter data
                    quarter_stats = next(
                        (qd for qd in ae_stats.quarterly_data if qd.name == f"Q{q} {self.current_year}"),
                        None
                    )
                    
                    if quarter_stats:
                        ae_quarters.append({
                            'name': f"Q{q}",
                            'assigned': quarter_stats.assigned,
                            'unassigned': quarter_stats.unassigned,
                            'budget': budget_value,
                            'completion_percentage': round((quarter_stats.assigned / budget_value * 100) if budget_value > 0 else 0)
                        })
                    else:
                        # Fallback if quarter not found
                        ae_quarters.append({
                            'name': f"Q{q}",
                            'assigned': 0,
                            'unassigned': 0,
                            'budget': budget_value,
                            'completion_percentage': 0
                        })

                # Add AE's data to the list
                ae_data.append({
                    'name': ae_name,
                    'total_assigned_revenue': ae_stats.total_assigned_revenue,
                    'total_customers': ae_stats.total_customers,
                    'quarters': ae_quarters
                })

            except Exception as e:
                print(f"Error processing AE {ae_name}: {str(e)}")
                continue

        # Sort AE data by total revenue
        ae_data.sort(key=lambda x: x['total_assigned_revenue'], reverse=True)

        return ManagementStats(
            total_revenue=total_revenue,
            total_unassigned_revenue=total_unassigned_revenue,
            total_customers=total_customers,
            ae_data=ae_data
        )

    def validate_data(self, sales_data_df: pd.DataFrame) -> None:
        """
        Validate the sales data DataFrame structure and content

        Args:
            sales_data_df: DataFrame to validate

        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        # Required columns
        required_columns = ["AE1", "Customer", "Sector"] + self.quarter_columns

        # Check for missing columns
        missing_columns = [col for col in required_columns if col not in sales_data_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns in sales data: {', '.join(missing_columns)}")

        # Validate numeric columns (quarters)
        for col in self.quarter_columns:
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

        # Validate AE names against configuration
        valid_aes = {name.lower() for name, ae in self.config.account_executives.items() if ae.enabled}
        actual_aes = {ae.lower() for ae in sales_data_df["AE1"].unique() if pd.notna(ae)}
        invalid_aes = actual_aes - valid_aes
        
        if invalid_aes:
            raise ValueError(f"Found unauthorized AEs in data: {', '.join(invalid_aes)}")