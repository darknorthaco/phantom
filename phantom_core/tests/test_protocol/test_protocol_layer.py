"""Tests for protocol abstraction layer"""

import pytest
from phantom_protocol.interfaces import TransportAdapter
from phantom_protocol.serializers.json_serializer import JSONSerializer
from phantom_protocol.config import ProtocolConfig, ChannelConfig
from phantom_protocol.channels import ChannelManager
from phantom_protocol.factory import create_channel_manager


class TestJSONSerializer:
    """Test JSON serializer implementation"""

    def setup_method(self):
        """Setup test fixtures"""
        self.serializer = JSONSerializer()

    def test_serialize_dict(self):
        """Test serialization of dictionary"""
        data = {"key": "value", "number": 42}
        result = self.serializer.serialize(data)

        assert isinstance(result, bytes)
        assert b"key" in result
        assert b"value" in result

    def test_deserialize_dict(self):
        """Test deserialization to dictionary"""
        data = b'{"key": "value", "number": 42}'
        result = self.serializer.deserialize(data)

        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_roundtrip(self):
        """Test serialization and deserialization roundtrip"""
        original = {
            "string": "test",
            "number": 123,
            "float": 45.67,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"a": "b"},
        }

        serialized = self.serializer.serialize(original)
        deserialized = self.serializer.deserialize(serialized)

        assert deserialized == original

    def test_content_type(self):
        """Test content type property"""
        assert self.serializer.content_type == "application/json"

    def test_name(self):
        """Test name property"""
        assert self.serializer.name == "json"


class TestProtocolConfig:
    """Test protocol configuration"""

    def test_default_config(self):
        """Test default configuration"""
        config = ProtocolConfig()

        assert "task_distribution" in config.channels
        assert "heartbeat" in config.channels
        assert "realtime" in config.channels

    def test_channel_config(self):
        """Test channel configuration"""
        config = ChannelConfig(serializer="json", transport="http", timeout=60.0)

        assert config.serializer == "json"
        assert config.transport == "http"
        assert config.timeout == 60.0

    def test_get_channel(self):
        """Test get channel configuration"""
        config = ProtocolConfig()
        channel = config.get_channel("task_distribution")

        assert channel is not None
        assert channel.serializer == "json"
        assert channel.transport == "http"

    def test_update_channel(self):
        """Test update channel configuration"""
        config = ProtocolConfig()
        config.update_channel(
            "task_distribution", serializer="protobuf", transport="grpc"
        )

        channel = config.get_channel("task_distribution")
        assert channel.serializer == "protobuf"
        assert channel.transport == "grpc"


class MockTransport(TransportAdapter):
    """Mock transport for testing"""

    def __init__(self):
        self._connected = False
        self.sent_messages = []
        self.response_queue = []

    async def connect(self, endpoint: str, **kwargs):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def send(self, message: bytes, metadata=None):
        self.sent_messages.append((message, metadata))

    async def receive(self, timeout=None):
        if self.response_queue:
            return self.response_queue.pop(0)
        raise TimeoutError("No messages in queue")

    async def send_and_receive(self, message: bytes, metadata=None, timeout=None):
        self.sent_messages.append((message, metadata))
        if self.response_queue:
            return self.response_queue.pop(0)
        return b'{"status": "success"}', {}

    @property
    def is_connected(self):
        return self._connected

    @property
    def name(self):
        return "mock"


class TestChannelManager:
    """Test channel manager"""

    def setup_method(self):
        """Setup test fixtures"""
        self.config = ProtocolConfig()
        self.manager = ChannelManager(self.config)
        self.serializer = JSONSerializer()
        self.transport = MockTransport()

    def test_register_serializer(self):
        """Test register serializer"""
        self.manager.register_serializer("json", self.serializer)
        assert "json" in self.manager.serializers

    def test_register_transport(self):
        """Test register transport"""
        self.manager.register_transport("mock", self.transport)
        assert "mock" in self.manager.transports

    def test_register_channel(self):
        """Test register channel"""
        self.manager.register_channel("test_channel", self.serializer, self.transport)
        assert "test_channel" in self.manager.channels

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test send message through channel"""
        self.manager.register_channel("test_channel", self.serializer, self.transport)

        await self.transport.connect("http://localhost:8080")

        message = {"test": "data"}
        await self.manager.send_message(
            "test_channel", message, "http://localhost:8080"
        )

        assert len(self.transport.sent_messages) == 1
        sent_data, _ = self.transport.sent_messages[0]
        assert b"test" in sent_data

    @pytest.mark.asyncio
    async def test_send_and_receive(self):
        """Test send and receive message"""
        self.manager.register_channel("test_channel", self.serializer, self.transport)

        await self.transport.connect("http://localhost:8080")

        # Queue a response
        response_data = {"result": "success"}
        self.transport.response_queue.append(
            (self.serializer.serialize(response_data), {})
        )

        message = {"test": "request"}
        result = await self.manager.send_and_receive(
            "test_channel", message, "http://localhost:8080", response_type=dict
        )

        assert result["result"] == "success"


class TestFactory:
    """Test protocol factory"""

    def test_create_channel_manager(self):
        """Test create channel manager with default config"""
        manager = create_channel_manager()

        assert isinstance(manager, ChannelManager)
        assert "json" in manager.serializers
        assert "http" in manager.transports

    def test_create_with_custom_config(self):
        """Test create with custom configuration"""
        config = ProtocolConfig()
        config.update_channel("task_distribution", serializer="json", transport="http")

        manager = create_channel_manager(config)

        assert isinstance(manager, ChannelManager)
        assert "task_distribution" in manager.channels


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
