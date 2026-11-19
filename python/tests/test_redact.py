from platform_toolkit.redact import redact


def test_key_value_secrets():
    out = redact("DB_PASSWORD=hunter2 api_key: abc123 user=bob")
    assert "hunter2" not in out and "abc123" not in out
    assert "user=bob" in out


def test_bearer_and_jwt():
    out = redact("Authorization: Bearer eyJhbGciOi.eyJzdWIi.sig-part")
    assert "eyJ" not in out


def test_pem_block():
    pem = "-----BEGIN PRIVATE KEY-----\nMIIEv\n-----END PRIVATE KEY-----"
    assert redact(pem) == "[REDACTED_PEM]"


def test_plain_text_untouched():
    line = "GET /healthz 200 in 3ms"
    assert redact(line) == line
