# Sales Report Application

## Setup

1. Clone the repository:
```bash
git clone [your-repository-url]
cd [repository-name]
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure environment variables:
   - Copy `.env.template` to `.env`
   - Fill in your SendGrid API key and email configurations
```bash
cp .env.template .env
```

4. Update the paths in `config.json` to match your local setup.

## Running the Application

### Basic Usage
```bash
python main.py
```

### Test Mode
Test mode provides several features for development and testing:
- Sends emails only to the test email address specified in `.env`
- Enables more detailed DEBUG level logging
- Creates logs with 'TEST' prefix
- Skips environment variable validation
- Log files are created in `reports/logs` with format: `sales_report_TEST_YYYYMMDD_HHMMSS.log`

To run in test mode:
```bash
python main.py --test
```

### Configuration Options
- Use a specific config file:
```bash
python main.py --config path/to/config.json
```

- Combine test mode with specific config:
```bash
python main.py --test --config path/to/config.json
```

## Configuration

- `config.json`: Contains non-sensitive configuration like paths and budgets
- `.env`: Contains sensitive information like API keys and email addresses
- `config.py`: Main configuration handler that combines both sources

### Environment Variables
Required environment variables:
- `SENDGRID_API_KEY`: Your SendGrid API key (required in production mode)
- `AE_EMAILS_*`: Email lists for each Account Executive
- `TEST_EMAIL`: Email address for test mode
- `SENDER_EMAIL`: Email address used as sender

## Logging
- Log files are created in the `reports/logs` directory
- Log filename format: `sales_report_[MODE]_[TIMESTAMP].log`
- Production mode uses INFO level logging
- Test mode uses DEBUG level logging for more detailed output

## Development

- The application uses environment variables for sensitive information
- Never commit the `.env` file to the repository
- Update `.env.template` when adding new environment variables
- Keep email addresses and API keys in `.env` file only

## Exit Codes
- 0: Successful execution
- 1: Error occurred during execution