"""
Factory for creating protocol stacks

Provides convenience functions for creating channel managers with
appropriate serializers and transports based on configuration.

Protocol selection is strictly config-driven.  If a channel is configured
to use protobuf serialization or gRPC transport but the optional [grpc]
extras are not installed, an explicit RuntimeError is raised – there is
**no silent fallback to JSON**.  To enable gRPC support install::

    pip install .[grpc]

To roll back, change the channel configuration back to
``serializer="json", transport="http"``.
"""

from typing import Optional
import logging
from .config import ProtocolConfig
from .channels import ChannelManager

logger = logging.getLogger(__name__)

# Protocols that require the optional [grpc] extras
_GRPC_SERIALIZERS = {"protobuf"}
_GRPC_TRANSPORTS = {"grpc"}

_GRPC_INSTALL_HINT = (
    "Install the optional gRPC/Protobuf extras with:  pip install .[grpc]"
)


def create_channel_manager(config: Optional[ProtocolConfig] = None) -> ChannelManager:
    """
    Create a channel manager with registered serializers and transports

    Args:
        config: Protocol configuration (uses default if not provided)

    Returns:
        Configured ChannelManager instance
    """
    if config is None:
        config = ProtocolConfig.from_env()

    manager = ChannelManager(config)

    # Register available serializers
    _register_serializers(manager, config)

    # Register available transports
    _register_transports(manager, config)

    # Setup channels from configuration
    _setup_channels(manager, config)

    logger.info("Channel manager created and configured")
    return manager


def _register_serializers(manager: ChannelManager, config: ProtocolConfig) -> None:
    """Register all available serializers"""

    # Always register JSON serializer (default)
    try:
        from .serializers.json_serializer import JSONSerializer

        manager.register_serializer("json", JSONSerializer())
    except ImportError as e:
        logger.error(f"Failed to register JSON serializer: {e}")

    # Register Protocol Buffers serializer if available
    _protobuf_available = True
    try:
        from .serializers.protobuf_serializer import ProtobufSerializer

        manager.register_serializer("protobuf", ProtobufSerializer())
    except ImportError:
        _protobuf_available = False
        logger.debug(
            "Protobuf serializer not available (optional, requires [grpc] extras)"
        )

    # Store availability flag so _setup_channels can raise a helpful error
    manager._protobuf_available = _protobuf_available  # type: ignore[attr-defined]

    # Register FlatBuffers serializer if available
    try:
        from .serializers.flatbuffer_serializer import FlatBufferSerializer

        manager.register_serializer("flatbuffers", FlatBufferSerializer())
    except ImportError:
        logger.debug("FlatBuffers serializer not available (optional)")

    # Register MessagePack serializer if available
    try:
        from .serializers.msgpack_serializer import MessagePackSerializer

        manager.register_serializer("msgpack", MessagePackSerializer())
    except ImportError:
        logger.debug("MessagePack serializer not available (optional)")


def _register_transports(manager: ChannelManager, config: ProtocolConfig) -> None:
    """Register all available transports"""

    # Always register HTTP transport (default)
    try:
        from .transports.http_transport import HTTPTransport

        manager.register_transport("http", HTTPTransport())
    except ImportError as e:
        logger.error(f"Failed to register HTTP transport: {e}")

    # Register gRPC transport if available
    _grpc_available = True
    try:
        from .transports.grpc_transport import GRPCTransport

        manager.register_transport("grpc", GRPCTransport())
    except ImportError:
        _grpc_available = False
        logger.debug("gRPC transport not available (optional, requires [grpc] extras)")

    # Store availability flag so _setup_channels can raise a helpful error
    manager._grpc_available = _grpc_available  # type: ignore[attr-defined]

    # Register WebSocket transport if available
    try:
        from .transports.websocket_transport import WebSocketTransport

        manager.register_transport("websocket", WebSocketTransport())
    except ImportError:
        logger.debug("WebSocket transport not available (optional)")

    # Register QUIC transport if available
    try:
        from .transports.quic_transport import QUICTransport

        manager.register_transport("quic", QUICTransport())
    except ImportError:
        logger.debug("QUIC transport not available (optional)")

    # Register ZeroMQ transport if available
    try:
        from .transports.zeromq_transport import ZeroMQTransport

        manager.register_transport("zeromq", ZeroMQTransport())
    except ImportError:
        logger.debug("ZeroMQ transport not available (optional)")


def _setup_channels(manager: ChannelManager, config: ProtocolConfig) -> None:
    """Setup channels from configuration"""

    protobuf_available = getattr(manager, "_protobuf_available", True)
    grpc_available = getattr(manager, "_grpc_available", True)

    for channel_name, channel_config in config.channels.items():
        # --- Fail loudly when a grpc/protobuf channel is misconfigured -------
        if channel_config.serializer in _GRPC_SERIALIZERS and not protobuf_available:
            raise RuntimeError(
                f"Channel '{channel_name}' is configured to use "
                f"serializer='{channel_config.serializer}' but the Protobuf "
                f"package is not installed.\n{_GRPC_INSTALL_HINT}"
            )
        if channel_config.transport in _GRPC_TRANSPORTS and not grpc_available:
            raise RuntimeError(
                f"Channel '{channel_name}' is configured to use "
                f"transport='{channel_config.transport}' but grpcio is not "
                f"installed.\n{_GRPC_INSTALL_HINT}"
            )

        # Get serializer
        serializer = manager.serializers.get(channel_config.serializer)
        if not serializer:
            logger.warning(
                f"Serializer '{channel_config.serializer}' not available for "
                f"channel '{channel_name}', skipping"
            )
            continue

        # Get transport
        transport = manager.transports.get(channel_config.transport)
        if not transport:
            logger.warning(
                f"Transport '{channel_config.transport}' not available for "
                f"channel '{channel_name}', skipping"
            )
            continue

        # Register channel
        manager.register_channel(channel_name, serializer, transport, channel_config)
