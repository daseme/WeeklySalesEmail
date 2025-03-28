from typing import List
import pandas as pd
from datetime import datetime
from config import Config
import logging

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
        stats.total_previous_year_revenue_raw = float(
            stats.total_previous_year_revenue
        )  # Add raw value

        # Ensure company_quarters data are numeric
        for quarter in stats.company_quarters:
            quarter["assigned"] = float(quarter.get("assigned", 0))
            quarter["unassigned"] = float(quarter.get("unassigned", 0))
            quarter["budget"] = float(quarter.get("budget", 0))
            quarter["completion_percentage"] = float(
                quarter.get("completion_percentage", 0)
            )
            quarter["previous_year_assigned"] = float(
                quarter.get("previous_year_assigned", 0)
            )
            quarter["previous_year_assigned_raw"] = float(
                quarter.get("previous_year_assigned", 0)
            )  # Add raw value
            quarter["year_over_year_change"] = float(
                quarter.get("year_over_year_change", 0)
            )

        # Ensure ae_data numbers are numeric
        if stats.ae_data:
            for ae in stats.ae_data:
                ae["total_assigned_revenue"] = float(
                    ae.get("total_assigned_revenue", 0)
                )
                ae["year_over_year_change"] = float(ae.get("year_over_year_change", 0))
                ae["total_customers"] = int(ae.get("total_customers", 0))
                ae["previous_year_customers"] = int(
                    ae.get("previous_year_customers", 0)
                )
                ae["total_budget"] = float(ae.get("total_budget", 0))
                ae["previous_year_revenue_raw"] = float(
                    ae.get("previous_year_revenue", 0)
                )  # Add raw value

        print(f"After preprocessing: {stats.__dict__}")  # Debugging

    def calculate_sales_stats(
        self, sales_data_df: pd.DataFrame, ae_name: str
    ) -> SalesStats:
        """Calculate sales statistics for a specific account executive."""
        logger = logging.getLogger(__name__)
        logger.debug(f"=== Processing Stats for {ae_name} ===")

        # Verify AE is enabled and get config
        ae_config = self.config.account_executives.get(ae_name)
        if not ae_config or not ae_config.enabled:
            raise ValueError(f"AE {ae_name} is not enabled or doesn't exist")

        # Get AE's data and ensure numeric values
        ae_data = sales_data_df[sales_data_df.AE1 == ae_name].copy()

        # Calculate current and previous year column names
        current_year = str(datetime.now().year)[2:]  # e.g., "25"
        previous_year = str(int(current_year) - 1)  # e.g., "24"
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]

        # Process quarterly data
        quarterly_data = []
        total_assigned = 0
        total_unassigned = 0
        total_previous_year = 0

        for q in range(1, 5):
            current_quarter = f"{current_year}Q{q}"
            previous_quarter = f"{previous_year}Q{q}"
            budget_value = float(getattr(ae_config.budgets, f"q{q}"))

            # Current year calculations
            assigned_revenue = ae_data[
                (ae_data["Sector"] != "AAA - UNASSIGNED")
                & (ae_data[current_quarter] > 0)
            ][current_quarter].sum()

            unassigned_revenue = ae_data[
                (ae_data["Sector"] == "AAA - UNASSIGNED")
                & (ae_data[current_quarter] > 0)
            ][current_quarter].sum()

            # Previous year calculations
            previous_assigned_revenue = ae_data[
                (ae_data["Sector"] != "AAA - UNASSIGNED")
                & (ae_data[previous_quarter] > 0)
            ][previous_quarter].sum()

            previous_unassigned_revenue = ae_data[
                (ae_data["Sector"] == "AAA - UNASSIGNED")
                & (ae_data[previous_quarter] > 0)
            ][previous_quarter].sum()

            logger.debug(f"- Current quarter revenue: {assigned_revenue}")
            logger.debug(f"- Current quarter unassigned: {unassigned_revenue}")
            logger.debug(f"- Previous quarter revenue: {previous_assigned_revenue}")
            logger.debug(
                f"- Previous quarter unassigned: {previous_unassigned_revenue}"
            )

            total_assigned += assigned_revenue
            total_unassigned += unassigned_revenue
            total_previous_year += previous_assigned_revenue

            # Calculate completion percentage
            completion_percentage = (
                (assigned_revenue / budget_value * 100) if budget_value > 0 else 0
            )

            # Year over year calculations
            yoy_change = (
                (
                    (assigned_revenue - previous_assigned_revenue)
                    / previous_assigned_revenue
                    * 100
                )
                if previous_assigned_revenue > 0
                else 0
            )
            logger.debug(f"- Year over year change: {yoy_change}%")

            quarterly_data.append(
                QuarterData(
                    name=f"Q{q} {current_year}",
                    assigned=assigned_revenue,
                    unassigned=unassigned_revenue,
                    budget=budget_value,
                    completion_percentage=completion_percentage,
                    previous_year_assigned=previous_assigned_revenue,
                    previous_year_unassigned=previous_unassigned_revenue,
                    year_over_year_change=yoy_change,
                )
            )

        # Calculate customer counts
        current_customers = len(
            ae_data[
                (ae_data["Sector"] != "AAA - UNASSIGNED")
                & (ae_data[current_quarters].sum(axis=1) > 0)
            ]["Customer"].unique()
        )

        previous_customers = len(
            ae_data[
                (ae_data["Sector"] != "AAA - UNASSIGNED")
                & (ae_data[previous_quarters].sum(axis=1) > 0)
            ]["Customer"].unique()
        )

        quarterly_totals = {
            q: d.assigned for q, d in zip(current_quarters, quarterly_data)
        }
        unassigned_totals = {
            q: d.unassigned for q, d in zip(current_quarters, quarterly_data)
        }

        avg_per_customer = (
            total_assigned / current_customers if current_customers > 0 else 0
        )

        total_yoy_change = (
            ((total_assigned - total_previous_year) / total_previous_year * 100)
            if total_previous_year > 0
            else 0
        )

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
            total_year_over_year_change=total_yoy_change,
        )

    # This patch focuses on fixing the year-over-year calculation in sales_analytics.py
    # Specifically in the calculate_company_quarterly_data method

    def calculate_company_quarterly_data(self, df: pd.DataFrame) -> List[dict]:
        """Calculate quarterly data for the entire company with corrected YoY changes."""
        logger = logging.getLogger(__name__)

        # Setup year/quarter references
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]

        # Log the quarters being analyzed for debugging
        logger.debug(
            f"Analyzing quarters: Current year ({current_year}): {current_quarters}"
        )
        logger.debug(
            f"Analyzing quarters: Previous year ({previous_year}): {previous_quarters}"
        )

        # Split data into assigned and unassigned
        assigned_data = df[df["Sector"] != "AAA - UNASSIGNED"]
        unassigned_data = df[df["Sector"] == "AAA - UNASSIGNED"]

        quarterly_data = []

        for q in range(1, 5):
            current_q = f"{current_year}Q{q}"
            previous_q = f"{previous_year}Q{q}"

            # Calculate quarterly totals with detailed logging
            assigned = assigned_data[current_q].sum()
            unassigned = unassigned_data[current_q].sum()
            previous_assigned = assigned_data[previous_q].sum()

            # Log the raw values for verification
            logger.debug(f"Q{q}: Current Year Assigned Revenue: ${assigned:,.2f}")
            logger.debug(
                f"Q{q}: Previous Year Assigned Revenue: ${previous_assigned:,.2f}"
            )
            logger.debug(f"Q{q}: Current Year Unassigned Revenue: ${unassigned:,.2f}")

            # ADD THIS LINE SPECIFICALLY FOR Q1 (right here)
            if q == 1:
                logger.debug(
                    f"DETAILED Q1 COMPARISON: 2025 Q1=${assigned:,.2f}, 2024 Q1=${previous_assigned:,.2f}, Calculation=({assigned:,.2f}-{previous_assigned:,.2f})/{previous_assigned:,.2f}*100 = {((assigned - previous_assigned) / previous_assigned * 100):,.2f}%"
                )

            # Calculate budget for this quarter
            budget = sum(
                float(getattr(ae_config.budgets, f"q{q}"))
                for ae_config in self.config.account_executives.values()
                if ae_config.enabled
            )

            # Calculate completion percentage
            completion_percentage = (assigned / budget * 100) if budget > 0 else 0

            # FIXED: Calculate year-over-year change correctly
            # If previous_assigned is 0, we want to indicate this as "new revenue"
            # rather than 0% change
            if previous_assigned > 0:
                # Correct formula: ((current - previous) / previous) * 100
                # A negative value means a decrease
                yoy_change = ((assigned - previous_assigned) / previous_assigned) * 100
                logger.debug(
                    f"Q{q} YoY Change: {yoy_change:.2f}% (${assigned:,.2f} vs ${previous_assigned:,.2f})"
                )
            else:
                # If there was no revenue last year, mark as "new revenue" with null percentage
                yoy_change = float("inf")  # Could also use None or a special indicator
                logger.debug(f"Q{q} YoY Change: New Revenue (no previous year revenue)")

            quarter_data = {
                "name": f"Q{q} {current_year}",
                "assigned": assigned,
                "unassigned": unassigned,
                "budget": budget,
                "completion_percentage": round(completion_percentage),
                "previous_year_assigned": previous_assigned,
                "previous_year_assigned_raw": previous_assigned,
                "year_over_year_change": yoy_change,
            }

            quarterly_data.append(quarter_data)

        return quarterly_data

    # This is the complete fix for the calculate_management_stats method
    # including the missing ae_data processing

    def calculate_management_stats(self, sales_data: pd.DataFrame) -> ManagementStats:
        """Calculate management-level statistics with fixed YoY calculations."""
        logger = logging.getLogger(__name__)

        # Create a copy of the data and setup year/quarter references
        df = sales_data.copy()
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)
        current_quarters = [f"{current_year}Q{q}" for q in range(1, 5)]
        previous_quarters = [f"{previous_year}Q{q}" for q in range(1, 5)]

        logger.debug(f"Management stats: Using current quarters: {current_quarters}")
        logger.debug(f"Management stats: Using previous quarters: {previous_quarters}")

        # Split data into assigned and unassigned
        assigned_data = df[df["Sector"] != "AAA - UNASSIGNED"]
        unassigned_data = df[df["Sector"] == "AAA - UNASSIGNED"]

        # Calculate company-wide totals
        total_revenue = assigned_data[current_quarters].sum().sum()
        total_unassigned_revenue = unassigned_data[current_quarters].sum().sum()
        total_customers = len(
            assigned_data[assigned_data[current_quarters].sum(axis=1) > 0][
                "Customer"
            ].unique()
        )

        # Previous year totals
        total_previous_year_revenue = assigned_data[previous_quarters].sum().sum()
        total_previous_year_unassigned = unassigned_data[previous_quarters].sum().sum()
        previous_year_customers = len(
            assigned_data[assigned_data[previous_quarters].sum(axis=1) > 0][
                "Customer"
            ].unique()
        )

        # Log the raw totals for verification
        logger.debug(f"Total Current Year Revenue: ${total_revenue:,.2f}")
        logger.debug(
            f"Total Previous Year Revenue: ${total_previous_year_revenue:,.2f}"
        )

        # FIXED: Calculate year-over-year change correctly
        if total_previous_year_revenue > 0:
            total_year_over_year_change = (
                (total_revenue - total_previous_year_revenue)
                / total_previous_year_revenue
                * 100
            )
            logger.debug(f"Total YoY Change: {total_year_over_year_change:.2f}%")
        else:
            total_year_over_year_change = float("inf")  # New revenue
            logger.debug("Total YoY Change: New Revenue (no previous year revenue)")

        # Calculate company quarterly data with the fixed function
        company_quarters = self.calculate_company_quarterly_data(sales_data)

        # Calculate total company budget
        company_total_budget = sum(
            sum(float(getattr(ae_config.budgets, f"q{q}")) for q in range(1, 5))
            for ae_config in self.config.account_executives.values()
            if ae_config.enabled
        )

        # Calculate company completion percentage
        company_completion_percentage = (
            (total_revenue / company_total_budget * 100)
            if company_total_budget > 0
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
                total_budget = 0

                for q in range(1, 5):
                    quarter_col = f"{current_year}Q{q}"
                    previous_quarter = f"{previous_year}Q{q}"
                    budget_value = float(getattr(ae_config.budgets, f"q{q}"))
                    total_budget += budget_value

                    # Get current and previous data for this quarter
                    current_data = next(
                        (
                            qd
                            for qd in ae_stats.quarterly_data
                            if qd.name == f"Q{q} {current_year}"
                        ),
                        None,
                    )

                    if current_data:
                        # Calculate previous year assigned raw value
                        previous_year_assigned_raw = current_data.previous_year_assigned
                        if isinstance(current_data.previous_year_assigned, str):
                            previous_year_assigned_raw = float(
                                current_data.previous_year_assigned.replace(
                                    "$", ""
                                ).replace(",", "")
                            )

                        # Create quarter data
                        quarter_data = {
                            "name": f"Q{q}",
                            "assigned": current_data.assigned,
                            "unassigned": current_data.unassigned,
                            "budget": budget_value,
                            "completion_percentage": round(
                                (current_data.assigned / budget_value * 100)
                                if budget_value > 0
                                else 0
                            ),
                            "previous_year_assigned": current_data.previous_year_assigned,
                            "previous_year_unassigned": current_data.previous_year_unassigned,
                            "year_over_year_change": current_data.year_over_year_change,
                            "previous_year_assigned_raw": previous_year_assigned_raw,
                        }
                        ae_quarters.append(quarter_data)

                # Calculate annual totals
                annual_completion_percentage = (
                    (ae_stats.total_assigned_revenue / total_budget * 100)
                    if total_budget > 0
                    else 0
                )

                annual_totals = {
                    "name": "Annual Total",
                    "assigned": ae_stats.total_assigned_revenue,
                    "unassigned": ae_stats.total_unassigned_revenue,
                    "budget": total_budget,
                    "completion_percentage": round(annual_completion_percentage),
                    "year_over_year_change": ae_stats.total_year_over_year_change,
                }

                # Calculate raw previous year revenue
                previous_year_revenue_raw = ae_stats.total_previous_year_revenue
                if isinstance(previous_year_revenue_raw, str):
                    previous_year_revenue_raw = float(
                        previous_year_revenue_raw.replace("$", "").replace(",", "")
                    )

                # Create AE data entry
                ae_entry = {
                    "name": ae_name,
                    "total_assigned_revenue": ae_stats.total_assigned_revenue,
                    "total_customers": ae_stats.total_customers,
                    "quarters": ae_quarters,
                    "previous_year_revenue": ae_stats.total_previous_year_revenue,
                    "previous_year_revenue_raw": previous_year_revenue_raw,
                    "previous_year_customers": ae_stats.previous_year_customers,
                    "year_over_year_change": ae_stats.total_year_over_year_change,
                    "total_budget": total_budget,
                    "annual_totals": annual_totals,
                }

                ae_data.append(ae_entry)

            except Exception as e:
                logger.error(f"Error processing AE {ae_name}: {str(e)}")
                continue

        # Sort AE data by total revenue
        ae_data.sort(key=lambda x: x["total_assigned_revenue"], reverse=True)

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
            company_completion_percentage=round(company_completion_percentage),
        )

    def override_with_direct_calculation(self, management_stats):
        """Override calculated YoY with direct calculation from DataProcessor"""
        logger = logging.getLogger(__name__)

        # Get the direct calculation from the DataProcessor
        from data_processor import DataProcessor

        data_processor = DataProcessor(self.config)

        # Check if direct calculation exists
        if hasattr(data_processor, "direct_q1_calculation"):
            direct_calculation = data_processor.direct_q1_calculation
            direct_yoy = direct_calculation["yoy_change"]

            # Find Q1 in company quarters
            for quarter in management_stats.company_quarters:
                if quarter["name"].startswith("Q1"):
                    calculated_yoy = quarter["year_over_year_change"]
                    logger.info(
                        f"Overriding Q1 YoY: {calculated_yoy:.2f}% -> {direct_yoy:.2f}%"
                    )

                    # Override with direct calculation
                    quarter["year_over_year_change"] = direct_yoy
                    break

            logger.info(
                "YoY calculation successfully overridden with direct calculation"
            )
        else:
            logger.warning("Direct calculation not available, using calculated values")

        return management_stats

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
        missing_columns = [
            col for col in required_columns if col not in sales_data_df.columns
        ]
        if missing_columns:
            raise ValueError(
                f"Missing required columns in sales data: {', '.join(missing_columns)}"
            )

        # Validate numeric columns (quarters)
        for col in self.quarter_columns:
            try:
                pd.to_numeric(sales_data_df[col], errors="raise")
            except (ValueError, TypeError):
                raise ValueError(f"Column {col} must contain numeric values")

        # Validate required string columns
        if sales_data_df["Customer"].isna().any():
            raise ValueError("Found missing values in Customer column")

        # Validate sector values
        if not all(
            sales_data_df["Sector"].isin(["AAA - UNASSIGNED"])
            | (sales_data_df["Sector"] != "AAA - UNASSIGNED")
        ):
            raise ValueError("Invalid values found in Sector column")

        # Validate AE names against configuration
        valid_aes = {
            name.lower()
            for name, ae in self.config.account_executives.items()
            if ae.enabled
        }
        actual_aes = {
            ae.lower() for ae in sales_data_df["AE1"].unique() if pd.notna(ae)
        }
        invalid_aes = actual_aes - valid_aes

        if invalid_aes:
            raise ValueError(
                f"Found unauthorized AEs in data: {', '.join(invalid_aes)}"
            )

    def validate_quarter_data(self, df: pd.DataFrame) -> None:
        """
        Validate that quarterly data exists and is correctly formatted.
        This helps catch issues with missing quarters or data assignment problems.

        Args:
            df: DataFrame containing the quarterly data

        Raises:
            ValueError: If quarter data is missing or malformed
        """
        logger = logging.getLogger(__name__)

        # Get expected quarter columns
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)
        expected_quarters = []

        for year in [previous_year, current_year]:
            for q in range(1, 5):
                expected_quarters.append(f"{year}Q{q}")

        # Check if all expected quarters exist in DataFrame
        missing_quarters = [q for q in expected_quarters if q not in df.columns]
        if missing_quarters:
            logger.warning(f"Missing quarter columns in data: {missing_quarters}")

        # Check that quarter columns contain numeric data
        for quarter in [q for q in expected_quarters if q in df.columns]:
            if not pd.api.types.is_numeric_dtype(df[quarter]):
                logger.warning(f"Quarter column {quarter} contains non-numeric data")

            # Log quarter totals for debugging
            total = df[quarter].sum()
            logger.debug(f"Quarter {quarter} total: ${total:,.2f}")

        # Verify Q1 2024 and Q1 2025 specifically (the problematic quarters)
        if f"{previous_year}Q1" in df.columns and f"{current_year}Q1" in df.columns:
            q1_prev = df[f"{previous_year}Q1"].sum()
            q1_curr = df[f"{current_year}Q1"].sum()
            yoy_change = (
                ((q1_curr - q1_prev) / q1_prev * 100) if q1_prev > 0 else float("inf")
            )

            logger.info(f"Q1 {previous_year} total: ${q1_prev:,.2f}")
            logger.info(f"Q1 {current_year} total: ${q1_curr:,.2f}")
            logger.info(f"Q1 YoY change: {yoy_change:.2f}%")

        # Check for suspicious data patterns
        # 1. Check for quarters with unusually low totals
        quarter_totals = {q: df[q].sum() for q in expected_quarters if q in df.columns}
        avg_total = sum(quarter_totals.values()) / len(quarter_totals)
        for quarter, total in quarter_totals.items():
            if total < avg_total * 0.25:  # Quarter is less than 25% of average
                logger.warning(
                    f"Quarter {quarter} total (${total:,.2f}) is unusually low compared to average (${avg_total:,.2f})"
                )

        # 2. Check for dramatic quarter-to-quarter changes
        for i in range(1, len(expected_quarters)):
            prev_q = expected_quarters[i - 1]
            curr_q = expected_quarters[i]
            if prev_q in df.columns and curr_q in df.columns:
                prev_total = df[prev_q].sum()
                curr_total = df[curr_q].sum()
                if prev_total > 0:
                    change = (curr_total - prev_total) / prev_total * 100
                    if abs(change) > 50:  # More than 50% change
                        logger.warning(
                            f"Large quarter-to-quarter change from {prev_q} (${prev_total:,.2f}) to {curr_q} (${curr_total:,.2f}): {change:.2f}%"
                        )
