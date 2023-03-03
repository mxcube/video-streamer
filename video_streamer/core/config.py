import logging
import os
import json

from typing import Dict, Union
from pydantic import BaseModel, Field, ValidationError


class SourceConfiguration(BaseModel):
    input_uri: str = Field("", description="Tango URI for input device")
    quality: int = Field(4, description="FFMpeg Quality")
    format: str = Field("MPEG1", description="Output format MPEG1 or MJPEG")
    url_prefix: str = Field("", description="Server url_prefix, default: /")


class ServerConfiguration(BaseModel):
    sources: Dict[str, SourceConfiguration]


def get_config(fpath: str) -> Union[ServerConfiguration, None]:
    data = None

    if os.path.isfile(fpath):
        with open(fpath, "r") as _f:
            config_data = json.load(_f)

            try:
                data = ServerConfiguration(**config_data)
            except ValidationError:
                logging.exception(f"Validation error in {fpath}")

    return data
