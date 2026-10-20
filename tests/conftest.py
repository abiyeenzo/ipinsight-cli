import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Isole le dossier de configuration et supprime le délai anti-rafale."""
    monkeypatch.setenv("IPINSIGHT_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr("src.http_client.MIN_INTERVAL_SECONDS", 0.0)


@pytest.fixture
def geo_payload():
    return {
        "ip": "8.8.8.8",
        "success": True,
        "country": "United States",
        "country_code": "US",
        "region": "California",
        "city": "Mountain View",
        "latitude": 37.3860517,
        "longitude": -122.0838511,
        "connection": {"asn": 15169, "org": "Google LLC", "isp": "Google LLC", "domain": "google.com"},
        "timezone": {"id": "America/Los_Angeles"},
    }


@pytest.fixture
def no_network():
    def _raise(*_args, **_kwargs):
        raise AssertionError("Requête réseau inattendue")

    return _raise
