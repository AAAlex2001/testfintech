import os
import sys

os.environ.update(
    {
        "CDS_URL": "http://test-cds.com",
        "CDS_AUTH_TOKEN": "test-cds-token",
        "SBANK_API_BASE_URL": "http://test-sbank-api.com",
        "SBANK_RADMIN_BASE_URL": "http://test-sbank-radmin.com",
        "SBANK_API_AUTH_TOKEN": "test-sbank-token",
    }
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
