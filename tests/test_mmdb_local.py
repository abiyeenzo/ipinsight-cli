import json

import pytest

from src import analysis, cli, local_db
from src.mmdb import MMDBError, MMDBReader
from tests.mmdb_writer import build_mmdb, city_record

PARIS = city_record(48.8566, 2.3522, country="France", iso="FR", region="Ile-de-France", city="Paris", radius=20)
ENTRIES = [
    ("8.8.8.0/24", city_record(37.386, -122.0838, country="United States", iso="US", region="California", city="Mountain View", radius=1000)),
    ("1.2.3.0/24", PARIS),
    ("100.64.0.0/10", city_record(10.0, 10.0)),
]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test-city.mmdb"
    path.write_bytes(build_mmdb(ENTRIES, database_type="DBIP-City-Lite"))
    return path


@pytest.mark.parametrize("record_size", [24, 28, 32])
@pytest.mark.parametrize("ip_version", [4, 6])
def test_reader_lookup_all_formats(tmp_path, record_size, ip_version):
    path = tmp_path / "db.mmdb"
    path.write_bytes(build_mmdb(ENTRIES, ip_version=ip_version, record_size=record_size))
    with MMDBReader(path) as reader:
        assert reader.ip_version == ip_version and reader.record_size == record_size
        record = reader.get("1.2.3.77")
        assert record["city"]["names"]["en"] == "Paris"
        assert record["location"]["latitude"] == pytest.approx(48.8566)
        assert record["location"]["accuracy_radius"] == 20
        assert reader.get("8.8.8.8")["country"]["iso_code"] == "US"
        assert reader.get("9.9.9.9") is None          # absente
        assert reader.get("1.2.4.1") is None          # hors du /24


def test_reader_ipv6_in_ipv6_database(tmp_path):
    entries = ENTRIES + [("2001:db8::/32", city_record(1.5, 2.5, country="Doc", iso="DC"))]
    path = tmp_path / "v6.mmdb"
    path.write_bytes(build_mmdb(entries, ip_version=6))
    with MMDBReader(path) as reader:
        assert reader.get("2001:db8::1")["country"]["iso_code"] == "DC"
        assert reader.get("2001:db9::1") is None


def test_ipv6_in_ipv4_database_is_not_found(db_path):
    with MMDBReader(db_path) as reader:
        assert reader.get("2001:db8::1") is None


def test_metadata(db_path):
    with MMDBReader(db_path) as reader:
        assert reader.database_type == "DBIP-City-Lite"
        assert reader.build_epoch == 1_700_000_000


def test_reader_rejects_bad_files(tmp_path):
    missing = tmp_path / "absent.mmdb"
    with pytest.raises(MMDBError):
        MMDBReader(missing)
    empty = tmp_path / "empty.mmdb"
    empty.write_bytes(b"")
    with pytest.raises(MMDBError):
        MMDBReader(empty)
    garbage = tmp_path / "garbage.mmdb"
    garbage.write_bytes(b"not a database " * 50)
    with pytest.raises(MMDBError):
        MMDBReader(garbage)


def test_reader_rejects_truncated_database(tmp_path, db_path):
    data = db_path.read_bytes()
    truncated = tmp_path / "trunc.mmdb"
    truncated.write_bytes(data[:20] + data[-120:])
    with pytest.raises(MMDBError):
        with MMDBReader(truncated) as reader:
            reader.get("1.2.3.4")


def test_reader_rejects_invalid_ip(db_path):
    with MMDBReader(db_path) as reader:
        with pytest.raises(ValueError):
            reader.get("not-an-ip")


def test_family_detection():
    assert local_db.detect_family("GeoLite2-City") == "maxmind"
    assert local_db.detect_family("GeoIP2-City") == "maxmind"
    assert local_db.detect_family("DBIP-City-Lite") == "dbip"
    assert local_db.detect_family("DB-IP City Lite").startswith("dbip")
    assert local_db.detect_family("Mystery").startswith("unverified")
    assert local_db.detect_family("").startswith("unverified")


def test_local_lookup_fields(db_path):
    (db,), errors = local_db.open_databases([db_path])
    try:
        assert errors == []
        result = local_db.lookup(db, "1.2.3.4")
        assert result.country == "France" and result.country_code == "FR"
        assert result.region == "Ile-de-France" and result.city == "Paris"
        assert (result.latitude, result.longitude) == (48.8566, 2.3522)
        assert result.accuracy_radius_km == 20.0
        assert result.kind == "local" and result.family == "dbip"
        assert result.database_date == "2023-11-14"
        assert result.source == "base locale test-city.mmdb"
        assert local_db.lookup(db, "9.9.9.9") is None
    finally:
        local_db.close_all([db])


def test_local_record_with_invalid_coordinates(tmp_path):
    path = tmp_path / "bad.mmdb"
    path.write_bytes(build_mmdb([("5.5.5.0/24", city_record(123.0, 10.0))], database_type="GeoLite2-City"))
    (db,), _ = local_db.open_databases([path])
    try:
        result = local_db.lookup(db, "5.5.5.5")
        assert result.point is None
        assert "coordinates_out_of_range" in {i.code for i in result.issues}
    finally:
        local_db.close_all([db])


def test_open_databases_reports_bad_files_without_stopping(tmp_path, db_path):
    bad = tmp_path / "bad.mmdb"
    bad.write_bytes(b"x" * 100)
    databases, errors = local_db.open_databases([bad, db_path])
    try:
        assert len(databases) == 1
        assert len(errors) == 1 and "bad.mmdb" in errors[0]
    finally:
        local_db.close_all(databases)


def test_staleness_note(tmp_path):
    path = tmp_path / "old.mmdb"
    path.write_bytes(build_mmdb(ENTRIES, build_epoch=1_500_000_000))
    (db,), _ = local_db.open_databases([path])
    try:
        assert "périmées" in local_db.staleness_note(db)
    finally:
        local_db.close_all([db])


def test_offline_analysis_makes_no_network_request(db_path, no_network):
    (db,), _ = local_db.open_databases([db_path])
    try:
        report = analysis.analyze("1.2.3.4", offline=True, databases=[db], fetch_json=no_network, fetch_text=no_network)
    finally:
        local_db.close_all([db])
    assert report.location.city == "Paris"
    assert report.anonymity is None
    assert report.links is not None and report.offline is True
    assert report.comparison.status == "single_source"
    assert report.comparison.confidence.level == "low"
    assert any("hors ligne" in item for item in report.limitations)


def test_offline_address_absent_from_database(db_path, no_network):
    (db,), _ = local_db.open_databases([db_path])
    try:
        report = analysis.analyze("9.9.9.9", offline=True, databases=[db], fetch_json=no_network, fetch_text=no_network)
    finally:
        local_db.close_all([db])
    assert report.estimates == [] and report.location is None and report.links is None
    assert any("absente" in e for e in report.source_errors)
    data = report.to_dict()
    assert data["latitude"] is None and data["maps_url"] is None and data["position_status"] == "no_data"


def test_offline_self_is_refused(db_path, no_network):
    (db,), _ = local_db.open_databases([db_path])
    try:
        with pytest.raises(Exception, match="--offline"):
            analysis.analyze(None, offline=True, databases=[db], fetch_json=no_network)
    finally:
        local_db.close_all([db])


def test_cli_offline_json(db_path, capsys, monkeypatch):
    def forbidden(*_a, **_k):
        raise AssertionError("requete reseau interdite hors ligne")

    monkeypatch.setattr("src.http_client.urllib.request.urlopen", forbidden)
    assert cli.main(["--ip", "1.2.3.4", "--offline", "--mmdb", str(db_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["offline"] is True and data["city"] == "Paris"
    assert data["estimates"][0]["database_date"] == "2023-11-14"
    assert data["source"]["geolocation"] == ["base locale test-city.mmdb"]


def test_cli_offline_requires_database(capsys):
    assert cli.main(["--ip", "1.2.3.4", "--offline", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error_type"] == "no_local_database"


def test_cli_ignores_corrupt_database_but_reports_it(tmp_path, capsys):
    bad = tmp_path / "bad.mmdb"
    bad.write_bytes(b"x" * 100)
    assert cli.main(["--ip", "1.2.3.4", "--offline", "--mmdb", str(bad), "--json"]) == 2
    captured = capsys.readouterr()
    assert "Base locale ignorée" in captured.err
    assert json.loads(captured.out)["error_type"] == "no_local_database"


def test_environment_variable_paths(monkeypatch, db_path, tmp_path):
    monkeypatch.setenv(local_db.ENV_VAR, f"{db_path}{__import__('os').pathsep}{tmp_path / 'x.mmdb'}")
    assert len(local_db.paths_from_environment()) == 2
