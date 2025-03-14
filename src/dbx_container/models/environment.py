from pydantic import BaseModel, ConfigDict


class SystemEnvironment(BaseModel):
    """Information about the system environment in a Databricks runtime."""

    # model_config = ConfigDict(frozen=True)

    operating_system: str
    java_version: str
    scala_version: str
    python_version: str
    r_version: str
    delta_lake_version: str
