"""Outbound HTTPS trust: OUTBOUND_CA_BUNDLE, else the OS bundle, else certifi."""
from app.core import http
from app.core.config import get_settings


def test_explicit_bundle_wins(monkeypatch):
    monkeypatch.setattr(get_settings(), "outbound_ca_bundle", "/custom/ca.pem")
    assert http.tls_verify() == "/custom/ca.pem"


def test_system_bundle_is_preferred_over_certifi(monkeypatch, tmp_path):
    bundle = tmp_path / "ca-certificates.crt"
    bundle.write_text("x")
    monkeypatch.setattr(get_settings(), "outbound_ca_bundle", "")
    monkeypatch.setattr(http, "SYSTEM_CA_BUNDLES", ("/nope/ca.crt", str(bundle)))
    assert http.tls_verify() == str(bundle)


def test_falls_back_to_certifi_when_no_system_bundle(monkeypatch):
    monkeypatch.setattr(get_settings(), "outbound_ca_bundle", "")
    monkeypatch.setattr(http, "SYSTEM_CA_BUNDLES", ("/nope/ca.crt",))
    assert http.tls_verify() is True


def test_the_downloader_and_crawler_use_it(monkeypatch):
    import inspect

    from app.connectors.gem import connector
    from app.document_processing import downloader

    assert "verify=tls_verify()" in inspect.getsource(downloader.download_document)
    assert "verify=tls_verify()" in inspect.getsource(connector.GemConnector.__init__)
