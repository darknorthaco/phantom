"""
Phantom Protocol Abstraction Layer

This package provides a protocol-agnostic communication layer for Phantom Distributed,
enabling seamless migration between different serialization and transport protocols
without modifying business logic.

Core Components:
- MessageSerializer: Abstract interface for serialization (JSON, Protobuf, FlatBuffers, etc.)
- TransportAdapter: Abstract interface for transport (HTTP, gRPC, WebSocket, etc.)
- ChannelManager: Routes messages through appropriate protocol stacks
- ProtocolConfig: Configuration system for protocol selection

Example Usage:
    >>> from phantom_protocol import create_channel_manager
    >>>
    >>> # Create channel manager with JSON+HTTP (current default)
    >>> manager = create_channel_manager()
    >>>
    >>> # Send a message
    >>> await manager.send_message(
    ...     channel="task_distribution",
    ...     message=task_message,
    ...     destination="worker-1"
    ... )
    >>>
    >>> # Receive a message
    >>> result = await manager.receive_message(
    ...     channel="task_distribution",
    ...     message_type=TaskResultMessage
    ... )

Future Protocols:
- gRPC + Protobuf (5-10x performance improvement)
- QUIC + FlatBuffers (ultra-low latency)
- ZeroMQ (broker-less telemetry)
"""

__version__ = "1.0.0"

# Only export these if they can be imported successfully
__all__ = []

try:
    from .interfaces import MessageSerializer, TransportAdapter  # noqa: F401

    __all__.extend(["MessageSerializer", "TransportAdapter"])
except ImportError:
    pass

try:
    from .channels import ChannelManager  # noqa: F401

    __all__.append("ChannelManager")
except ImportError:
    pass

try:
    from .config import ProtocolConfig  # noqa: F401

    __all__.append("ProtocolConfig")
except ImportError:
    pass

try:
    from .factory import create_channel_manager  # noqa: F401

    __all__.append("create_channel_manager")
except ImportError:
    pass
