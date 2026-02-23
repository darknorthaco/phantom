"""
Channel manager for routing messages through protocol stacks

The ChannelManager is the main interface for sending/receiving messages
through the protocol abstraction layer.
"""

from typing import Any, Dict, Optional, Type
import logging
from .interfaces import MessageSerializer, TransportAdapter, ProtocolError
from .config import ProtocolConfig, ChannelConfig

logger = logging.getLogger(__name__)


class ChannelManager:
    """
    Manages communication channels and routes messages through appropriate protocol stacks

    Each channel has a configured serializer and transport. Messages sent through
    a channel are automatically serialized and transmitted using the channel's protocol stack.
    """

    def __init__(self, config: ProtocolConfig):
        """
        Initialize channel manager

        Args:
            config: Protocol configuration
        """
        self.config = config
        self.channels: Dict[str, Dict[str, Any]] = {}
        self.serializers: Dict[str, MessageSerializer] = {}
        self.transports: Dict[str, TransportAdapter] = {}

        logger.info("ChannelManager initialized")

    def register_serializer(self, name: str, serializer: MessageSerializer) -> None:
        """
        Register a serializer implementation

        Args:
            name: Serializer name (e.g., "json", "protobuf")
            serializer: Serializer instance
        """
        self.serializers[name] = serializer
        logger.info(f"Registered serializer: {name} ({serializer.content_type})")

    def register_transport(self, name: str, transport: TransportAdapter) -> None:
        """
        Register a transport implementation

        Args:
            name: Transport name (e.g., "http", "grpc")
            transport: Transport instance
        """
        self.transports[name] = transport
        logger.info(f"Registered transport: {name}")

    def register_channel(
        self,
        channel_name: str,
        serializer: MessageSerializer,
        transport: TransportAdapter,
        config: Optional[ChannelConfig] = None,
    ) -> None:
        """
        Register a communication channel with its protocol stack

        Args:
            channel_name: Name of the channel
            serializer: Serializer for this channel
            transport: Transport for this channel
            config: Optional channel configuration
        """
        self.channels[channel_name] = {
            "serializer": serializer,
            "transport": transport,
            "config": config or ChannelConfig(),
        }
        logger.info(
            f"Registered channel: {channel_name} "
            f"(serializer={serializer.name}, transport={transport.name})"
        )

    def get_channel(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """
        Get channel configuration

        Args:
            channel_name: Name of the channel

        Returns:
            Channel dict or None if not found
        """
        return self.channels.get(channel_name)

    async def send_message(
        self,
        channel: str,
        message: Any,
        destination: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send message through specified channel

        Args:
            channel: Channel name
            message: Message object to send
            destination: Target endpoint
            metadata: Optional metadata

        Raises:
            ProtocolError: If channel not found or send fails
        """
        channel_config = self.channels.get(channel)
        if not channel_config:
            raise ProtocolError(f"Channel '{channel}' not registered")

        serializer = channel_config["serializer"]
        transport = channel_config["transport"]

        # Serialize message
        try:
            serialized = serializer.serialize(message)
            logger.debug(
                f"Serialized message for channel '{channel}' "
                f"({len(serialized)} bytes)"
            )
        except Exception as e:
            logger.error(f"Serialization failed for channel '{channel}': {e}")
            raise ProtocolError(f"Serialization failed: {e}") from e

        # Connect if not already connected
        if not transport.is_connected:
            await transport.connect(destination)

        # Send through transport
        try:
            await transport.send(serialized, metadata)
            logger.debug(f"Sent message through channel '{channel}' to {destination}")
        except Exception as e:
            logger.error(f"Transport send failed for channel '{channel}': {e}")
            raise ProtocolError(f"Transport send failed: {e}") from e

    async def receive_message(
        self,
        channel: str,
        message_type: Optional[Type] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Receive and deserialize message from channel

        Args:
            channel: Channel name
            message_type: Expected message type for deserialization
            timeout: Optional timeout in seconds

        Returns:
            Deserialized message object

        Raises:
            ProtocolError: If channel not found or receive fails
        """
        channel_config = self.channels.get(channel)
        if not channel_config:
            raise ProtocolError(f"Channel '{channel}' not registered")

        serializer = channel_config["serializer"]
        transport = channel_config["transport"]

        # Receive from transport
        try:
            data, metadata = await transport.receive(timeout)
            logger.debug(
                f"Received message from channel '{channel}' " f"({len(data)} bytes)"
            )
        except Exception as e:
            logger.error(f"Transport receive failed for channel '{channel}': {e}")
            raise ProtocolError(f"Transport receive failed: {e}") from e

        # Deserialize message
        try:
            message = serializer.deserialize(data, message_type)
            logger.debug(f"Deserialized message from channel '{channel}'")
            return message
        except Exception as e:
            logger.error(f"Deserialization failed for channel '{channel}': {e}")
            raise ProtocolError(f"Deserialization failed: {e}") from e

    async def send_and_receive(
        self,
        channel: str,
        message: Any,
        destination: str,
        response_type: Optional[Type] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Send message and wait for response (request/response pattern)

        Args:
            channel: Channel name
            message: Message object to send
            destination: Target endpoint
            response_type: Expected response type
            metadata: Optional metadata
            timeout: Optional timeout in seconds

        Returns:
            Deserialized response object

        Raises:
            ProtocolError: If channel not found or send/receive fails
        """
        channel_config = self.channels.get(channel)
        if not channel_config:
            raise ProtocolError(f"Channel '{channel}' not registered")

        serializer = channel_config["serializer"]
        transport = channel_config["transport"]

        # Serialize request
        try:
            serialized = serializer.serialize(message)
            logger.debug(
                f"Serialized request for channel '{channel}' "
                f"({len(serialized)} bytes)"
            )
        except Exception as e:
            logger.error(f"Request serialization failed for channel '{channel}': {e}")
            raise ProtocolError(f"Request serialization failed: {e}") from e

        # Connect if not already connected
        if not transport.is_connected:
            await transport.connect(destination)

        # Send and receive
        try:
            response_data, response_metadata = await transport.send_and_receive(
                serialized, metadata, timeout
            )
            logger.debug(
                f"Received response from channel '{channel}' "
                f"({len(response_data)} bytes)"
            )
        except Exception as e:
            logger.error(f"Request/response failed for channel '{channel}': {e}")
            raise ProtocolError(f"Request/response failed: {e}") from e

        # Deserialize response
        try:
            response = serializer.deserialize(response_data, response_type)
            logger.debug(f"Deserialized response from channel '{channel}'")
            return response
        except Exception as e:
            logger.error(
                f"Response deserialization failed for channel '{channel}': {e}"
            )
            raise ProtocolError(f"Response deserialization failed: {e}") from e

    async def close_channel(self, channel_name: str) -> None:
        """
        Close a specific channel and disconnect its transport

        Args:
            channel_name: Name of the channel to close
        """
        channel_config = self.channels.get(channel_name)
        if not channel_config:
            logger.warning(f"Attempted to close non-existent channel: {channel_name}")
            return

        transport = channel_config["transport"]
        if transport.is_connected:
            await transport.disconnect()
            logger.info(f"Closed channel: {channel_name}")

    async def close_all(self) -> None:
        """Close all channels and disconnect all transports"""
        for channel_name in list(self.channels.keys()):
            await self.close_channel(channel_name)
        logger.info("All channels closed")
