# tests/conftest.py
import pytest
import json
import os
from pathlib import Path


@pytest.fixture
def sample_config_path(tmp_path):
    """Fixture for valid configuration"""
    # Create required directories
    root_path = tmp_path / "root"
    reports_path = tmp_path / "reports"
    vba_path = tmp_path / "vba.bas"

    root_path.mkdir()
    reports_path.mkdir()
    vba_path.write_text("")

    config_data = {
        "root_path": str(root_path),
        "reports_folder": str(reports_path),
        "vba_path": str(vba_path),
        "account_executives": {
            "John Doe": {
                "enabled": True,
                "budgets": {"q1": 100000, "q2": 200000, "q3": 300000, "q4": 400000},
            }
        },
        "management_recipients": ["manager@example.com"],
        "test_mode": False,
        "test_email": "test@example.com",
    }

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data))
    return str(config_file)


@pytest.fixture
def test_mode_config_path(tmp_path):
    """Fixture for test mode configuration"""
    root_path = tmp_path / "root"
    reports_path = tmp_path / "reports"
    vba_path = tmp_path / "vba.bas"

    root_path.mkdir()
    reports_path.mkdir()
    vba_path.write_text("")

    config_data = {
        "root_path": str(root_path),
        "reports_folder": str(reports_path),
        "vba_path": str(vba_path),
        "account_executives": {
            "John Doe": {
                "enabled": True,
                "budgets": {"q1": 100000, "q2": 200000, "q3": 300000, "q4": 400000},
            }
        },
        "management_recipients": ["test@example.com"],
        "test_mode": True,
        "test_email": "test@example.com",
        "email_recipients": {"John Doe": ["test@example.com"]},
    }

    config_file = tmp_path / "test_mode_config.json"
    config_file.write_text(json.dumps(config_data))
    return str(config_file)


@pytest.fixture
def invalid_config_path(tmp_path):
    """Fixture for invalid configuration"""
    root_path = tmp_path / "root"
    root_path.mkdir()

    # Create VBA file
    vba_path = tmp_path / "vba.bas"
    vba_path.write_text("")

    config_data = {
        "root_path": str(root_path),
        "reports_folder": str(tmp_path / "reports"),
        "vba_path": str(vba_path),
        # Intentionally empty account_executives
        "account_executives": {},
    }
    config_file = tmp_path / "invalid_config.json"
    config_file.write_text(json.dumps(config_data))
    return str(config_file)


@pytest.fixture
def test_env_vars(monkeypatch):
    """Fixture for environment variables"""
    test_vars = {
        "SENDGRID_API_KEY": "test_key",
        "SENDER_EMAIL": "test@example.com",
        "TEST_EMAIL": "test@example.com",
        "AE_EMAILS_JOHN_DOE": "john@example.com,john.sales@example.com",
    }
    for key, value in test_vars.items():
        monkeypatch.setenv(key, value)
    return test_vars
