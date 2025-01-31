#!/usr/bin/env python3

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple
import traceback
from datetime import datetime
import argparse
import os
from dotenv import load_dotenv

from config import Config
from data_processor import DataProcessor
from email_sender import EmailSender
from email_template_renderer import EmailTemplateRenderer, ManagementStats
from sales_analytics import SalesAnalytics

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def verify_excel_dependencies() -> None:
    """Verify required Excel-related dependencies are installed"""
    try:
        import pandas as pd
        import xlsxwriter
        import openpyxl
        import jinja2
    except ImportError as e:
        raise ImportError(
            "Missing required packages. Please run:\n"
            "pip install pandas xlsxwriter openpyxl jinja2"
        ) from e

def validate_environment(config: Config) -> None:
    """Validate required environment variables"""
    if not config.test_mode:
        required_vars = ["SENDGRID_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

def enhance_logging(config: Config, base_logger: logging.Logger) -> logging.Logger:
    """Enhance logging with file output"""
    log_dir = Path(config.reports_folder) / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "TEST" if config.test_mode else "PROD"
    log_file = log_dir / f"sales_report_{mode}_{timestamp}.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    base_logger.addHandler(file_handler)
    base_logger.setLevel(logging.DEBUG if config.test_mode else logging.INFO)

    # Set higher log level for SendGrid client
    logging.getLogger("python_http_client").setLevel(logging.INFO)

    return base_logger

def load_config(test_mode: bool = False, config_path: Optional[str] = None) -> Config:
    """Load and configure the application configuration"""
    config_file = config_path if config_path else "config.json"
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    config = Config.load_from_json(config_file)

    if test_mode:
        config.test_mode = True
        config.test_email = os.getenv("TEST_EMAIL", "test@example.com")
        config.email_recipients = {ae: [config.test_email] for ae in config.active_aes}
        config.management_recipients = [config.test_email]

    config.validate()
    return config

def process_ae_report(
    ae_name: str,
    report_path: str,
    sales_data,
    sales_analytics: SalesAnalytics,
    email_sender: EmailSender,
    logger: logging.Logger,
    is_test: bool = False
) -> bool:
    """Process and send report for a single AE"""
    try:
        mode_suffix = "(TEST MODE)" if is_test else ""
        logger.info(f"Processing report for {ae_name} {mode_suffix}")

        stats = sales_analytics.calculate_sales_stats(sales_data.report, ae_name)
        
        if email_sender.send_report(ae_name, stats, report_path):
            logger.info(f"Successfully sent report to {ae_name} {mode_suffix}")
            return True
        else:
            logger.error(f"Failed to send email to {ae_name} {mode_suffix}")
            return False

    except Exception as e:
        logger.error(f"Error processing {ae_name} {mode_suffix}: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def send_management_report(
    sales_data,
    sales_analytics: SalesAnalytics,
    email_sender: EmailSender,
    logger: logging.Logger
) -> bool:
    """Generate and send management report"""
    try:
        logger.info("Generating management report")

        management_stats = sales_analytics.calculate_management_stats(sales_data.report)
        sales_analytics.preprocess_management_stats(management_stats)

        if email_sender.send_management_report(management_stats):
            logger.info("Successfully sent management report")
            return True
        else:
            logger.error("Failed to send management report")
            return False

    except Exception as e:
        logger.error(f"Error sending management report: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def run_sales_report() -> tuple[bool, Optional[Config]]:
    """
    Main function to run the sales report generation process
    Returns:
        Tuple of (success: bool, config: Optional[Config])
    """
    config = None
    try:
        # Parse command line arguments first
        parser = argparse.ArgumentParser(
            description="Generate and send sales reports (Excel .xlsx format)"
        )
        parser.add_argument(
            "-t", "--test",
            action="store_true",
            help="Run in test mode (sends emails only to test address)"
        )
        parser.add_argument(
            "-c", "--config",
            help="Path to configuration file"
        )

        args = parser.parse_args()

        # Load environment variables
        load_dotenv()
        
        # Load and validate configuration
        config = load_config(test_mode=args.test, config_path=args.config)
        
        # Enhance logging with file output
        global logger
        logger = enhance_logging(config, logger)
        
        # Log initial information
        logger.info(f"Loaded .env file: SENDGRID_API_KEY length = {len(os.getenv('SENDGRID_API_KEY', ''))}")
        logger.info(f"Active Account Executives: {config.active_aes}")
        if args.test:
            logger.info("Running in TEST mode - emails will only be sent to test address")

        # Verify dependencies and environment
        verify_excel_dependencies()
        validate_environment(config)

        # Initialize components
        templates_dir = Path(config.reports_folder).parent / "WeeklySalesEmail" / "email_templates"
        if not templates_dir.exists():
            raise ValueError(f"Templates directory not found at: {templates_dir}")

        data_processor = DataProcessor(config)
        template_renderer = EmailTemplateRenderer(templates_dir)
        email_sender = EmailSender(config, template_renderer)
        sales_analytics = SalesAnalytics(config)

        # Process data
        logger.info("Processing sales data")
        sales_data, created_files = data_processor.process_data()
        
        logger.info(f"Created {len(created_files)} report files")
        for file in created_files:
            logger.info(f"Created file: {file}")
            if not file.endswith(".xlsx"):
                logger.warning(f"Unexpected file extension for {file}")

        # Map AE names to report files
        reports_created: Dict[str, str] = {
            os.path.basename(f).split("-")[0]: f for f in created_files
        }

        # Send reports
        success_count = 0
        total_reports = len(reports_created)
        logger.info(f"Sending {total_reports} reports")

        if config.test_mode:
            # Test mode: process single selected AE
            print("\n=== TEST MODE ===")
            print("Please select an Account Executive (AE) to generate and send a report for:")
            
            for i, ae_name in enumerate(config.active_aes, start=1):
                print(f"{i}. {ae_name}")

            while True:
                try:
                    selection = int(input("Enter the number of the AE: "))
                    if 1 <= selection <= len(config.active_aes):
                        ae_name = config.active_aes[selection - 1]
                        break
                    print("Invalid selection. Please enter a number from the list.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

            report_path = reports_created.get(ae_name)
            if report_path and process_ae_report(
                ae_name, report_path, sales_data, sales_analytics, 
                email_sender, logger, is_test=True
            ):
                success_count += 1
        else:
            # Production mode: process all AEs
            for ae_name, report_path in reports_created.items():
                if process_ae_report(
                    ae_name, report_path, sales_data, sales_analytics, 
                    email_sender, logger
                ):
                    success_count += 1

        # Send management report
        try:
            logger.info("Generating management report")

            # Step 1: Generate management stats
            management_stats = sales_analytics.calculate_management_stats(sales_data.report)

            # Step 2: Preprocess the stats to ensure proper types
            sales_analytics.preprocess_management_stats(management_stats)

            # Step 3: Send the management stats object directly
            management_success = email_sender.send_management_report(management_stats)
            if management_success:
                logger.info("Successfully sent management report")
            else:
                logger.error("Failed to send management report")

        except Exception as e:
            logger.error(f"Error sending management report: {str(e)}")
            logger.error(traceback.format_exc())
            management_success = False

        # Determine overall success
        success = success_count == total_reports and management_success
        status = (
            "SUCCESS" if success
            else "PARTIAL SUCCESS" if success_count > 0 or management_success
            else "FAILURE"
        )
        
        logger.info(f"Process complete - {status}")
        logger.info(f"Reports sent successfully: {success_count}/{total_reports}")
        logger.info(f"Management report status: {'Success' if management_success else 'Failed'}")

        return success, config

    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Critical error in sales report generation: {str(e)}")
            logger.error(traceback.format_exc())
        else:
            print(f"Critical error before logger initialization: {str(e)}")
            traceback.print_exc()
        return False, config

def print_summary(start_time: datetime, success: bool, config: Config) -> None:
    """Print execution summary"""
    end_time = datetime.now()
    duration = end_time - start_time

    print("\nExecution Summary:")
    print(f"Mode: {'TEST' if config.test_mode else 'PRODUCTION'}")
    print(f"Status: {'SUCCESS' if success else 'FAILURE'}")
    print(f"Started at: {start_time:%Y-%m-%d %H:%M:%S}")
    print(f"Ended at: {end_time:%Y-%m-%d %H:%M:%S}")
    print(f"Total duration: {duration}")

def main():
    """Main entry point for the application"""
    start_time = datetime.now()
    success, config = run_sales_report()
    
    if config:  # Only print summary if we have a valid config
        print_summary(start_time, success, config)
    else:
        print("\nExecution Summary:")
        print("Status: FAILURE (Configuration error)")
        print(f"Started at: {start_time:%Y-%m-%d %H:%M:%S}")
        print(f"Ended at: {datetime.now():%Y-%m-%d %H:%M:%S}")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()