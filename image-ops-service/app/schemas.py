from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImageOpsRequest(BaseModel):
    imageBase64: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class ImageOpsResponse(BaseModel):
    contentBase64: str
    contentType: str
    fileExt: str
