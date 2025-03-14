from datetime import date
from re import S
from xmlrpc.client import boolean

from pydantic import BaseModel, ConfigDict, Field

from dbx_container.models.environment import SystemEnvironment


class RuntimeRelease(BaseModel):
    """Databricks Runtime release information."""

    version: str
    release_date: date | str
    end_of_support_date: date | str
    spark_version: str
    url: str
    ml_url: str


class Runtime(BaseModel):
    """Databricks Runtime version information."""

    # model_config = ConfigDict(frozen=True)
    version: str
    release_date: date | str
    end_of_support_date: date | str
    spark_version: str
    url: str
    is_ml: bool
    is_lts: bool
    system_environment: SystemEnvironment

    included_libraries: dict[str, dict[str, str | tuple[str, str]]] = Field(default_factory=dict)
