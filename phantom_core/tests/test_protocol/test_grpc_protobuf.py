"""
Tests for gRPC+Protobuf protocol support (Phase 4)

Test coverage:
1. ProtobufSerializer – unit tests for serialize/deserialize roundtrip
2. Protocol selection – factory raises helpful errors when deps are absent and
   grpc/protobuf is configured
3. GRPCTransport integration – in-process gRPC server that verifies a
   complete TaskRequest → TaskResult round-trip through ChannelManager

Run only base tests (no grpc required)::

    pytest tests/test_protocol/test_grpc_protobuf.py -m "not grpc_integration"

Run all including integration test (requires grpcio + protobuf)::

    pytest tests/test_protocol/test_grpc_protobuf.py
"""

import asyncio
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / marks
# ---------------------------------------------------------------------------

grpc_available = True
try:
    import grpc
    from phantom_protocol_schemas import task_pb2, task_pb2_grpc
    from phantom_protocol.serializers.protobuf_serializer import ProtobufSerializer
    from phantom_protocol.transports.grpc_transport import GRPCTransport
except ImportError:
    grpc_available = False

requires_grpc = pytest.mark.skipif(
    not grpc_available,
    reason="grpcio and protobuf extras not installed (pip install .[grpc])",
)

pytestmark = pytest.mark.grpc_integration


# ---------------------------------------------------------------------------
# 1. ProtobufSerializer – unit tests
# ---------------------------------------------------------------------------


@requires_grpc
class TestProtobufSerializer:
    """Unit tests for ProtobufSerializer"""

    def setup_method(self):
        self.s = ProtobufSerializer()

    def test_name(self):
        assert self.s.name == "protobuf"

    def test_content_type(self):
        assert self.s.content_type == "application/x-protobuf"

    def test_serialize_task_request_dict(self):
        d = {"task_id": "t1", "task_type": "gpu_compute", "correlation_id": "c1"}
        data = self.s.serialize(d)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_serialize_task_result_dict(self):
        d = {"task_id": "t1", "status": "completed", "correlation_id": "c1"}
        data = self.s.serialize(d)
        assert isinstance(data, bytes)

    def test_roundtrip_task_request(self):
        original = {
            "task_id": "t42",
            "task_type": "llm_inference",
            "parameters": {"prompt": "hello", "max_tokens": "256"},
            "schema_version": "1",
            "correlation_id": "corr-99",
        }
        data = self.s.serialize(original)
        result = self.s.deserialize(data, task_pb2.TaskRequest)
        assert result["task_id"] == "t42"
        assert result["task_type"] == "llm_inference"
        assert result["parameters"]["prompt"] == "hello"

    def test_roundtrip_task_result(self):
        original = {
            "task_id": "t42",
            "status": "completed",
            "result": {"output": "world"},
            "schema_version": "1",
            "correlation_id": "corr-99",
        }
        data = self.s.serialize(original)
        result = self.s.deserialize(data, task_pb2.TaskResult)
        assert result["task_id"] == "t42"
        assert result["status"] == "completed"

    def test_serialize_proto_message_directly(self):
        req = task_pb2.TaskRequest(task_id="x", task_type="y")
        data = self.s.serialize(req)
        assert isinstance(data, bytes)
        # Roundtrip
        result = self.s.deserialize(data, task_pb2.TaskRequest)
        assert result["task_id"] == "x"

    def test_serialize_dataclass(self):
        from dataclasses import dataclass

        @dataclass
        class MyTask:
            task_type: str = "test"

        data = self.s.serialize(MyTask())
        assert isinstance(data, bytes)

    def test_serialize_invalid_raises(self):
        from phantom_protocol.interfaces import SerializationError

        with pytest.raises(SerializationError):
            self.s.serialize(object())

    def test_deserialize_invalid_raises(self):
        from phantom_protocol.interfaces import DeserializationError

        with pytest.raises(DeserializationError):
            self.s.deserialize(b"\xff\xff\xff invalid protobuf bytes zzz")


# ---------------------------------------------------------------------------
# 2. Protocol selection – factory behaviour
# ---------------------------------------------------------------------------


class TestProtocolSelection:
    """Tests that the factory enforces config-driven protocol selection."""

    def test_default_config_uses_json_http(self):
        """Default config must produce a manager with json+http channels."""
        from phantom_protocol.factory import create_channel_manager
        from phantom_protocol.config import ProtocolConfig

        manager = create_channel_manager(ProtocolConfig())
        assert "json" in manager.serializers
        assert "http" in manager.transports
        assert "task_distribution" in manager.channels
        ch = manager.channels["task_distribution"]
        assert ch["serializer"].name == "json"
        assert ch["transport"].name == "http"

    def test_grpc_config_raises_when_deps_missing(self):
        """Requesting grpc transport when grpcio is absent must raise RuntimeError."""
        from phantom_protocol.factory import create_channel_manager
        from phantom_protocol.config import ProtocolConfig

        config = ProtocolConfig()
        config.update_channel(
            "task_distribution", serializer="protobuf", transport="grpc"
        )

        # Simulate missing grpcio by patching the availability flags
        with patch(
            "phantom_protocol.factory._register_transports",
            side_effect=lambda manager, cfg: _register_transports_no_grpc(manager, cfg),
        ):
            with pytest.raises(RuntimeError, match="pip install"):
                create_channel_manager(config)

    def test_protobuf_config_raises_when_deps_missing(self):
        """Requesting protobuf serializer when protobuf is absent must raise RuntimeError."""
        from phantom_protocol.factory import create_channel_manager
        from phantom_protocol.config import ProtocolConfig

        config = ProtocolConfig()
        config.update_channel(
            "task_distribution", serializer="protobuf", transport="http"
        )

        with patch(
            "phantom_protocol.factory._register_serializers",
            side_effect=lambda manager, cfg: _register_serializers_no_protobuf(
                manager, cfg
            ),
        ):
            with pytest.raises(RuntimeError, match="pip install"):
                create_channel_manager(config)

    @requires_grpc
    def test_grpc_config_registers_when_deps_present(self):
        """Requesting grpc+protobuf when deps are present must succeed."""
        from phantom_protocol.factory import create_channel_manager
        from phantom_protocol.config import ProtocolConfig

        config = ProtocolConfig()
        config.update_channel(
            "task_distribution", serializer="protobuf", transport="grpc"
        )
        manager = create_channel_manager(config)
        assert "protobuf" in manager.serializers
        assert "grpc" in manager.transports
        assert "task_distribution" in manager.channels
        ch = manager.channels["task_distribution"]
        assert ch["serializer"].name == "protobuf"
        assert ch["transport"].name == "grpc"


# ---------------------------------------------------------------------------
# Helpers for patching in TestProtocolSelection
# ---------------------------------------------------------------------------


def _register_transports_no_grpc(manager, config):
    """Register only http transport (simulates absent grpcio)."""
    try:
        from phantom_protocol.transports.http_transport import HTTPTransport

        manager.register_transport("http", HTTPTransport())
    except ImportError:
        pass
    manager._grpc_available = False  # type: ignore[attr-defined]
    manager._protobuf_available = True  # type: ignore[attr-defined]


def _register_serializers_no_protobuf(manager, config):
    """Register only json serializer (simulates absent protobuf)."""
    from phantom_protocol.serializers.json_serializer import JSONSerializer

    manager.register_serializer("json", JSONSerializer())
    manager._protobuf_available = False  # type: ignore[attr-defined]
    manager._grpc_available = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 3. GRPCTransport integration – in-process server
# ---------------------------------------------------------------------------


@requires_grpc
class TestGRPCIntegration:
    """
    End-to-end integration test using an in-process gRPC server.

    Spins up a real grpc.server() in a background thread, then exercises the
    full ChannelManager → ProtobufSerializer → GRPCTransport → gRPC server
    path and validates the response.
    """

    def _start_server(self, port: int):
        """Start an in-process gRPC server and return (server, servicer)."""
        import concurrent.futures

        class EchoServicer(task_pb2_grpc.TaskDistributionServicer):
            def SubmitTask(self, request, context):
                return task_pb2.TaskResult(
                    task_id=request.task_id,
                    status="completed",
                    schema_version=request.schema_version,
                    correlation_id=request.correlation_id,
                    result={"echo": request.parameters.get("input", "")},
                )

        server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=2))
        task_pb2_grpc.add_TaskDistributionServicer_to_server(EchoServicer(), server)
        server.add_insecure_port(f"[::]:{port}")
        server.start()
        return server

    @pytest.mark.asyncio
    async def test_roundtrip_via_channel_manager(self):
        """Full round-trip: ChannelManager.send_and_receive over gRPC."""
        from phantom_protocol.channels import ChannelManager
        from phantom_protocol.config import ProtocolConfig, ChannelConfig

        port = 50077  # fixed port for this test

        # Start in-process server
        server = self._start_server(port)
        # Give the server a moment to start
        await asyncio.sleep(0.1)

        try:
            # Build manager with grpc+protobuf for task_distribution
            config = ProtocolConfig(
                channels={
                    "task_distribution": ChannelConfig(
                        serializer="protobuf",
                        transport="grpc",
                        timeout=5.0,
                    )
                }
            )
            manager = ChannelManager(config)
            manager.register_serializer("protobuf", ProtobufSerializer())
            transport = GRPCTransport(timeout=5.0)
            manager.register_transport("grpc", transport)
            manager.register_channel(
                "task_distribution",
                manager.serializers["protobuf"],
                transport,
                config.channels["task_distribution"],
            )

            # Connect and exercise
            await transport.connect(f"localhost:{port}")

            request = {
                "task_id": "integration-1",
                "task_type": "echo",
                "parameters": {"input": "hello_grpc"},
                "schema_version": "1",
                "correlation_id": "test-corr",
            }

            response = await manager.send_and_receive(
                channel="task_distribution",
                message=request,
                destination=f"localhost:{port}",
                response_type=task_pb2.TaskResult,
            )

            assert response["task_id"] == "integration-1"
            assert response["status"] == "completed"
            assert response["result"]["echo"] == "hello_grpc"
            assert response["correlation_id"] == "test-corr"

        finally:
            await transport.disconnect()
            server.stop(grace=1)

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        """A slow server exceeding the timeout raises TimeoutError."""
        import concurrent.futures
        import time as time_module

        port = 50078

        class SlowServicer(task_pb2_grpc.TaskDistributionServicer):
            def SubmitTask(self, request, context):
                time_module.sleep(10)  # far longer than the 0.1s timeout
                return task_pb2.TaskResult(task_id=request.task_id, status="ok")

        server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=1))
        task_pb2_grpc.add_TaskDistributionServicer_to_server(SlowServicer(), server)
        server.add_insecure_port(f"[::]:{port}")
        server.start()
        await asyncio.sleep(0.1)

        transport = GRPCTransport(timeout=0.1)
        try:
            await transport.connect(f"localhost:{port}")
            req = task_pb2.TaskRequest(task_id="slow-1", task_type="noop")
            with pytest.raises(TimeoutError):
                await transport.send_and_receive(req.SerializeToString(), timeout=0.1)
        finally:
            await transport.disconnect()
            server.stop(grace=1)
