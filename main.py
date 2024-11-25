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
        level=logging.DEBUG if config.test_mode else logging.INFO,  # More detailed logging in test mode
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def validate_environment() -> None:
    """Validate required environment variables and Python version"""
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
        import jinja2  # Add Jinja2 to dependency check
    except ImportError as e:
        raise ImportError(
            "Missing required packages. Please run:\n"
            "pip install pandas xlsxwriter openpyxl jinja2"
        ) from e

def run_sales_report(config_path: Optional[str] = None, test_mode: bool = False) -> bool:
    """Main function to run the sales report generation process"""
    try:
        # Verify Excel dependencies first
        verify_excel_dependencies()
        
        # Validate environment
        if not test_mode:
            validate_environment()
        
        # Load configuration
        config = (Config.load_from_json(config_path) if config_path 
                 else Config.load_default(test_mode=test_mode))
        
        # Validate configuration
        config.validate()
        
        # Set up logging
        logger = setup_logging(config)
        logger.info(f"Starting sales report generation in {'TEST' if test_mode else 'PRODUCTION'} mode")
        
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
        sales_analytics = SalesAnalytics()
        
        # Process data
        logger.info("Processing sales data")
        try:
            # Get sales data and created files
            sales_data, created_files = data_processor.process_data()
            logger.info(f"Created {len(created_files)} report files")
            for file in created_files:
                logger.info(f"Created file: {file}")
                if not file.endswith('.xlsx'):
                    logger.warning(f"Unexpected file extension for {file} - should be .xlsx")
            
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
        
        # Send management report (removed test_mode condition)
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

def print_summary(start_time: datetime, success: bool, test_mode: bool) -> None:
    """Print execution summary"""
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\nExecution Summary:")
    print(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
    print(f"Status: {'SUCCESS' if success else 'FAILURE'}")
    print(f"Started at: {start_time:%Y-%m-%d %H:%M:%S}")
    print(f"Ended at: {end_time:%Y-%m-%d %H:%M:%S}")
    print(f"Total duration: {duration}")

def main():
    """Main entry point for the application"""
    start_time = datetime.now()
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Generate and send sales reports (Excel .xlsx format)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              Run in production mode:
                python main.py
              
              Run in test mode:
                python main.py --test
              
              Run with specific config:
                python main.py --config path/to/config.json
              
              Run in test mode with specific config:
                python main.py --test --config path/to/config.json
        """)
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file'
    )
    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help='Run in test mode (sends emails only to test address)'
    )
    
    args = parser.parse_args()
    
    # Run with parsed arguments
    if args.test:
        print("Running in TEST mode - emails will only be sent to test address")
    success = run_sales_report(config_path=args.config, test_mode=args.test)
    
    # Print summary
    print_summary(start_time, success, args.test)
    
    # Set exit code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()