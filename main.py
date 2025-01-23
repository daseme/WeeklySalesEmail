import sys
import logging
from pathlib import Path
from typing import Optional
import traceback
from datetime import datetime
import argparse
import os
import textwrap
from dotenv import load_dotenv

from config import Config
from data_processor import DataProcessor
from email_sender import EmailSender
from email_template_renderer import EmailTemplateRenderer
from sales_analytics import SalesAnalytics

# After the imports but before the config loading

# Load environment variables
load_dotenv()
print(f"Loaded .env file: SENDGRID_API_KEY length = {len(os.getenv('SENDGRID_API_KEY', ''))}")

# Parse command line arguments early
parser = argparse.ArgumentParser(
    description='Generate and send sales reports (Excel .xlsx format)'
)

def load_config(test_mode: bool = False, config_path: Optional[str] = None) -> Config:
    """Load and configure the application configuration"""
    # Load base configuration from JSON file
    config_file = config_path if config_path else "config.json"
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    config = Config.load_from_json(config_file)
    
    # Override settings for test mode if specified
    if test_mode:
        config.test_mode = True
        config.test_email = os.getenv("TEST_EMAIL", "kurt.olmstead@crossingstv.com")
        # Update email recipients for test mode
        config.email_recipients = {ae: [config.test_email] for ae in config.active_aes}
        config.management_recipients = [config.test_email]
    
    # Validate the configuration
    config.validate()
    
    return config

# Parse command line arguments early
parser = argparse.ArgumentParser(
    description='Generate and send sales reports (Excel .xlsx format)'
)
parser.add_argument(
    '-t', '--test',
    action='store_true',
    help='Run in test mode (sends emails only to test address)'
)
parser.add_argument(
    '-c', '--config',
    help='Path to configuration file'
)

# Get arguments without fully parsing to allow other parts to handle remaining args
args, _ = parser.parse_known_args()

# Load configuration with appropriate mode
config = load_config(test_mode=args.test, config_path=args.config)

# Display active AEs and mode
print(f"Active Account Executives: {config.active_aes}")
if args.test:
    print("Running in TEST mode - emails will only be sent to test address")

def setup_logging(config: Config) -> logging.Logger:
    """Configure logging for the application"""
    # Create logs directory
    log_dir = Path(config.reports_folder) / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    mode = 'TEST' if config.test_mode else 'PROD'
    log_file = log_dir / f'sales_report_{mode}_{timestamp}.log'
    
    # Configure logging with more detailed format
    logging.basicConfig(
        level=logging.DEBUG if config.test_mode else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set higher log level for SendGrid client to avoid payload logging
    logging.getLogger('python_http_client').setLevel(logging.INFO)
    
    return logging.getLogger(__name__)

def validate_environment() -> None:
    """Validate required environment variables"""
    if not config.test_mode:  # Only validate in production mode
        required_vars = ['SENDGRID_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

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

def run_sales_report() -> bool:
    """Main function to run the sales report generation process"""
    try:
        # Verify Excel dependencies first
        verify_excel_dependencies()
        
        # Validate environment variables
        validate_environment()
        
        # Set up logging
        logger = setup_logging(config)
        logger.info(f"Starting sales report generation in {'TEST' if config.test_mode else 'PRODUCTION'} mode")
        logger.info(f"Processing reports for AEs: {config.active_aes}")
        
        # Initialize components
        logger.info("Initializing components")
        
        # Set up template directory path
        templates_dir = Path(config.reports_folder).parent / "WeeklySalesEmail" / "email_templates"
        logger.debug(f"Templates directory path: {templates_dir}")
        if not templates_dir.exists():
            raise ValueError(f"Templates directory not found at: {templates_dir}")
            
        # Initialize components with proper paths
        data_processor = DataProcessor(config)
        template_renderer = EmailTemplateRenderer(templates_dir)
        email_sender = EmailSender(config, template_renderer)
        sales_analytics = SalesAnalytics(config)
        
        # Process data
        logger.info("Processing sales data")
        try:
            # Get sales data and created files
            sales_data, created_files = data_processor.process_data()
            logger.info(f"Created {len(created_files)} report files")
            for file in created_files:
                logger.info(f"Created file: {file}")
                if not file.endswith('.xlsx'):
                    logger.warning(f"Unexpected file extension for {file}")
            
            # Create mapping of AE names to report files
            reports_created = {
                os.path.basename(f).split('-')[0]: f
                for f in created_files
            }
            
        except Exception as e:
            logger.error(f"Error processing sales data: {str(e)}")
            raise
        
        # Send individual reports
        success_count = 0
        total_reports = len(reports_created)
        
        logger.info(f"Sending {total_reports} reports")
        for ae_name, report_path in reports_created.items():
            try:
                logger.info(f"Processing report for {ae_name}")
                
                # Calculate stats
                stats = sales_analytics.calculate_sales_stats(sales_data.report, ae_name)
                
                # Send email
                if email_sender.send_report(ae_name, stats, report_path):
                    success_count += 1
                    logger.info(f"Successfully sent report to {ae_name}")
                else:
                    logger.error(f"Failed to send email to {ae_name}")
                    
            except Exception as e:
                logger.error(f"Error processing {ae_name}: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Send management report
        try:
            logger.info("Generating management report")
            management_stats = sales_analytics.calculate_management_stats(sales_data.report)
            if email_sender.send_management_report(management_stats):
                logger.info("Successfully sent management report")
            else:
                logger.error("Failed to send management report")
        except Exception as e:
            logger.error(f"Error sending management report: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Log summary
        success = success_count == total_reports
        status = "SUCCESS" if success else "PARTIAL SUCCESS" if success_count > 0 else "FAILURE"
        logger.info(f"Process complete - {status}")
        logger.info(f"Reports sent successfully: {success_count}/{total_reports}")
        
        return success
        
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Critical error in sales report generation: {str(e)}")
            logger.error(traceback.format_exc())
        else:
            print(f"Critical error before logger initialization: {str(e)}")
            traceback.print_exc()
        return False

def print_summary(start_time: datetime, success: bool) -> None:
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
    
    # Run the report process
    success = run_sales_report()
    
    # Print summary
    print_summary(start_time, success)
    
    # Set exit code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()