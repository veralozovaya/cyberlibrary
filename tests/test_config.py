from cyberlibrary.config import load_config


def test_load_config_reads_ebooks_token(monkeypatch):
    test_token = "lib_20260101_test0000000000000000"  #gitleaks:allow
    monkeypatch.setenv("EBOOKS_API_TOKEN", test_token)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")

    cfg = load_config()
    assert cfg["EBOOKS_API_TOKEN"].startswith("lib_20260101_")
