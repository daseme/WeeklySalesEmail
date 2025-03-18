import pytest
import json
import os
from config import Config


def test_load_valid_config(sample_config_path):
    """Test loading a valid configuration"""
    config = Config.load_from_json(sample_config_path)
    assert config.root_path.endswith("root")
    assert config.reports_folder.endswith("reports")
    assert config.vba_path.endswith("vba.bas")
    assert len(config.active_aes) == 1
    assert "John Doe" in config.active_aes


def test_validate_config(sample_config_path, test_env_vars):  # Added test_env_vars
    """Test configuration validation"""
    config = Config.load_from_json(sample_config_path)
    # Set required environment values before validation
    config.sendgrid_api_key = "test_key"
    config.email_recipients = {
        "John Doe": ["john@example.com"]
    }  # Set directly for this test
    assert config.validate() is True


def test_invalid_config_missing_fields(invalid_config_path):
    """Test handling of missing required fields"""
    with pytest.raises(ValueError) as exc_info:
        config = Config.load_from_json(invalid_config_path).validate()
    assert "No Account Executives configured" in str(exc_info.value)


def test_invalid_config_paths(sample_config_path, tmp_path):
    """Test invalid path validation"""
    config = Config.load_from_json(sample_config_path)
    config.root_path = str(tmp_path / "nonexistent")
    with pytest.raises(ValueError) as exc_info:
        config.validate()
    assert "Root path does not exist" in str(exc_info.value)


def test_email_validation(sample_config_path, test_env_vars):  # Added test_env_vars
    """Test email format validation"""
    config = Config.load_from_json(sample_config_path)
    # Set up valid environment first
    config.sendgrid_api_key = "test_key"
    config.email_recipients = {"John Doe": ["john@example.com"]}
    assert config.validate() is True  # Verify valid config first
    # Now test invalid email
    config.sender_email = "invalid-email"
    with pytest.raises(ValueError) as exc_info:
        config.validate()
    assert "Invalid sender email" in str(exc_info.value)


def test_test_mode_configuration(test_mode_config_path, test_env_vars):
    """Test test mode settings"""
    config = Config.load_from_json(test_mode_config_path)
    assert config.test_mode is True
    assert config.test_email == "test@example.com"
    # Set the test email recipients directly for test mode
    config.email_recipients = {"John Doe": ["test@example.com"]}
    config.management_recipients = ["test@example.com"]
    assert config.validate() is True


def test_ae_budget_validation(sample_config_path):
    """Test AE budget validation"""
    config = Config.load_from_json(sample_config_path)
    ae = config.account_executives["John Doe"]
    assert ae.budgets.q1 == 100000
    assert ae.budgets.q2 == 200000
    assert ae.budgets.q3 == 300000
    assert ae.budgets.q4 == 400000


def test_environment_variables(sample_config_path, test_env_vars):
    """Test environment variable integration"""
    config = Config.load_from_json(sample_config_path)
    print("Active AEs:", config.active_aes)  # Debug print
    print("Environment variables:", test_env_vars)  # Debug print
    print("Current env value:", os.getenv("AE_EMAILS_JOHN_DOE"))  # Debug print
    config.email_recipients = config._load_email_recipients(config.active_aes)
    assert config.sendgrid_api_key == "test_key"
    assert config.sender_email == "test@example.com"
    assert config.email_recipients["John Doe"] == [
        "john@example.com",
        "john.sales@example.com",
    ]


def test_config_raises_on_missing_file():
    """Test file not found handling"""
    with pytest.raises(FileNotFoundError):
        Config.load_from_json("nonexistent.json")


def test_config_raises_on_invalid_json(tmp_path):
    """Test invalid JSON handling"""
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{invalid json")
    with pytest.raises(json.JSONDecodeError):
        Config.load_from_json(str(invalid_json))
