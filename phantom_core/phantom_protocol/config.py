"""
Protocol configuration system

Defines configuration schema and defaults for protocol abstraction layer.
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass, field
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Configuration for a single communication channel"""

    serializer: str = "json"  # Serializer type: "json", "protobuf", "flatbuffers", etc.
    transport: str = "http"  # Transport type: "http", "grpc", "websocket", etc.
    endpoint: Optional[str] = None  # Default endpoint for this channel
    timeout: float = 30.0  # Default timeout in seconds
    options: Dict[str, Any] = field(default_factory=dict)  # Protocol-specific options

    def __post_init__(self):
        """Validate configuration"""
        valid_serializers = ["json", "protobuf", "flatbuffers", "msgpack"]
        valid_transports = ["http", "grpc", "websocket", "quic", "zeromq"]

        if self.serializer not in valid_serializers:
            logger.warning(
                f"Unknown serializer '{self.serializer}', supported: {valid_serializers}"
            )

        if self.transport not in valid_transports:
            logger.warning(
                f"Unknown transport '{self.transport}', supported: {valid_transports}"
            )


@dataclass
class ProtocolConfig:
    """
    Master configuration for protocol abstraction layer

    Defines serializers and transports for each communication channel.
    """

    # Channel configurations
    channels: Dict[str, ChannelConfig] = field(
        default_factory=lambda: {
            # Task distribution: Controller → Worker
            "task_distribution": ChannelConfig(
                serializer="json",
                transport="http",
                timeout=300.0,  # Long timeout for task execution
            ),
            # Heartbeat/Telemetry: Worker → Controller
            "heartbeat": ChannelConfig(
                serializer="json",
                transport="http",
                timeout=5.0,  # Short timeout for heartbeat
            ),
            # Real-time updates: Controller ↔ All
            "realtime": ChannelConfig(
                serializer="json",
                transport="websocket",
                timeout=None,  # No timeout for persistent connection
            ),
            # LLM routing: Controller ↔ LLM Task Master
            "llm_routing": ChannelConfig(
                serializer="json", transport="websocket", timeout=10.0
            ),
            # Worker registration: Worker → Controller
            "worker_registration": ChannelConfig(
                serializer="json", transport="http", timeout=30.0
            ),
        }
    )

    # Global options
    enable_compression: bool = False  # Enable compression for serialized data
    enable_encryption: bool = False  # Enable transport-level encryption
    retry_attempts: int = 3  # Number of retry attempts for failed operations
    retry_delay: float = 1.0  # Delay between retries in seconds

    @classmethod
    def from_env(cls) -> "ProtocolConfig":
        """
        Create configuration from environment variables

        Environment variables:
        - PHANTOM_PROTOCOL_SERIALIZER: Default serializer (e.g., "json", "protobuf")
        - PHANTOM_PROTOCOL_TRANSPORT: Default transport (e.g., "http", "grpc")
        - PHANTOM_PROTOCOL_COMPRESSION: Enable compression ("true"/"false")
        - PHANTOM_PROTOCOL_ENCRYPTION: Enable encryption ("true"/"false")

        Returns:
            ProtocolConfig instance
        """
        config = cls()

        # Override defaults from environment
        default_serializer = os.getenv("PHANTOM_PROTOCOL_SERIALIZER", "json")
        default_transport = os.getenv("PHANTOM_PROTOCOL_TRANSPORT", "http")

        # Apply defaults to all channels
        for channel_config in config.channels.values():
            if channel_config.serializer == "json":
                channel_config.serializer = default_serializer
            if channel_config.transport == "http":
                channel_config.transport = default_transport

        # Global options
        config.enable_compression = (
            os.getenv("PHANTOM_PROTOCOL_COMPRESSION", "false").lower() == "true"
        )
        config.enable_encryption = (
            os.getenv("PHANTOM_PROTOCOL_ENCRYPTION", "false").lower() == "true"
        )

        logger.info(
            f"Protocol configuration loaded from environment: "
            f"serializer={default_serializer}, transport={default_transport}"
        )

        return config

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ProtocolConfig":
        """
        Create configuration from dictionary

        Args:
            config_dict: Configuration dictionary

        Returns:
            ProtocolConfig instance
        """
        channels = {}
        for channel_name, channel_dict in config_dict.get("channels", {}).items():
            channels[channel_name] = ChannelConfig(**channel_dict)

        return cls(
            channels=channels,
            enable_compression=config_dict.get("enable_compression", False),
            enable_encryption=config_dict.get("enable_encryption", False),
            retry_attempts=config_dict.get("retry_attempts", 3),
            retry_delay=config_dict.get("retry_delay", 1.0),
        )

    def get_channel(self, channel_name: str) -> Optional[ChannelConfig]:
        """
        Get configuration for a specific channel

        Args:
            channel_name: Name of the channel

        Returns:
            ChannelConfig or None if channel not found
        """
        return self.channels.get(channel_name)

    def update_channel(
        self,
        channel_name: str,
        serializer: Optional[str] = None,
        transport: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Update configuration for a specific channel

        Args:
            channel_name: Name of the channel
            serializer: New serializer (if provided)
            transport: New transport (if provided)
            **kwargs: Additional options to update
        """
        if channel_name not in self.channels:
            self.channels[channel_name] = ChannelConfig()

        channel = self.channels[channel_name]

        if serializer:
            channel.serializer = serializer
        if transport:
            channel.transport = transport

        channel.options.update(kwargs)

        logger.info(
            f"Updated channel '{channel_name}': serializer={channel.serializer}, "
            f"transport={channel.transport}"
        )


# Default configuration
DEFAULT_CONFIG = ProtocolConfig()
