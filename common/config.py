"""
Configuration management for MCP DevOps Tools
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class KibanaConfig:
    """Kibana configuration"""
    url: str
    username: str
    password: str

    @classmethod
    def from_env(cls) -> "KibanaConfig":
        return cls(
            url=os.getenv("KIBANA_URL", ""),
            username=os.getenv("KIBANA_USERNAME", ""),
            password=os.getenv("KIBANA_PASSWORD", "")
        )


@dataclass
class ArcheryConfig:
    """Archery configuration"""
    url: str
    username: str
    password: str

    @classmethod
    def from_env(cls) -> "ArcheryConfig":
        return cls(
            url=os.getenv("ARCHERY_URL", ""),
            username=os.getenv("ARCHERY_USERNAME", ""),
            password=os.getenv("ARCHERY_PASSWORD", "")
        )


@dataclass
class DorisConfig:
    """Doris configuration"""
    host: str
    port: int
    username: str
    password: str

    @classmethod
    def from_env(cls) -> "DorisConfig":
        return cls(
            host=os.getenv("DORIS_HOST", ""),
            port=int(os.getenv("DORIS_PORT", "9030")),
            username=os.getenv("DORIS_USERNAME", ""),
            password=os.getenv("DORIS_PASSWORD", "")
        )


class Config:
    """Main configuration class"""

    def __init__(self):
        self.kibana = KibanaConfig.from_env()
        self.archery = ArcheryConfig.from_env()
        self.doris = DorisConfig.from_env()
        self.server_port = int(os.getenv("MCP_SERVER_PORT", "8000"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

    def validate_kibana(self) -> bool:
        """Check if Kibana config is valid"""
        return bool(self.kibana.url and self.kibana.username and self.kibana.password)

    def validate_archery(self) -> bool:
        """Check if Archery config is valid"""
        return bool(self.archery.url and self.archery.username and self.archery.password)

    def validate_doris(self) -> bool:
        """Check if Doris config is valid"""
        return bool(self.doris.host and self.doris.username and self.doris.password)
