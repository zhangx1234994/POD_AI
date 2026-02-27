from app.services.agent_management import AgentTokenService


def test_parse_secrets_supports_kid_secret_pairs() -> None:
    secrets = AgentTokenService._parse_secrets("k1:s1,k2:s2")
    assert secrets["k1"] == "s1"
    assert secrets["k2"] == "s2"


def test_get_keyset_returns_active_entries() -> None:
    svc = AgentTokenService()
    keyset = svc.get_keyset()
    assert keyset
    assert all(item.get("kid") for item in keyset)
    assert all(item.get("secret") for item in keyset)
