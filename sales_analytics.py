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

    def _format_currency(self, amount: float) -> str:
        """Format number as currency string with no decimal places
        
        Args:
            amount: Float value to format
            
        Returns:
            Formatted string with thousands separators
        """
        return f"{int(round(amount)):,}"
    
    @staticmethod
    def preprocess_management_stats(stats: ManagementStats):
        """
        Ensures all numerical values in management stats are correctly formatted as float or int
        before passing to the template to avoid type mismatches.
        """
        print(f"Before preprocessing: {stats.__dict__}")  # Debugging

        # Ensure all top-level stats are numeric
        stats.total_revenue = float(stats.total_revenue)
        stats.total_previous_year_revenue = float(stats.total_previous_year_revenue)
        stats.total_year_over_year_change = float(stats.total_year_over_year_change)
        stats.total_customers = int(stats.total_customers)
        stats.previous_year_customers = int(stats.previous_year_customers)
        stats.total_previous_year_revenue_raw = float(stats.total_previous_year_revenue)  # Add raw value

        # Ensure company_quarters data are numeric
        for quarter in stats.company_quarters:
            quarter["assigned"] = float(quarter.get("assigned", 0))
            quarter["unassigned"] = float(quarter.get("unassigned", 0))
            quarter["budget"] = float(quarter.get("budget", 0))
            quarter["completion_percentage"] = float(quarter.get("completion_percentage", 0))
            quarter["previous_year_assigned"] = float(quarter.get("previous_year_assigned", 0))
            quarter["previous_year_assigned_raw"] = float(quarter.get("previous_year_assigned", 0))  # Add raw value
            quarter["year_over_year_change"] = float(quarter.get("year_over_year_change", 0))
        
        # Ensure ae_data numbers are numeric
        if stats.ae_data:
            for ae in stats.ae_data:
                ae["total_assigned_revenue"] = float(ae.get("total_assigned_revenue", 0))
                ae["year_over_year_change"] = float(ae.get("year_over_year_change", 0))
                ae["total_customers"] = int(ae.get("total_customers", 0))
                ae["previous_year_customers"] = int(ae.get("previous_year_customers", 0))
                ae["total_budget"] = float(ae.get("total_budget", 0))
                ae["previous_year_revenue_raw"] = float(ae.get("previous_year_revenue", 0))  # Add raw value

        print(f"After preprocessing: {stats.__dict__}")  # Debugging

    def calculate_sales_stats(self, sales_data_df: pd.DataFrame, ae_name: str) -> SalesStats:
            """Calculate sales statistics for a specific account executive."""
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
            
            # Process quarterly data
            quarterly_data = []
            total_assigned = 0
            total_unassigned = 0
            total_previous_year = 0
            
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
                
                # Update totals
                total_assigned += assigned_revenue
                total_unassigned += unassigned_revenue
                total_previous_year += previous_assigned_revenue
                
                # Calculate completion percentage
                completion_percentage = (assigned_revenue / budget_value * 100) if budget_value > 0 else 0
                
                # Year over year calculations
                yoy_change = (
                    ((assigned_revenue - previous_assigned_revenue) / previous_assigned_revenue * 100)
                    if previous_assigned_revenue > 0
                    else 0
                )
                print(f"- Year over year change: {yoy_change}%")
                
                # Create QuarterData object
                quarterly_data.append(QuarterData(
                    name=f"Q{q} {current_year}",
                    assigned=assigned_revenue,
                    unassigned=unassigned_revenue,
                    budget=budget_value,
                    completion_percentage=completion_percentage,
                    previous_year_assigned=previous_assigned_revenue,
                    previous_year_unassigned=previous_unassigned_revenue,
                    year_over_year_change=yoy_change
                ))
            
            # Calculate customer counts
            current_customers = len(ae_data[
                (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
                (ae_data[current_quarters].sum(axis=1) > 0)
            ]['Customer'].unique())

            previous_customers = len(ae_data[
                (ae_data['Sector'] != 'AAA - UNASSIGNED') & 
                (ae_data[previous_quarters].sum(axis=1) > 0)
            ]['Customer'].unique())

            # Create quarterly and unassigned totals dictionaries
            quarterly_totals = {q: d.assigned for q, d in zip(current_quarters, quarterly_data)}
            unassigned_totals = {q: d.unassigned for q, d in zip(current_quarters, quarterly_data)}

            # Calculate per customer metrics
            avg_per_customer = total_assigned / current_customers if current_customers > 0 else 0

            # Calculate total year-over-year change
            total_yoy_change = (
                ((total_assigned - total_previous_year) / total_previous_year * 100)
                if total_previous_year > 0
                else 0
            )

            # Create and return SalesStats
            return SalesStats(
                total_customers=current_customers,
                total_assigned_revenue=total_assigned,
                total_unassigned_revenue=total_unassigned,
                quarterly_totals=quarterly_totals,
                avg_per_customer=avg_per_customer,
                unassigned_totals=unassigned_totals,
                quarterly_data=quarterly_data,
                previous_year_customers=previous_customers,
                total_previous_year_revenue=total_previous_year,
                total_year_over_year_change=total_yoy_change
            )

    def calculate_company_quarterly_data(self, df: pd.DataFrame) -> List[dict]:
        """Calculate quarterly data for the entire company."""
        # Setup year/quarter references
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]
        
        # Split data into assigned and unassigned
        assigned_data = df[df['Sector'] != 'AAA - UNASSIGNED']
        unassigned_data = df[df['Sector'] == 'AAA - UNASSIGNED']
        
        quarterly_data = []
        
        for q in range(1, 5):
            current_q = f"{current_year}Q{q}"
            previous_q = f"{previous_year}Q{q}"
            
            # Calculate quarterly totals
            assigned = assigned_data[current_q].sum()
            unassigned = unassigned_data[current_q].sum()
            previous_assigned = assigned_data[previous_q].sum()
            
            # Calculate budget for this quarter
            budget = sum(
                float(getattr(ae_config.budgets, f"q{q}"))
                for ae_config in self.config.account_executives.values()
                if ae_config.enabled
            )
            
            # Calculate completion percentage
            completion_percentage = (assigned / budget * 100) if budget > 0 else 0
            
            # Calculate year-over-year change
            yoy_change = (
                ((assigned - previous_assigned) / previous_assigned * 100)
                if previous_assigned > 0
                else 0
            )
            
            quarter_data = {
                'name': f"Q{q} {current_year}",
                'assigned': assigned,
                'unassigned': unassigned,
                'budget': budget,
                'completion_percentage': round(completion_percentage),
                'previous_year_assigned': previous_assigned,
                'previous_year_assigned_raw': previous_assigned,  # Add raw value for template
                'year_over_year_change': yoy_change
            }
            
            quarterly_data.append(quarter_data)
        
        return quarterly_data

    def calculate_management_stats(self, sales_data: pd.DataFrame) -> ManagementStats:
        """
        Calculate management-level statistics combining individual AE stats and company rollups.
        Returns both individual AE performance and company-wide statistics.
        """
        # Create a copy of the data and setup year/quarter references
        df = sales_data.copy()
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]

        # Split data into assigned and unassigned
        assigned_data = df[df['Sector'] != 'AAA - UNASSIGNED']
        unassigned_data = df[df['Sector'] == 'AAA - UNASSIGNED']

        # Calculate company-wide totals
        total_revenue = assigned_data[current_quarters].sum().sum()
        total_unassigned_revenue = unassigned_data[current_quarters].sum().sum()
        total_customers = len(assigned_data[assigned_data[current_quarters].sum(axis=1) > 0]['Customer'].unique())
        
        # Previous year totals
        total_previous_year_revenue = assigned_data[previous_quarters].sum().sum()
        total_previous_year_unassigned = unassigned_data[previous_quarters].sum().sum()
        previous_year_customers = len(assigned_data[assigned_data[previous_quarters].sum(axis=1) > 0]['Customer'].unique())

        # Calculate year-over-year change
        total_year_over_year_change = (
            ((total_revenue - total_previous_year_revenue) / total_previous_year_revenue * 100)
            if total_previous_year_revenue > 0
            else 0
        )

        # Calculate company quarterly data
        company_quarters = self.calculate_company_quarterly_data(sales_data)
        
        # Calculate total company budget
        company_total_budget = sum(
            sum(float(getattr(ae_config.budgets, f"q{q}")) for q in range(1, 5))
            for ae_config in self.config.account_executives.values()
            if ae_config.enabled
        )

        # Calculate company completion percentage
        company_completion_percentage = (
            (total_revenue / company_total_budget * 100) if company_total_budget > 0 else 0
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
                total_budget = 0
                
                for q in range(1, 5):
                    quarter_col = f"{current_year}Q{q}"
                    previous_quarter = f"{previous_year}Q{q}"
                    budget_value = float(getattr(ae_config.budgets, f'q{q}'))
                    total_budget += budget_value
                    
                    # Get current and previous data for this quarter
                    current_data = next(
                        (qd for qd in ae_stats.quarterly_data if qd.name == f"Q{q} {current_year}"),
                        None
                    )
                    
                    if current_data:
                        # Calculate previous year assigned raw value
                        previous_year_assigned_raw = current_data.previous_year_assigned
                        if isinstance(current_data.previous_year_assigned, str):
                            previous_year_assigned_raw = float(
                                current_data.previous_year_assigned.replace('$', '').replace(',', '')
                            )
                        
                        # Create quarter data
                        quarter_data = {
                            'name': f"Q{q}",
                            'assigned': current_data.assigned,
                            'unassigned': current_data.unassigned,
                            'budget': budget_value,
                            'completion_percentage': round((current_data.assigned / budget_value * 100) if budget_value > 0 else 0),
                            'previous_year_assigned': current_data.previous_year_assigned,
                            'previous_year_unassigned': current_data.previous_year_unassigned,
                            'year_over_year_change': current_data.year_over_year_change,
                            'previous_year_assigned_raw': previous_year_assigned_raw
                        }
                        ae_quarters.append(quarter_data)

                # Calculate annual totals
                annual_completion_percentage = (
                    (ae_stats.total_assigned_revenue / total_budget * 100) 
                    if total_budget > 0 else 0
                )
                
                annual_totals = {
                    'name': 'Annual Total',
                    'assigned': ae_stats.total_assigned_revenue,
                    'unassigned': ae_stats.total_unassigned_revenue,
                    'budget': total_budget,
                    'completion_percentage': round(annual_completion_percentage),
                    'year_over_year_change': ae_stats.total_year_over_year_change
                }

                # Calculate raw previous year revenue
                previous_year_revenue_raw = ae_stats.total_previous_year_revenue
                if isinstance(previous_year_revenue_raw, str):
                    previous_year_revenue_raw = float(
                        previous_year_revenue_raw.replace('$', '').replace(',', '')
                    )

                # Create AE data entry
                ae_entry = {
                    'name': ae_name,
                    'total_assigned_revenue': ae_stats.total_assigned_revenue,
                    'total_customers': ae_stats.total_customers,
                    'quarters': ae_quarters,
                    'previous_year_revenue': ae_stats.total_previous_year_revenue,
                    'previous_year_revenue_raw': previous_year_revenue_raw,
                    'previous_year_customers': ae_stats.previous_year_customers,
                    'year_over_year_change': ae_stats.total_year_over_year_change,
                    'total_budget': total_budget,
                    'annual_totals': annual_totals
                }
                
                ae_data.append(ae_entry)

            except Exception as e:
                print(f"Error processing AE {ae_name}: {str(e)}")
                continue

        # Sort AE data by total revenue
        ae_data.sort(key=lambda x: x['total_assigned_revenue'], reverse=True)

        # Return final management stats
        return ManagementStats(
            total_revenue=total_revenue,
            total_unassigned_revenue=total_unassigned_revenue,
            total_customers=total_customers,
            ae_data=ae_data,
            total_previous_year_revenue=total_previous_year_revenue,
            total_previous_year_unassigned=total_previous_year_unassigned,
            total_year_over_year_change=total_year_over_year_change,
            previous_year_customers=previous_year_customers,
            company_quarters=company_quarters,
            company_total_budget=company_total_budget,
            company_completion_percentage=round(company_completion_percentage)
        )

    def validate_management_stats(stats: ManagementStats) -> bool:
        """
        Validate that a ManagementStats object has all required fields with correct types
        """
        if not isinstance(stats, ManagementStats):
            raise TypeError(f"Expected ManagementStats, got {type(stats).__name__}")
            
        required_float_fields = [
            'total_revenue',
            'total_unassigned_revenue',
            'total_previous_year_revenue',
            'total_year_over_year_change',
            'company_total_budget',
            'company_completion_percentage'
        ]
        
        required_int_fields = [
            'total_customers',
            'previous_year_customers'
        ]
        
        # Validate float fields
        for field in required_float_fields:
            value = getattr(stats, field)
            if not isinstance(value, (int, float)):
                setattr(stats, field, float(value))
        
        # Validate int fields
        for field in required_int_fields:
            value = getattr(stats, field)
            if not isinstance(value, int):
                setattr(stats, field, int(float(value)))
        
        # Validate company_quarters
        if not isinstance(stats.company_quarters, list):
            raise TypeError("company_quarters must be a list")
            
        for quarter in stats.company_quarters:
            if not isinstance(quarter, dict):
                raise TypeError("Each quarter in company_quarters must be a dictionary")
                
            required_quarter_fields = [
                'assigned',
                'unassigned',
                'budget',
                'completion_percentage',
                'previous_year_assigned',
                'year_over_year_change'
            ]
            
            for field in required_quarter_fields:
                if field not in quarter:
                    quarter[field] = 0.0
                elif not isinstance(quarter[field], (int, float)):
                    quarter[field] = float(quarter[field])
        
        return True

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