"""
Abstract interfaces for protocol abstraction layer

These interfaces define the contracts for serializers and transports,
enabling pluggable protocol implementations without coupling to specific technologies.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Type
import logging

logger = logging.getLogger(__name__)


class MessageSerializer(ABC):
    """
    Abstract base class for message serialization

    Implementations must convert Python objects to/from bytes in a specific format.
    Examples: JSON, Protocol Buffers, FlatBuffers, MessagePack, etc.
    """

    @abstractmethod
    def serialize(self, obj: Any) -> bytes:
        """
        Convert Python object to bytes

        Args:
            obj: Python object to serialize (dict, dataclass, Pydantic model, etc.)

        Returns:
            Serialized bytes representation

        Raises:
            SerializationError: If object cannot be serialized
        """
        pass

    @abstractmethod
    def deserialize(self, data: bytes, message_type: Optional[Type] = None) -> Any:
        """
        Convert bytes to Python object

        Args:
            data: Serialized bytes
            message_type: Optional type hint for deserialization

        Returns:
            Deserialized Python object

        Raises:
            DeserializationError: If bytes cannot be deserialized
        """
        pass

    @property
    @abstractmethod
    def content_type(self) -> str:
        """
        MIME type / content type identifier for this serialization format

        Returns:
            Content type string (e.g., "application/json", "application/x-protobuf")
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable name for this serializer

        Returns:
            Serializer name (e.g., "json", "protobuf", "flatbuffers")
        """
        pass


class TransportAdapter(ABC):
    """
    Abstract base class for transport protocols

    Implementations handle the actual network communication using various protocols.
    Examples: HTTP, gRPC, WebSocket, QUIC, ZeroMQ, etc.
    """

    @abstractmethod
    async def connect(self, endpoint: str, **kwargs) -> None:
        """
        Establish connection to remote endpoint

        Args:
            endpoint: Target endpoint (URL, IP:port, etc.)
            **kwargs: Protocol-specific connection parameters

        Raises:
            ConnectionError: If connection cannot be established
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to remote endpoint

        Raises:
            ConnectionError: If disconnect fails
        """
        pass

    @abstractmethod
    async def send(
        self, message: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send message to remote endpoint

        Args:
            message: Serialized message bytes
            metadata: Optional metadata (headers, routing info, etc.)

        Raises:
            TransportError: If send fails
        """
        pass

    @abstractmethod
    async def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Receive message from remote endpoint

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (message bytes, metadata dict)

        Raises:
            TransportError: If receive fails
            TimeoutError: If timeout expires
        """
        pass

    @abstractmethod
    async def send_and_receive(
        self,
        message: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Send message and wait for response (request/response pattern)

        Args:
            message: Serialized message bytes
            metadata: Optional metadata (headers, routing info, etc.)
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (response bytes, response metadata)

        Raises:
            TransportError: If send or receive fails
            TimeoutError: If timeout expires
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if transport is currently connected

        Returns:
            True if connected, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable name for this transport

        Returns:
            Transport name (e.g., "http", "grpc", "websocket")
        """
        pass


class ProtocolError(Exception):
    """Base exception for protocol layer errors"""

    pass


class SerializationError(ProtocolError):
    """Exception raised when serialization fails"""

    pass


class DeserializationError(ProtocolError):
    """Exception raised when deserialization fails"""

    pass


class TransportError(ProtocolError):
    """Exception raised when transport operation fails"""

    pass


class ConnectionError(TransportError):
    """Exception raised when connection fails"""

    pass
