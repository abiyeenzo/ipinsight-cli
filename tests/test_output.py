import io
import json

from rich.console import Console

from src import analysis, output
from src.disclaimer import WARNING_TEXT
from src.models import AnonymityResult

OK_ANON = {"is_vpn": False, "is_proxy": False, "is_tor": False, "is_datacenter": False}


def _fetch_json(geo_payload, anon_payload=OK_ANON):
    def fetch(url, _timeout):
        return geo_payload if "ipwho.is" in url else anon_payload

    return fetch


def _report(geo_payload, **kwargs):
    return analysis.analyze(
        "8.8.8.8",
        fetch_json=_fetch_json(geo_payload, kwargs.pop("anon", OK_ANON)),
        fetch_text=lambda _u, _t: "1.2.3.4\n",
        **kwargs,
    )


def _render(report, no_color=True):
    buffer = io.StringIO()
    console = Console(file=buffer, no_color=no_color, color_system=None if no_color else "standard", width=110, force_terminal=not no_color)
    output.render_report(console, report)
    return buffer.getvalue()


def test_json_contains_required_fields(geo_payload):
    data = json.loads(output.to_json(_report(geo_payload)))
    for key in (
        "ip", "country", "region", "city", "latitude", "longitude", "accuracy_radius_km", "isp", "asn",
        "vpn_detected", "proxy_detected", "tor_detected", "maps_url", "source", "timestamp", "limitations",
    ):
        assert key in data
    assert data["ip"] == "8.8.8.8"
    assert data["asn"] == 15169
    assert data["maps_url"].startswith("https://www.google.com/maps?q=37.386")
    assert data["accuracy_radius_km"] is None
    assert data["vpn_detected"] is None  # absence d'indicateur != absence de VPN
    assert data["anonymity_status"] == "no_indicator_found"
    assert data["source"]["geolocation"] == "ipwho.is"
    assert data["timestamp"].endswith("+00:00")
    assert any("approximative" in item for item in data["limitations"])


def test_json_roundtrip_non_ascii(geo_payload):
    geo_payload["city"] = "São Paulo"
    text = output.to_json(_report(geo_payload))
    assert "São Paulo" in text
    assert json.loads(text)["city"] == "São Paulo"


def test_json_missing_fields_are_null():
    report = analysis.analyze(
        "8.8.8.8",
        fetch_json=lambda url, _t: {"ip": "8.8.8.8", "success": True} if "ipwho" in url else {},
        fetch_text=lambda _u, _t: "",
    )
    data = json.loads(output.to_json(report))
    assert data["latitude"] is None and data["longitude"] is None and data["maps_url"] is None
    assert data["country"] is None and data["isp"] is None and data["asn"] is None
    assert data["anonymity_status"] == "indeterminate"
    assert any("Coordonnées non fournies" in item for item in data["limitations"])


def test_json_vpn_flag_true(geo_payload):
    data = json.loads(output.to_json(_report(geo_payload, anon={**OK_ANON, "is_vpn": True})))
    assert data["vpn_detected"] is True
    assert data["anonymity_status"] == "indicators_found"


def test_terminal_render_sections(geo_payload):
    text = " ".join(_render(_report(geo_payload)).split())  # insensible aux retours à la ligne
    for fragment in ("Localisation estimée", "Mountain View", "AS15169", "Google Maps", "pas un GPS",
                     "inconnu (non fourni)", "non nécessairement", "Aucun indicateur trouvé dans la source consultée"):
        assert fragment in text
    assert "\x1b[" not in text  # mode sans couleur


def test_terminal_render_with_color_has_ansi(geo_payload):
    assert "\x1b[" in _render(_report(geo_payload), no_color=False)


def test_terminal_render_missing_coordinates():
    report = analysis.analyze(
        "8.8.8.8",
        fetch_json=lambda url, _t: {"ip": "8.8.8.8", "success": True} if "ipwho" in url else {},
        fetch_text=lambda _u, _t: "",
    )
    text = _render(report)
    assert "Coordonnées non fournies par la source" in text
    assert "Indéterminé : données insuffisantes" in text
    assert "maps?q=" not in text


def test_non_public_report_render_and_json(no_network):
    report = analysis.analyze("192.168.1.1", fetch_json=no_network, fetch_text=no_network)
    assert report.geo is None
    assert "non publique" in _render(report)
    data = json.loads(output.to_json(report))
    assert data["ip_scope"] == "private" and data["latitude"] is None and data["maps_url"] is None


def test_banner_and_signature():
    buffer = io.StringIO()
    output.print_banner(Console(file=buffer, no_color=True, color_system=None))
    assert "Developed by Abiye Enzo (@abiyeenzo)" in buffer.getvalue()


def test_warning_text_is_official_wording():
    assert WARNING_TEXT.startswith("Cet outil est destiné à l'apprentissage")
    assert "approximative" in WARNING_TEXT


def test_error_json():
    data = json.loads(output.error_json("boom", "timeout", "8.8.8.8"))
    assert data == {"ip": "8.8.8.8", "error": "boom", "error_type": "timeout"}


def test_anonymity_default_is_indeterminate():
    assert AnonymityResult().summary_lines() == ["Indéterminé : données insuffisantes"]
