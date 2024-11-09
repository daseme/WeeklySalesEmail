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

## Development

- The application uses environment variables for sensitive information
- Never commit the `.env` file to the repository
- Update `.env.template` when adding new environment variables
- Keep email addresses and API keys in `.env` file only

## Configuration

- `config.json`: Contains non-sensitive configuration like paths and budgets
- `.env`: Contains sensitive information like API keys and email addresses
- `config.py`: Main configuration handler that combines both sources

## Testing

To run in test mode:
```python
config = Config.load_default(test_mode=True)
```
This will send emails only to the test email address specified in `.env`.