from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class PmproxyConfig(BaseSettings):
    url: AnyHttpUrl
    timeout: float = 30.0
    health_interval: int = 15

    model_config = {"env_prefix": "PMPROXY_"}
