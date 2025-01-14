import sys

from typing import Any, Dict, Optional, Union, Tuple
from pathlib import Path
from pydantic import BaseModel, Field, validate_call, FilePath
from pydantic_core import ValidationError
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

__all__ = (
    "AuthenticationConfiguration",
    "SourceConfiguration",
    "ServerConfiguration",
    "get_config_from_file",
    "get_config_from_dict",
    "get_auth_config_from_dict",
)

class AuthenticationConfiguration(BaseModel):
    """Authentication Configuration"""

    type: Union[str, None] = Field(
        title="Authentication Type",
        description="Type of authentication, supported types are 'Basic', 'Digest', None",
        default= None,
    )

    username: Union[bytes, str] = Field(
        title="Username",
        default="",
    )

    password: Union[bytes, str] = Field(
        title="Password",
        default="",
    )

class SourceConfiguration(BaseModel):
    """Source Configuration"""

    input_uri: str = Field(
        title="Input URI",
        description="URI for input device.",
        default="",
    )
    quality: int = Field(
        title="FFMpeg Quality",
        default=4,
    )
    format: str = Field(
        title="Format",
        description="Output format MPEG1 or MJPEG.",
        default="MPEG1",
    )
    hash: str = Field(
        title="Hash",
        description="Server url postfix/trail.",
        default="",
    )
    size: Tuple[int, int] = Field(
        title="Image Size",
        default=(0, 0),
    )
    redis: Optional[str] = Field(
        title="Redis URI",
        description="Redis host and port (format host:port).",
        default=None,
    )
    redis_channel: str = Field(
        title="Redis Channel",
        description="Redis-Channel to publish stream.",
        default="video-streamer",
    )
    in_redis_channel: str = Field(
        title="Input Redis Channel",
        description= "Channel for RedisCamera to listen to",
        default="CameraStream",
    )
    auth_config: AuthenticationConfiguration = Field(
        title="Authentication Configurations",
        default=AuthenticationConfiguration(type=None),
    )

class ServerConfiguration(BaseModel):
    """Server Configuration"""

    sources: Dict[str, SourceConfiguration]

    @classmethod
    @validate_call
    def model_validate_file(cls, path: FilePath, encoding: str = "utf-8") -> Self:
        """Get server configuration from file.

        Args:
            path (FilePath): Path to JSON config file.
            encoding (str, optional): File encoding. Defaults to "utf-8".

        Returns:
            Self: Server Configuration.
        """

        class _Config(BaseSettings, cls):
            """Config"""

            model_config = SettingsConfigDict(
                env_file_encoding=encoding,
            )

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: type[BaseSettings],
                init_settings: PydanticBaseSettingsSource,
                env_settings: PydanticBaseSettingsSource,
                dotenv_settings: PydanticBaseSettingsSource,
                file_secret_settings: PydanticBaseSettingsSource,
            ) -> tuple[PydanticBaseSettingsSource, ...]:  # type: ignore
                return (
                    JsonConfigSettingsSource(
                        settings_cls,
                        json_file=path,
                        json_file_encoding=encoding,
                    ),
                )

        return ServerConfiguration.model_validate(
            _Config().model_dump(warnings=False),
        )


def get_config_from_file(fpath: Union[str, Path]) -> Union[ServerConfiguration, None]:
    """Get server configuration from file.

    Args:
        fpath (str | Path): Path to JSON config file.

    Returns:
        Union[ServerConfiguration, None]: Server Configuration or None.
    """
    try:
        return ServerConfiguration.model_validate_file(path=fpath)
    except ValidationError:
        return None


def get_config_from_dict(
    config_data: Dict[str, Any],
) -> Union[ServerConfiguration, None]:
    """Get server configuration from dictionary.

    Args:
        config_data (dict[str, Any]): Configuration data.

    Returns:
        Union[ServerConfiguration, None]: Server Configuration or None.
    """
    try:
        return ServerConfiguration.model_validate(config_data)
    except ValidationError:
        return None

def get_auth_config_from_dict(
    config_data: Dict[str, Any],
) -> Union[AuthenticationConfiguration, None]:
    """Get authentication configuration from dictionary.
    
    Args:
        config_data (dict[str, Any]): Authentication Data.

    Returns:
        Union[AuthenticationConfiguration, None]: Authentication Configuration or None.
    """
    try:
        return AuthenticationConfiguration.model_validate(config_data)
    except ValidationError:
        return None