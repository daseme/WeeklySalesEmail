import pandas as pd
import logging
from dataclasses import dataclass
from typing import Tuple, List
import glob
import os
from datetime import datetime
from config import Config


@dataclass
class Budget:
    """Container for quarterly budget values"""

    q1: float
    q2: float
    q3: float
    q4: float

@dataclass
class SalesData:
    """Container for processed sales data"""

    report: pd.DataFrame
    budget_unassigned: pd.DataFrame
    quarter_columns: List[str]


class DataProcessor:
    """Handles all data processing operations for sales reports"""

    def __init__(self, config: Config):
        """Initialize with configuration"""
        self.config = config
        self.current_year = str(datetime.now().year)[2:]
        self.quarter_columns = [f"{self.current_year}Q{i}" for i in range(1, 5)]

    def get_latest_forecast_file(self) -> str:
        """Find the most recent forecast file in the specified directory"""
        files = [
            fn
            for fn in glob.glob(self.config.get_forecast_path())
            if not os.path.basename(fn).startswith("~")
        ]
        if not files:
            raise FileNotFoundError(
                f"No forecast files found in {self.config.get_forecast_path()}"
            )
        return max(files, key=os.path.getctime)

    def get_unfiltered_data(self, excel_file, sheet_name):
        """Extract raw data from Excel without any filters"""
        import openpyxl
        import pandas as pd
        import tempfile
        import os
        
        logger = logging.getLogger(__name__)
        logger.info(f"Extracting unfiltered data from {excel_file}, sheet {sheet_name}")
        
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_file:
            temp_csv = temp_file.name
        
        try:
            # Load the workbook and get the sheet
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb[sheet_name]
            
            # Extract all data cell by cell to ensure no filters are applied
            data = []
            headers = None
            for i, row in enumerate(sheet.rows):
                row_data = [cell.value for cell in row]
                if i == 0:
                    headers = row_data
                else:
                    data.append(row_data)
            
            # Create DataFrame from raw data
            df = pd.DataFrame(data, columns=headers)
            
            # Save to CSV temporarily (removes all Excel formatting/filters)
            df.to_csv(temp_csv, index=False)
            
            # Read back the CSV (clean data)
            clean_df = pd.read_csv(temp_csv)
            logger.info(f"Successfully extracted {len(clean_df)} rows of unfiltered data")
            
            return clean_df
        
        except Exception as e:
            logger.error(f"Error extracting unfiltered data: {str(e)}")
            raise
        
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_csv):
                os.remove(temp_csv)

    def calculate_direct_yoy_change(self, df, year1, year2, start_month=1, end_month=3):
        """
        Calculate YoY change directly from monthly columns
        
        Args:
            df: DataFrame with monthly data columns
            year1: Previous year (e.g., 2024)
            year2: Current year (e.g., 2025)
            start_month: First month of quarter (default: 1 for Q1)
            end_month: Last month of quarter (default: 3 for Q1)
        
        Returns:
            Dictionary with totals and YoY change
        """
        logger = logging.getLogger(__name__)
        
        # Define month columns for each year
        year1_cols = [f"{m}/1/{year1}" for m in range(start_month, end_month + 1)]
        year2_cols = [f"{m}/1/{year2}" for m in range(start_month, end_month + 1)]
        
        # Sum values for each year
        year1_total = 0
        year2_total = 0
        
        # Validate columns exist
        missing_cols = []
        for col in year1_cols + year2_cols:
            if col not in df.columns:
                missing_cols.append(col)
        
        if missing_cols:
            logger.warning(f"Missing columns: {missing_cols}")
        
        # Calculate totals for previous year
        for col in year1_cols:
            if col in df.columns:
                # Convert string values to numeric, handling currency symbols
                if df[col].dtype == 'object':
                    df[col] = df[col].replace('[$,]', '', regex=True).astype(float)
                col_sum = df[col].sum()
                logger.info(f"{col} sum: ${col_sum:,.2f}")
                year1_total += col_sum
        
        # Calculate totals for current year
        for col in year2_cols:
            if col in df.columns:
                # Convert string values to numeric, handling currency symbols
                if df[col].dtype == 'object':
                    df[col] = df[col].replace('[$,]', '', regex=True).astype(float)
                col_sum = df[col].sum()
                logger.info(f"{col} sum: ${col_sum:,.2f}")
                year2_total += col_sum
        
        # Calculate YoY change
        if year1_total > 0:
            yoy_change = ((year2_total - year1_total) / year1_total) * 100
        else:
            yoy_change = float('inf')  # Undefined if previous year had zero revenue
        
        logger.info(f"Direct calculation: {year1} total: ${year1_total:,.2f}")
        logger.info(f"Direct calculation: {year2} total: ${year2_total:,.2f}")
        logger.info(f"Direct calculation: YoY change: {yoy_change:.2f}%")
        
        return {
            'previous_year_total': year1_total,
            'current_year_total': year2_total,
            'yoy_change': yoy_change
        }

    def process_data(self) -> Tuple[SalesData, List[str]]:
        """Main method to process all sales data"""
        logger = logging.getLogger(__name__)
        try:
            infile = self.get_latest_forecast_file()
            logger.info(f"Processing file: {infile}")
            
            # Extract unfiltered data first
            raw_df = self.get_unfiltered_data(infile, "RevenueDB")
            
            # Calculate direct YoY before any processing
            current_year = datetime.now().year
            previous_year = current_year - 1
            
            # Calculate Q1 YoY directly
            q1_direct = self.calculate_direct_yoy_change(raw_df, previous_year, current_year, 1, 3)
            logger.info(f"DIRECT Q1 YoY CALCULATION: {q1_direct['yoy_change']:.2f}%")
            
            # Store the direct calculation for later use
            self.direct_q1_calculation = q1_direct
            
            # Continue with regular processing but use the unfiltered data
            df = raw_df
            logger.info(f"Read {len(df)} rows from Excel")

            df_cleaned = self._clean_dataframe(df)
            logger.info(f"After cleaning: {len(df_cleaned)} rows")

            df_pivot = self._create_pivot(df_cleaned)
            logger.info(f"After pivot: {len(df_pivot)} rows")

            timeframe = self._filter_timeframe(df_pivot)
            logger.info(f"After timeframe filter: {len(timeframe)} rows")

            # Create main report and budget report
            main_report = self._create_main_report(timeframe)
            logger.info(f"Main report rows: {len(main_report)}")
            logger.debug(f"AEs in main report: {main_report['AE1'].unique()}")

            budget_report = self._create_budget_report(main_report)
            logger.info(f"Budget report rows: {len(budget_report)}")

            # Save the reports and get list of files created
            created_files = self.save_report(
                main_report,
                budget_report,
                self.config.reports_folder,  # Use correct path from config
            )
            logger.info(f"Created files: {created_files}")

            # Return both the data and files list
            return (
                SalesData(main_report, budget_report, self.quarter_columns),
                created_files,
            )

        except Exception as e:
            logger.error(f"Error in process_data: {str(e)}")
            raise RuntimeError(f"Error processing data: {str(e)}") from e

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove unnecessary columns and rows"""
        drop_columns = [
            "Active",
            "AE2",
            "AE3",
            "GrossCommission",
            "Broker",
            "BrokerPercent",
        ]

        # Drop specified columns and filter out TRADE sector
        df = df.drop(columns=drop_columns)

        # Fill NaN values in Sector
        df["Sector"] = df["Sector"].fillna("Unspecified")

        # Convert amount columns to numeric
        date_columns = [
            col
            for col in df.columns
            if str(col).startswith(
                (
                    "1/",
                    "2/",
                    "3/",
                    "4/",
                    "5/",
                    "6/",
                    "7/",
                    "8/",
                    "9/",
                    "10/",
                    "11/",
                    "12/",
                )
            )
        ]
        for col in date_columns:
            try:
                df[col] = pd.to_numeric(
                    df[col].replace(r"[\$,]", "", regex=True), errors="coerce"
                )
            except:
                pass

        return df[df.Sector != "TRADE"]

    def _create_pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create pivot table from cleaned data"""
        logger = logging.getLogger(__name__)
        logger.debug("=== PIVOT DEBUG ===")
        logger.debug(f"1. Shape before pivot: {df.shape}")

        # Define columns to keep as is
        id_vars = [
            "Customer",
            "Market",
            "Revenue Class",
            "AE1",
            "BrokerName",
            "Agency",
            "AgencyPercent",
            "Sector",
        ]

        # Find date columns for both years
        current_year = datetime.now().year
        previous_year = current_year - 1

        date_columns = []
        for year in [previous_year, current_year]:
            for month in range(1, 13):
                col = f"{month}/1/{year}"
                if col in df.columns:
                    date_columns.append(col)

        logger.debug(f"2. Found {len(date_columns)} date columns")
        logger.debug(f"3. Sample date columns: {date_columns[:5]}")

        # Create pivot
        df_subset = df[id_vars + date_columns].copy()
        logger.debug(f"4. Subset shape: {df_subset.shape}")

        df_pivot = pd.melt(
            df_subset, id_vars=id_vars, var_name="Date", value_name="Amt"
        )

        # Convert to datetime and add derived columns
        df_pivot["Date"] = pd.to_datetime(df_pivot["Date"])
        df_pivot["Quarter"] = df_pivot["Date"].dt.quarter
        df_pivot["Year"] = df_pivot["Date"].dt.year

        # Create year-specific quarter names (e.g., "24Q1", "25Q1")
        df_pivot["Year_Quarter"] = (
            df_pivot["Year"].astype(str).str[-2:]
            + "Q"
            + df_pivot["Quarter"].astype(str)
        )

        logger.debug("5. Final pivot info:")
        logger.debug(f"Shape: {df_pivot.shape}")
        logger.debug(
            f"Year quarters present: {sorted(df_pivot['Year_Quarter'].unique())}"
        )

        return df_pivot

    def _clean_currency(self, value) -> float:
        """Clean currency strings to floats"""
        if pd.isna(value):
            return 0.0
        if isinstance(value, str):
            # Remove currency symbols and commas, then convert to float
            clean_str = value.replace("$", "").replace(",", "").strip()
            return float(clean_str) if clean_str else 0.0
        return float(value) if value else 0.0

    def _filter_timeframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter data for current and previous year with positive amounts"""
        logger = logging.getLogger(__name__)
        logger.debug("=== DETAILED TIMEFRAME DEBUG ===")
        logger.debug(f"1. Initial shape: {df.shape}")

        # Show date range
        logger.debug(f"2. Date range: {df['Date'].min()} to {df['Date'].max()}")
        logger.debug(f"3. Years present: {sorted(df['Date'].dt.year.unique())}")

        # Show data by year before filtering
        logger.debug("4. Rows per year before filtering:")
        year_counts = df.groupby(df["Date"].dt.year).size()
        logger.debug(f"\n{year_counts}")

        # Show non-zero amounts by year
        logger.debug("5. Non-zero amounts by year:")
        nonzero = df[df["Amt"] > 0].groupby(df["Date"].dt.year).size()
        logger.debug(f"\n{nonzero}")

        current_year = datetime.now().year
        previous_year = current_year - 1

        # After year filter but before amount filter
        year_filtered = df[df["Date"].dt.year.isin([current_year, previous_year])]
        logger.debug(
            f"6. After year filter (before amount filter): {year_filtered.shape}"
        )

        # After both filters
        filtered_df = year_filtered[year_filtered["Amt"] > 0]
        logger.debug(f"7. After amount filter: {filtered_df.shape}")

        logger.debug("8. Sample of data:")
        logger.debug(filtered_df[["Date", "AE1", "Amt"]].head().to_string())

        return filtered_df

    def _create_main_report(self, timeframe: pd.DataFrame) -> pd.DataFrame:
        """Create the main sales report with proper filtering of empty rows"""
        logger = logging.getLogger(__name__)
        logger.debug("=== Main Report Creation Debug ===")
        logger.debug(f"1. Initial timeframe shape: {timeframe.shape}")
        logger.debug(
            f"2. Year_Quarter values present: {sorted(timeframe['Year_Quarter'].unique())}"
        )

        # Create a copy to avoid SettingWithCopyWarning
        timeframe = timeframe.copy()

        # Fill NaN values with appropriate defaults
        timeframe["Customer"] = timeframe["Customer"].fillna("Unspecified Customer")
        timeframe["Sector"] = timeframe["Sector"].fillna("Unspecified Sector")
        timeframe["AE1"] = timeframe["AE1"].fillna("")

        # Clean the Amt column
        timeframe["Amt"] = pd.to_numeric(
            timeframe["Amt"].replace(r"[\$,]", "", regex=True), errors="coerce"
        )
        timeframe = timeframe[timeframe["Amt"].notna() & (timeframe["Amt"] > 0)]

        # Filter for active AEs
        active_aes = self.config.active_aes
        timeframe = timeframe[
            timeframe["AE1"]
            .str.strip()
            .str.lower()
            .isin([ae.lower() for ae in active_aes])
        ]

        logger.debug(f"3. After AE filtering: {timeframe.shape}")

        # Create the summary DataFrame
        summary = (
            timeframe.groupby(["AE1", "Sector", "Customer", "Year_Quarter"])["Amt"]
            .sum()
            .reset_index()
        )

        logger.debug(
            f"4. Unique Year_Quarters in summary: {sorted(summary['Year_Quarter'].unique())}"
        )

        # Create the pivot table - MODIFIED to keep both years
        pivot_table = pd.pivot_table(
            summary,
            values="Amt",
            index=["AE1", "Sector", "Customer"],
            columns=["Year_Quarter"],
            fill_value=0,
            aggfunc="sum",
        ).reset_index()

        logger.debug(f"5. Final columns: {pivot_table.columns.tolist()}")

        # Ensure all required quarters exist
        all_quarters = []
        current_year = str(datetime.now().year)[2:]
        previous_year = str(int(current_year) - 1)

        for year in [previous_year, current_year]:
            for q in range(1, 5):
                quarter = f"{year}Q{q}"
                all_quarters.append(quarter)
                if quarter not in pivot_table.columns:
                    pivot_table[quarter] = 0

        # Sort columns to ensure consistent order
        final_columns = ["AE1", "Sector", "Customer"] + sorted(all_quarters)
        report = pivot_table.reindex(columns=final_columns, fill_value=0)

        logger.debug(f"6. Final report columns: {report.columns.tolist()}")

        return report.sort_values(["AE1", "Sector", "Customer"])

    def _create_budget_report(self, main_report: pd.DataFrame) -> pd.DataFrame:
        """Create budget and unassigned report with correct assigned calculation"""
        # Create a copy of the report to avoid warnings
        main_report = main_report.copy()

        # Create missing quarter columns if they don't exist
        for qtr in self.quarter_columns:
            if qtr not in main_report.columns:
                main_report[qtr] = 0

        # Ensure quarter columns are numeric
        for col in self.quarter_columns:
            main_report[col] = pd.to_numeric(
                main_report[col].replace("", "0"), errors="coerce"
            )

        # Calculate assigned totals correctly
        assigned_rows = []
        budget_rows = []
        unassigned_rows = []

        # Process each AE
        for ae_name, ae_config in self.config.account_executives.items():
            if not ae_config.enabled:
                continue

            ae_data = main_report[main_report["AE1"] == ae_name]

            # Create budget row
            budget_row = {"AE1": ae_name, "Sector": "Budget", "Customer": "Budget"}
            for i, qtr in enumerate(self.quarter_columns, 1):
                budget_row[qtr] = float(getattr(ae_config.budgets, f"q{i}"))
            budget_rows.append(budget_row)

            # Get unassigned data
            unassigned_data = ae_data[ae_data["Sector"] == "AAA - UNASSIGNED"]
            if not unassigned_data.empty:
                unassigned_rows.append(
                    {
                        "AE1": ae_name,
                        "Sector": "AAA - UNASSIGNED",
                        "Customer": "New Accounts",
                        **{
                            qtr: unassigned_data[qtr].sum()
                            for qtr in self.quarter_columns
                        },
                    }
                )

            # Calculate assigned (total minus unassigned)
            assigned_row = {"AE1": ae_name, "Sector": "Assigned", "Customer": ""}
            for qtr in self.quarter_columns:
                total_revenue = ae_data[qtr].sum()
                unassigned_revenue = (
                    unassigned_data[qtr].sum() if not unassigned_data.empty else 0
                )
                assigned_row[qtr] = total_revenue - unassigned_revenue
            assigned_rows.append(assigned_row)

        # Combine all rows
        report = pd.concat(
            [
                pd.DataFrame(budget_rows),
                pd.DataFrame(assigned_rows),
                pd.DataFrame(unassigned_rows),
            ],
            ignore_index=True,
        )

        # Calculate total column
        report["Total"] = report[self.quarter_columns].sum(axis=1)

        # Arrange columns
        cols = ["AE1", "Sector", "Customer"] + self.quarter_columns + ["Total"]
        report = report.reindex(columns=cols)

        # Sort the report
        report = report.sort_values(["AE1", "Sector"])

        return report

    def save_report(
        self, report: pd.DataFrame, budget_unassigned: pd.DataFrame, report_folder: str
    ) -> List[str]:
        """Save reports as regular Excel files with proper formatting"""
        files_created = []
        os.makedirs(report_folder, exist_ok=True)

        for sales_person in report["AE1"].unique():
            filename = f"{sales_person}-Sales Tool-{datetime.now().strftime('%y%m%d-%H%M%S')}.xlsx"
            full_path = os.path.join(report_folder, filename)
            sales_person_data = report[report.AE1 == sales_person].copy()
            budget_data = budget_unassigned[
                budget_unassigned.AE1 == sales_person
            ].copy()

            try:
                with pd.ExcelWriter(full_path, engine="xlsxwriter") as writer:
                    # Write data first
                    sales_person_data.to_excel(writer, sheet_name="Sheet1", index=False)
                    budget_data.to_excel(
                        writer, sheet_name="Budget-Assigned-Unassigned", index=False
                    )

                    workbook = writer.book
                    worksheet1 = writer.sheets["Sheet1"]

                    # Set formats
                    money_fmt = workbook.add_format(
                        {"num_format": "$#,##0", "align": "right"}
                    )

                    # Column formatting
                    worksheet1.set_column("A:B", 15)
                    worksheet1.set_column("C:C", 30)

                    # Format all quarter columns with money format
                    quarter_start_col = 3  # Column D
                    for col_idx in range(
                        quarter_start_col, len(sales_person_data.columns)
                    ):
                        col_letter = chr(
                            65 + col_idx
                        )  # Convert number to letter (3 = D, 4 = E, etc.)
                        worksheet1.set_column(
                            f"{col_letter}:{col_letter}", 12, money_fmt
                        )

                    # Calculate table range to include all data rows plus header
                    num_rows = len(sales_person_data)
                    end_row = num_rows + 1  # Add 1 for header and 1 for totals

                    # Get all quarter columns
                    id_cols = ["AE1", "Sector", "Customer"]
                    quarter_cols = [
                        col for col in sales_person_data.columns if col not in id_cols
                    ]

                    # Define the Excel table with proper range and all columns
                    table_columns = [
                        {"header": "AE1"},
                        {"header": "Sector"},
                        {"header": "Customer"},
                    ]

                    # Add quarter columns with sum totals
                    for quarter in quarter_cols:
                        table_columns.append(
                            {"header": quarter, "total_function": "sum"}
                        )

                    worksheet1.add_table(
                        0,
                        0,
                        end_row,
                        len(sales_person_data.columns) - 1,
                        {
                            "columns": table_columns,
                            "style": "Table Style Light 11",
                            "autofilter": True,
                            "total_row": True,
                        },
                    )

                    # Format other sheet
                    worksheet2 = writer.sheets["Budget-Assigned-Unassigned"]
                    worksheet2.set_column("A:B", 15)
                    worksheet2.set_column("C:C", 30)

                    # Format all money columns in second sheet
                    for col_idx in range(3, len(budget_data.columns)):
                        col_letter = chr(65 + col_idx)
                        worksheet2.set_column(
                            f"{col_letter}:{col_letter}", 12, money_fmt
                        )

                    # Freeze panes and set zoom
                    worksheet1.freeze_panes(1, 0)
                    worksheet2.freeze_panes(1, 0)
                    worksheet1.set_zoom(90)
                    worksheet2.set_zoom(90)

                    files_created.append(full_path)

            except Exception:
                if os.path.exists(full_path):
                    os.remove(full_path)
                raise

        return files_created
