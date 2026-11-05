from pathlib import Path

import pytest
from conftest import FAKE_CLIENT_ID, FAKE_CLIENT_SECRET

from roomsync.settings import Settings, SettingsError, load_settings


@pytest.mark.usefixtures("panopto_env")
def test_loads_from_environment() -> None:
    settings = load_settings()
    assert str(settings.panopto_base_url).startswith("https://panopto.example.edu")
    assert settings.panopto_client_id == FAKE_CLIENT_ID
    assert settings.panopto_client_secret.get_secret_value() == FAKE_CLIENT_SECRET
    assert settings.dry_run is True


@pytest.mark.usefixtures("panopto_env")
def test_dry_run_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOMSYNC_DRY_RUN", "0")
    assert load_settings().dry_run is False


def test_missing_values_name_every_variable() -> None:
    with pytest.raises(SettingsError) as info:
        load_settings()
    assert info.value.variables == [
        "ROOMSYNC_PANOPTO_BASE_URL",
        "ROOMSYNC_PANOPTO_CLIENT_ID",
        "ROOMSYNC_PANOPTO_CLIENT_SECRET",
    ]
    assert "ROOMSYNC_PANOPTO_CLIENT_SECRET" in str(info.value)


def test_missing_secret_alone_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOMSYNC_PANOPTO_BASE_URL", "https://panopto.example.edu")
    monkeypatch.setenv("ROOMSYNC_PANOPTO_CLIENT_ID", FAKE_CLIENT_ID)
    with pytest.raises(SettingsError) as info:
        load_settings()
    assert info.value.variables == ["ROOMSYNC_PANOPTO_CLIENT_SECRET"]


@pytest.mark.usefixtures("panopto_env")
def test_invalid_url_is_reported_without_other_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOMSYNC_PANOPTO_BASE_URL", "not a url")
    with pytest.raises(SettingsError) as info:
        load_settings()
    assert info.value.variables == ["ROOMSYNC_PANOPTO_BASE_URL"]
    assert FAKE_CLIENT_SECRET not in str(info.value)


def test_reads_dotenv_in_working_directory(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "ROOMSYNC_PANOPTO_BASE_URL=https://panopto.example.edu\n"
        f"ROOMSYNC_PANOPTO_CLIENT_ID={FAKE_CLIENT_ID}\n"
        f"ROOMSYNC_PANOPTO_CLIENT_SECRET={FAKE_CLIENT_SECRET}\n"
    )
    assert load_settings().panopto_client_id == FAKE_CLIENT_ID


@pytest.mark.usefixtures("panopto_env")
def test_secret_not_in_repr_or_str(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings()  # type: ignore[call-arg]
    print(settings)
    print(repr(settings))
    print(settings.model_dump())
    print(settings.model_dump_json())
    out = capsys.readouterr().out
    assert FAKE_CLIENT_SECRET not in out
    assert FAKE_CLIENT_SECRET not in repr(settings)
    assert FAKE_CLIENT_SECRET not in str(settings)


@pytest.mark.usefixtures("panopto_env")
def test_plain_http_base_url_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # The token request posts the client secret, so it must never go over plain http.
    monkeypatch.setenv("ROOMSYNC_PANOPTO_BASE_URL", "http://panopto.example.edu")
    with pytest.raises(SettingsError) as info:
        load_settings()
    assert info.value.variables == ["ROOMSYNC_PANOPTO_BASE_URL"]
    assert "https" in str(info.value)
