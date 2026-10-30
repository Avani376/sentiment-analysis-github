"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.registry import ModelRegistry, get_registry

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def registry_dep() -> Generator[ModelRegistry, None, None]:
    yield get_registry()


RegistryDep = Annotated[ModelRegistry, Depends(registry_dep)]
