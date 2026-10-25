import json

import pytest

from src import analysis, cli, disclaimer
from src.http_client import NetworkUnavailableError, ProviderTimeoutError


@pytest.fixture
def fake_providers(monkeypatch, geo_payload):
    def fetch_json(url, _timeout):
        if "ipwho.is" in url:
            return geo_payload
        return {"is_vpn": False, "is_proxy": False, "is_tor": False, "is_datacenter": False}

    original = analysis.analyze

    def patched(target, **kwargs):
        kwargs["fetch_json"] = fetch_json
        kwargs["fetch_text"] = lambda _u, _t: "1.2.3.4\n"
        return original(target, **kwargs)

    monkeypatch.setattr(cli.analysis, "analyze", patched)


def test_help(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--ip" in out and "--self" in out and "--json" in out
    assert "Developed by Abiye Enzo (@abiyeenzo)" in out


def test_version(capsys):
    assert cli.main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "IPInsight CLI 1.2.0" in out and "@abiyeenzo" in out


def test_disclaimer_option(capsys):
    assert cli.main(["--disclaimer", "--no-color"]) == 0
    assert "approximative" in capsys.readouterr().out.replace("\n", " ")


def test_json_analysis(fake_providers, capsys):
    assert cli.main(["--ip", "8.8.8.8", "--json"]) == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)  # stdout = JSON pur
    assert data["ip"] == "8.8.8.8" and data["country_code"] == "US"
    assert "Avertissement" in captured.err  # avertissement du premier lancement sur stderr


def test_first_run_warning_shown_once(fake_providers, capsys):
    cli.main(["--ip", "8.8.8.8", "--json"])
    assert "Avertissement" in capsys.readouterr().err
    assert disclaimer.already_shown()
    cli.main(["--ip", "8.8.8.8", "--json"])
    assert "Avertissement" not in capsys.readouterr().err


def test_terminal_analysis_no_color(fake_providers, capsys):
    assert cli.main(["--ip", "8.8.8.8", "--no-color"]) == 0
    out = capsys.readouterr().out
    assert "Mountain View" in out and "https://www.google.com/maps?q=" in out
    assert "\x1b[" not in out


def test_self_mode(fake_providers, capsys):
    assert cli.main(["--self", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ip"] == "8.8.8.8"


def test_invalid_ip_exit_code(no_network, monkeypatch, capsys):
    monkeypatch.setattr("src.geolocation.get_json", no_network)
    assert cli.main(["--ip", "999.1.1.1", "--no-color"]) == 2
    assert "mal formée" in capsys.readouterr().out


def test_invalid_ip_json(capsys):
    assert cli.main(["--ip", "nope", "--json"]) == 2
    data = json.loads(capsys.readouterr().out)
    assert data["error_type"] == "invalid_ip"


def test_private_ip_makes_no_request(no_network, monkeypatch, capsys):
    original = analysis.analyze

    def guarded(target, **kwargs):
        return original(target, fetch_json=no_network, fetch_text=no_network, **kwargs)

    monkeypatch.setattr(cli.analysis, "analyze", guarded)
    assert cli.main(["--ip", "192.168.0.1", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["ip_scope"] == "private"


@pytest.mark.parametrize(
    "exc,expected",
    [(NetworkUnavailableError("hors ligne"), "network_unavailable"), (ProviderTimeoutError("lent"), "timeout")],
)
def test_provider_errors_give_no_fake_result(monkeypatch, capsys, exc, expected):
    def failing(_url, _timeout):
        raise exc

    original = analysis.analyze
    monkeypatch.setattr(cli.analysis, "analyze", lambda t, **kw: original(t, fetch_json=failing, fetch_text=failing, **kw))
    assert cli.main(["--ip", "8.8.8.8", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["error_type"] == expected
    assert "latitude" not in data and "country" not in data


def test_offline_terminal_message(monkeypatch, capsys):
    def failing(_url, _timeout):
        raise NetworkUnavailableError("hors ligne")

    original = analysis.analyze
    monkeypatch.setattr(cli.analysis, "analyze", lambda t, **kw: original(t, fetch_json=failing, fetch_text=failing, **kw))
    assert cli.main(["--ip", "8.8.8.8", "--no-color"]) == 1
    out = capsys.readouterr().out
    assert "Réseau indisponible" in out and "jamais inventées" in out


def test_no_anonymity_flag(fake_providers, capsys):
    assert cli.main(["--ip", "8.8.8.8", "--json", "--no-anonymity"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["source"]["anonymity"] == [] and data["anonymity_status"] == "indeterminate"


def test_conflicting_targets_rejected():
    with pytest.raises(SystemExit) as exc:
        cli.main(["--ip", "8.8.8.8", "--self"])
    assert exc.value.code == 2


def test_negative_timeout_rejected():
    with pytest.raises(SystemExit):
        cli.main(["--ip", "8.8.8.8", "--timeout", "0"])


def test_no_args_without_tty_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_interactive_session(fake_providers, monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    answers = iter(["8.8.8.8", "bad-ip", "disclaimer", "help", "quit"])
    monkeypatch.setattr("rich.console.Console.input", lambda self, *_a, **_k: next(answers))
    assert cli.main(["--no-color"]) == 0
    out = capsys.readouterr().out
    assert "Mountain View" in out and "mal formée" in out and "Avertissement d'usage" in out


def test_keyboard_interrupt(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.analysis, "analyze", boom)
    assert cli.main(["--ip", "8.8.8.8", "--json"]) == 130
    assert "Interrompu" in capsys.readouterr().err


def test_copy_and_open_map(fake_providers, monkeypatch, capsys):
    monkeypatch.setattr(cli.maps, "copy_to_clipboard", lambda _t: True)
    monkeypatch.setattr(cli.maps, "open_in_browser", lambda _u: False)
    assert cli.main(["--ip", "8.8.8.8", "--no-color", "--copy-map", "--open-map"]) == 0
    out = capsys.readouterr().out
    assert "presse-papiers" in out and "Impossible d'ouvrir" in out


def test_output_json_and_text_files(fake_providers, tmp_path, capsys):
    json_dest = tmp_path / "sub" / "rapport.json"
    assert cli.main(["--ip", "8.8.8.8", "--json", "-o", str(json_dest)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["ip"] == "8.8.8.8"
    assert "Rapport enregistré" in captured.err
    saved_json = json.loads(json_dest.read_text(encoding="utf-8"))
    assert saved_json["ip"] == "8.8.8.8"

    txt_dest = tmp_path / "rapport.txt"
    assert cli.main(["--ip", "8.8.8.8", "--no-color", "--output", str(txt_dest)]) == 0
    saved_txt = txt_dest.read_text(encoding="utf-8")
    assert "Mountain View" in saved_txt and "\x1b[" not in saved_txt


def test_output_write_failure_is_reported(fake_providers, tmp_path, capsys):
    assert cli.main(["--ip", "8.8.8.8", "--no-color", "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Impossible d'enregistrer" in out


def test_rdap_cli_flag(monkeypatch, geo_payload, capsys):
    def fetch_json(url, _timeout):
        if "rdap.org" in url:
            return {"handle": "NET-8-8-8-0-2", "name": "GOGL", "country": "US", "port43": "whois.arin.net"}
        if "ipwho.is" in url:
            return geo_payload
        return {"is_vpn": False, "is_proxy": False, "is_tor": False, "is_datacenter": False}

    original = analysis.analyze
    monkeypatch.setattr(
        cli.analysis,
        "analyze",
        lambda t, **kw: original(t, fetch_json=fetch_json, fetch_text=lambda _u, _t: "", **kw),
    )
    assert cli.main(["--ip", "8.8.8.8", "--rdap", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["rdap"]["handle"] == "NET-8-8-8-0-2"
    assert data["rdap"]["registry"] == "ARIN"


def test_frozen_stdio_reconfiguration(monkeypatch):
    calls = []

    class DummyStream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "stdout", DummyStream())
    monkeypatch.setattr(cli.sys, "stderr", DummyStream())
    cli._configure_frozen_stdio()
    assert len(calls) == 2 and all(c.get("encoding") == "utf-8" for c in calls)

