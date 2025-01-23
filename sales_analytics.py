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
        print(f"\n=== Processing Stats for {ae_name} ===")
        
        # Verify AE is enabled and get config
        ae_config = self.config.account_executives.get(ae_name)
        if not ae_config or not ae_config.enabled:
            raise ValueError(f"AE {ae_name} is not enabled or doesn't exist")
        
        # Get AE's data and ensure numeric values
        ae_data = sales_data_df[sales_data_df.AE1 == ae_name].copy()
        
        # Calculate current and previous year column names
        current_year = str(datetime.now().year)[2:]  # "25"
        previous_year = str(int(current_year) - 1)   # "24"
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]
        
        print("\nLooking for quarters:")
        print(f"Current quarters: {current_quarters}")
        print(f"Previous quarters: {previous_quarters}")
        print(f"Available columns: {ae_data.columns.tolist()}")
        
        quarterly_data = []
        for q in range(1, 5):
            current_quarter = f"{current_year}Q{q}"
            previous_quarter = f"{previous_year}Q{q}"
            budget_value = float(getattr(ae_config.budgets, f'q{q}'))
            
            print(f"\nProcessing Q{q}:")
            print(f"- Looking for current: {current_quarter}")
            print(f"- Looking for previous: {previous_quarter}")
            
            # Current year calculations
            assigned_revenue = ae_data[
                (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
                (ae_data[current_quarter] > 0)
            ][current_quarter].sum()
            
            unassigned_revenue = ae_data[
                (ae_data['Sector'] == 'AAA - UNASSIGNED') & 
                (ae_data[current_quarter] > 0)
            ][current_quarter].sum()
            
            # Previous year calculations
            previous_assigned_revenue = ae_data[
                (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
                (ae_data[previous_quarter] > 0)
            ][previous_quarter].sum()
            
            previous_unassigned_revenue = ae_data[
                (ae_data['Sector'] == 'AAA - UNASSIGNED') & 
                (ae_data[previous_quarter] > 0)
            ][previous_quarter].sum()
            
            print(f"- Current quarter revenue: {assigned_revenue}")
            print(f"- Current quarter unassigned: {unassigned_revenue}")
            print(f"- Previous quarter revenue: {previous_assigned_revenue}")
            print(f"- Previous quarter unassigned: {previous_unassigned_revenue}")
            
            # Year over year calculations
            yoy_change = (
                ((assigned_revenue - previous_assigned_revenue) / previous_assigned_revenue * 100)
                if previous_assigned_revenue > 0
                else 0
            )
            print(f"- Year over year change: {yoy_change}%")
            
            quarterly_data.append(QuarterData(
                name=f"Q{q} {current_year}",
                assigned=assigned_revenue,
                unassigned=unassigned_revenue,
                budget=budget_value,
                completion_percentage=(assigned_revenue / budget_value * 100) if budget_value > 0 else 0,
                previous_year_assigned=previous_assigned_revenue,
                previous_year_unassigned=previous_unassigned_revenue,
                year_over_year_change=yoy_change
            ))

        # Calculate totals and return stats
        total_assigned = sum(q.assigned for q in quarterly_data)
        total_unassigned = sum(q.unassigned for q in quarterly_data)
        total_previous_year = sum(q.previous_year_assigned for q in quarterly_data)
        
        # Calculate customer counts
        current_customers = len(ae_data[
            (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
            (ae_data[current_quarters].sum(axis=1) > 0)
        ]['Customer'].unique())

        previous_customers = len(ae_data[
            (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
            (ae_data[previous_quarters].sum(axis=1) > 0)
        ]['Customer'].unique())

        return SalesStats(
            total_customers=current_customers,
            total_assigned_revenue=total_assigned,
            quarterly_totals={q: d.assigned for q, d in zip(current_quarters, quarterly_data)},
            avg_per_customer=total_assigned / current_customers if current_customers > 0 else 0,
            unassigned_totals={q: d.unassigned for q, d in zip(current_quarters, quarterly_data)},
            quarterly_data=quarterly_data,
            previous_year_customers=previous_customers,
            total_previous_year_revenue=total_previous_year,
            total_year_over_year_change=((total_assigned - total_previous_year) / total_previous_year * 100) if total_previous_year > 0 else 0
        )

    def calculate_management_stats(self, sales_data: pd.DataFrame) -> ManagementStats:
        """Calculate management level statistics"""
        # Create a copy of the data and ensure numeric values
        df = sales_data.copy()
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]

        # Calculate this year's totals
        assigned_data = df[df['Sector'] != 'AAA - UNASSIGNED']
        unassigned_data = df[df['Sector'] == 'AAA - UNASSIGNED']

        total_revenue = assigned_data[current_quarters].sum().sum()
        total_unassigned_revenue = unassigned_data[current_quarters].sum().sum()
        total_customers = len(assigned_data[assigned_data[current_quarters].sum(axis=1) > 0]['Customer'].unique())

        # Calculate previous year's totals
        total_previous_year_revenue = assigned_data[previous_quarters].sum().sum()
        total_previous_year_unassigned = unassigned_data[previous_quarters].sum().sum()
        previous_year_customers = len(assigned_data[assigned_data[previous_quarters].sum(axis=1) > 0]['Customer'].unique())

        # Calculate year-over-year change
        total_year_over_year_change = (
            ((total_revenue - total_previous_year_revenue) / total_previous_year_revenue * 100)
            if total_previous_year_revenue > 0
            else 0
        )

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
                    quarter_col = f"{current_year}Q{q}"
                    previous_quarter = f"{previous_year}Q{q}"
                    budget_value = float(getattr(ae_config.budgets, f'q{q}'))
                    
                    # Get current and previous data for this quarter
                    current_data = next(
                        (qd for qd in ae_stats.quarterly_data if qd.name == f"Q{q} {current_year}"),
                        None
                    )
                    
                    if current_data:
                        ae_quarters.append({
                            'name': f"Q{q}",
                            'assigned': current_data.assigned,
                            'unassigned': current_data.unassigned,
                            'budget': budget_value,
                            'completion_percentage': round((current_data.assigned / budget_value * 100) if budget_value > 0 else 0),
                            'previous_year_assigned': current_data.previous_year_assigned,
                            'previous_year_unassigned': current_data.previous_year_unassigned,
                            'year_over_year_change': current_data.year_over_year_change
                        })

                # Add AE's data to the list
                ae_data.append({
                    'name': ae_name,
                    'total_assigned_revenue': ae_stats.total_assigned_revenue,
                    'total_customers': ae_stats.total_customers,
                    'quarters': ae_quarters,
                    'previous_year_revenue': ae_stats.total_previous_year_revenue,
                    'previous_year_customers': ae_stats.previous_year_customers,
                    'year_over_year_change': ae_stats.total_year_over_year_change
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
            ae_data=ae_data,
            total_previous_year_revenue=total_previous_year_revenue,
            total_previous_year_unassigned=total_previous_year_unassigned,
            total_year_over_year_change=total_year_over_year_change,
            previous_year_customers=previous_year_customers
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