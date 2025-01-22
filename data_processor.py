import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Dict
import glob
import os
from datetime import datetime
from config import Config, AccountExecutive


@dataclass
class Budget:
    """Container for quarterly budget values"""
    q1: float
    q2: float
    q3: float
    q4: float


@dataclass
class Config:
    """Configuration container"""
    root_path: str
    reports_folder: str
    vba_path: str
    sendgrid_api_key: str
    sender_email: str
    email_recipients: Dict[str, List[str]]
    ae_budgets: Dict[str, Budget]
    test_mode: bool = False


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

    def process_data(self) -> Tuple[SalesData, List[str]]:
        """Main method to process all sales data"""
        try:
            infile = self.get_latest_forecast_file()
            print(f"Processing file: {infile}")

            # Read and process the data
            df = pd.read_excel(infile, "RevenueDB")
            print(f"Read {len(df)} rows from Excel")

            df_cleaned = self._clean_dataframe(df)
            print(f"After cleaning: {len(df_cleaned)} rows")

            df_pivot = self._create_pivot(df_cleaned)
            print(f"After pivot: {len(df_pivot)} rows")

            timeframe = self._filter_timeframe(df_pivot)
            print(f"After timeframe filter: {len(timeframe)} rows")

            # Create main report and budget report
            main_report = self._create_main_report(timeframe)
            print(f"Main report rows: {len(main_report)}")
            print(f"AEs in main report: {main_report['AE1'].unique()}")

            budget_report = self._create_budget_report(main_report)
            print(f"Budget report rows: {len(budget_report)}")

            # Save the reports and get list of files created
            created_files = self.save_report(
                main_report,
                budget_report,
                self.config.reports_folder,  # Use correct path from config
            )
            print(f"Created files: {created_files}")

            # Return both the data and files list
            return (
                SalesData(main_report, budget_report, self.quarter_columns),
                created_files,
            )

        except Exception as e:
            print(f"Error in process_data: {str(e)}")  # Debug print
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
                    df[col].replace("[\$,]", "", regex=True), errors="coerce"
                )
            except:
                pass

        return df[df.Sector != "TRADE"]

    def _create_pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create pivot table from cleaned data"""
        print("Debug - AE1 values before pivot:", df["AE1"].unique())

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

        # Find date columns
        date_columns = [
            col
            for col in df.columns
            if isinstance(col, str)
            and any(str(col).startswith(str(i) + "/") for i in range(1, 13))
        ]

        print(f"Debug - Found {len(date_columns)} date columns")

        # Create pivot
        df_subset = df[id_vars + date_columns].copy()
        print("Debug - AE1 values in subset:", df_subset["AE1"].unique())

        df_pivot = pd.melt(
            df_subset, id_vars=id_vars, var_name="Date", value_name="Amt"
        )

        print("Debug - AE1 values after melt:", df_pivot["AE1"].unique())

        # Convert to datetime and add derived columns
        df_pivot["Date"] = pd.to_datetime(df_pivot["Date"])
        df_pivot["Quarter"] = df_pivot["Date"].dt.quarter
        df_pivot["Year"] = df_pivot["Date"].dt.year
        df_pivot["Year_Quarter"] = (
            df_pivot["Year"].map(str).str[2:4] + "Q" + df_pivot["Quarter"].map(str)
        )

        print("Debug - Final AE1 values in pivot:", df_pivot["AE1"].unique())
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
        """Filter data for current year and positive amounts"""
        print("Debug - AE1 values before timeframe filter:", df["AE1"].unique())

        current_year = datetime.now().year

        # Clean and convert amount column
        df["Amt"] = df["Amt"].apply(self._clean_currency)

        # Filter the data
        filtered_df = df[
            (df["Date"].dt.year == current_year)  # Changed to exact year match
            & (df["Amt"] > 0)
        ]

        print("Debug - AE1 values after timeframe filter:", filtered_df["AE1"].unique())
        print(f"Debug - Year_Quarter values: {filtered_df['Year_Quarter'].unique()}")
        return filtered_df

    def _create_main_report(self, timeframe: pd.DataFrame) -> pd.DataFrame:
        """Create the main sales report with proper filtering of empty rows"""
        # Create a copy to avoid SettingWithCopyWarning
        timeframe = timeframe.copy()
        print(f"Debug - Initial shape: {timeframe.shape}")

        # Fill NaN values with appropriate defaults
        timeframe["Customer"] = timeframe["Customer"].fillna("Unspecified Customer")
        timeframe["Sector"] = timeframe["Sector"].fillna("Unspecified Sector")
        timeframe["AE1"] = timeframe["AE1"].fillna("")

        # Clean the Amt column
        timeframe["Amt"] = pd.to_numeric(
            timeframe["Amt"].replace("[\$,]", "", regex=True), errors="coerce"
        )
        timeframe = timeframe[timeframe["Amt"].notna() & (timeframe["Amt"] > 0)]

        # Filter for active AEs using the new config structure
        active_aes = self.config.active_aes
        timeframe = timeframe[
            timeframe["AE1"]
            .str.strip()
            .str.lower()
            .isin([ae.lower() for ae in active_aes])
        ]
        print(f"Debug - After AE filter shape: {timeframe.shape}")
        print(f"Debug - AEs present: {timeframe['AE1'].unique()}")

        # Create the summary DataFrame
        summary = (
            timeframe.groupby(["AE1", "Sector", "Customer", "Year_Quarter"])["Amt"]
            .sum()
            .reset_index()
        )

        # Create the pivot table
        pivot_table = pd.pivot_table(
            summary,
            values="Amt",
            index=["AE1", "Sector", "Customer"],
            columns=["Year_Quarter"],
            fill_value=0,
            aggfunc="sum",
        ).reset_index()

        # Ensure all required quarters exist
        for quarter in self.quarter_columns:
            if quarter not in pivot_table.columns:
                pivot_table[quarter] = 0

        # Sort columns
        final_columns = ["AE1", "Sector", "Customer"] + self.quarter_columns
        report = pivot_table.reindex(columns=final_columns, fill_value=0)

        # Sort rows
        report = report.sort_values(["AE1", "Sector", "Customer"])
        
        return report

    def _create_budget_report(self, main_report: pd.DataFrame) -> pd.DataFrame:
        """Create budget and unassigned report"""
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

        # Get assigned totals for non-zero rows
        assigned = main_report.groupby("AE1")[self.quarter_columns].sum().reset_index()

        # Create budget rows using new config structure
        budget_rows = []
        for ae_name, ae_config in self.config.account_executives.items():
            if ae_config.enabled:
                budget_row = {
                    "AE1": ae_name,
                    "Sector": "Budget",
                    "Customer": "Budget",
                    self.quarter_columns[0]: float(ae_config.budgets.q1),
                    self.quarter_columns[1]: float(ae_config.budgets.q2),
                    self.quarter_columns[2]: float(ae_config.budgets.q3),
                    self.quarter_columns[3]: float(ae_config.budgets.q4),
                }
                budget_rows.append(budget_row)

        # Create budget DataFrame
        budget_df = pd.DataFrame(budget_rows)

        # Get unassigned data
        unassigned = main_report[main_report["Sector"] == "AAA - UNASSIGNED"].copy()

        # Ensure numeric columns in unassigned data
        for col in self.quarter_columns:
            unassigned[col] = pd.to_numeric(
                unassigned[col].replace("", "0"), errors="coerce"
            )

        # Only keep unassigned rows with non-zero values
        unassigned = unassigned[unassigned[self.quarter_columns].sum(axis=1) > 0]

        # Combine reports and calculate totals
        report = pd.concat([budget_df, assigned, unassigned], ignore_index=True)
        report["Total"] = report[self.quarter_columns].sum(axis=1)

        # Arrange columns
        cols = ["AE1", "Sector", "Customer"] + self.quarter_columns + ["Total"]
        report = report.reindex(columns=cols)

        # Fill missing values and sort
        report["Sector"] = report["Sector"].fillna("Assigned")
        report = report.sort_values(["AE1", "Sector", "Customer"])

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
            budget_data = budget_unassigned[budget_unassigned.AE1 == sales_person].copy()

            try:
                with pd.ExcelWriter(full_path, engine="xlsxwriter") as writer:
                    # Write data first
                    sales_person_data.to_excel(writer, sheet_name="Sheet1", index=False)
                    budget_data.to_excel(writer, sheet_name="Budget-Assigned-Unassigned", index=False)
                    
                    workbook = writer.book
                    worksheet1 = writer.sheets["Sheet1"]
                    
                    # Set formats
                    money_fmt = workbook.add_format({"num_format": "$#,##0", "align": "right"})
                    
                    # Column formatting
                    worksheet1.set_column("A:B", 15)
                    worksheet1.set_column("C:C", 30)
                    worksheet1.set_column("D:G", 12, money_fmt)

                    # Critical change: Calculate table range to include all data rows plus header and totals
                    num_rows = len(sales_person_data)
                    end_row = num_rows + 1  # Add 1 for header and 1 for totals
                    
                    # Define the Excel table with proper range
                    worksheet1.add_table(0, 0, end_row, 6, {
                        "columns": [
                            {"header": "AE1"},
                            {"header": "Sector"},
                            {"header": "Customer"},
                            {"header": self.quarter_columns[0], "total_function": "sum"},
                            {"header": self.quarter_columns[1], "total_function": "sum"},
                            {"header": self.quarter_columns[2], "total_function": "sum"},
                            {"header": self.quarter_columns[3], "total_function": "sum"}
                        ],
                        "style": "Table Style Light 11",
                        "autofilter": True,
                        "total_row": True
                    })

                    # Format other sheet
                    worksheet2 = writer.sheets["Budget-Assigned-Unassigned"]
                    worksheet2.set_column("A:B", 15)
                    worksheet2.set_column("C:C", 30)
                    worksheet2.set_column("D:H", 12, money_fmt)

                    # Freeze panes and set zoom
                    worksheet1.freeze_panes(1, 0)
                    worksheet2.freeze_panes(1, 0)
                    worksheet1.set_zoom(90)
                    worksheet2.set_zoom(90)

                    files_created.append(full_path)

            except Exception as e:
                if os.path.exists(full_path):
                    os.remove(full_path)
                raise

        return files_created