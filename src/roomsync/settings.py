"""The one place roomsync reads configuration. Values come from ROOMSYNC_* variables or `.env`, never os.environ."""

from typing import Annotated

from pydantic import AnyUrl, SecretStr, UrlConstraints, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "ROOMSYNC_"

HttpsUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["https"], host_required=True)]
"""The token request posts the client secret, so the platform URL must be https."""


class Settings(BaseSettings):
    """Platform credentials and the dry-run switch. The Panopto fields have no defaults on purpose."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, env_file=".env", extra="ignore", frozen=True)

    panopto_base_url: HttpsUrl
    panopto_client_id: str
    panopto_client_secret: SecretStr
    dry_run: bool = True


class SettingsError(Exception):
    """Settings are missing or invalid. Carries variable names only, never the values."""

    def __init__(self, variables: list[str], reasons: list[str]) -> None:
        self.variables = variables
        lines = [f"  {name}: {reason}" for name, reason in zip(variables, reasons, strict=True)]
        super().__init__("roomsync settings are missing or invalid (set them in .env):\n" + "\n".join(lines))


def load_settings() -> Settings:
    """Load Settings, turning a validation error into a SettingsError that names the ROOMSYNC_ variables."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        variables: list[str] = []
        reasons: list[str] = []
        for error in exc.errors(include_input=False, include_url=False):
            field = str(error["loc"][0]) if error["loc"] else "?"
            variables.append(ENV_PREFIX + field.upper())
            reasons.append("missing" if error["type"] == "missing" else error["msg"])
        raise SettingsError(variables, reasons) from None
