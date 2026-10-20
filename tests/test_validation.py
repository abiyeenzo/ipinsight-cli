import pytest

from src.validation import InvalidIPError, classify_ip


@pytest.mark.parametrize("text,version", [("8.8.8.8", 4), ("1.1.1.1", 4), ("2001:4860:4860::8888", 6)])
def test_public_addresses(text, version):
    result = classify_ip(text)
    assert result.is_public and result.version == version and result.scope == "public"


@pytest.mark.parametrize(
    "text,scope",
    [
        ("192.168.1.10", "private"),
        ("10.0.0.1", "private"),
        ("172.16.5.4", "private"),
        ("127.0.0.1", "loopback"),
        ("::1", "loopback"),
        ("169.254.1.1", "link_local"),
        ("224.0.0.1", "multicast"),
        ("0.0.0.0", "unspecified"),
        ("240.0.0.1", "private"),
        ("100.64.0.1", "non_routable"),
        ("fe80::1", "link_local"),
        ("fd00::1", "private"),
    ],
)
def test_non_public_addresses(text, scope):
    result = classify_ip(text)
    assert not result.is_public
    assert result.scope == scope


def test_ipv4_mapped_ipv6_is_unwrapped():
    assert classify_ip("::ffff:8.8.8.8").address == "8.8.8.8"
    assert not classify_ip("::ffff:192.168.0.1").is_public


def test_whitespace_is_stripped():
    assert classify_ip("  8.8.8.8\n").address == "8.8.8.8"


@pytest.mark.parametrize(
    "text",
    ["", "   ", "999.1.1.1", "8.8.8", "abc", "8.8.8.8/24", "fe80::1%eth0", "8.8.8.8; rm -rf /", "1" * 60, "2001:::1"],
)
def test_invalid_inputs_rejected(text):
    with pytest.raises(InvalidIPError):
        classify_ip(text)


def test_non_string_rejected():
    with pytest.raises(InvalidIPError):
        classify_ip(None)  # type: ignore[arg-type]
