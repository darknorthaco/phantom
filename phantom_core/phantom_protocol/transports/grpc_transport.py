"""
gRPC transport implementation

Provides a TransportAdapter that sends TaskRequest messages over gRPC and
receives TaskResult responses using the phantom.protocol.TaskDistribution
service defined in phantom_protocol_schemas/task.proto.

This module requires the optional [grpc] extras:
    pip install .[grpc]

Safe defaults
-------------
- Default timeout:         30 s  (overridable per-call)
- Max incoming message:    4 MiB
- Max outgoing message:    4 MiB
- Silent JSON fallback:    NEVER (fail loud if grpc is requested but unavailable)
"""

import logging
from typing import Any, Dict, Optional, Tuple

try:
    import grpc
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "gRPC transport requires the [grpc] extras. "
        "Install with:  pip install .[grpc]"
    ) from exc

from ..interfaces import TransportAdapter, TransportError, ConnectionError

logger = logging.getLogger(__name__)

# Hard limits to prevent unbounded message growth
_MAX_MSG_BYTES = 4 * 1024 * 1024  # 4 MiB

# gRPC channel options applied to every new channel
_CHANNEL_OPTIONS = [
    ("grpc.max_receive_message_length", _MAX_MSG_BYTES),
    ("grpc.max_send_message_length", _MAX_MSG_BYTES),
    ("grpc.keepalive_time_ms", 30_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.keepalive_permit_without_calls", 1),
]


class GRPCTransport(TransportAdapter):
    """
    gRPC transport for Phantom protocol messages.

    Wraps the TaskDistribution.SubmitTask unary RPC so it fits the generic
    TransportAdapter interface expected by ChannelManager.

    The raw bytes passed to ``send`` / ``send_and_receive`` are assumed to be
    already-serialized Protobuf (produced by ProtobufSerializer).  The
    transport deserializes the response bytes using TaskResult.FromString and
    re-serialises to bytes so the serializer layer can apply its own
    deserialization on the way back.

    Thread-safety note: a single GRPCTransport instance should not be shared
    across threads.  The factory creates one instance per channel.

    Usage::

        transport = GRPCTransport(timeout=30.0)
        await transport.connect("localhost:50051")
        response_bytes, meta = await transport.send_and_receive(request_bytes)
        await transport.disconnect()
    """

    def __init__(
        self,
        timeout: float = 30.0,
        use_tls: bool = False,
        credentials: Optional[Any] = None,
    ) -> None:
        """
        Initialise gRPC transport.

        Args:
            timeout:     Default per-call timeout in seconds.
            use_tls:     Use TLS channel credentials (recommended for production).
            credentials: Optional grpc.ChannelCredentials; if provided, ``use_tls``
                         is ignored and these credentials are used directly.
        """
        self.timeout = timeout
        self.use_tls = use_tls
        self.credentials = credentials

        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[Any] = None
        self._endpoint: Optional[str] = None
        self._is_connected = False

    # ------------------------------------------------------------------
    # TransportAdapter implementation
    # ------------------------------------------------------------------

    async def connect(self, endpoint: str, **kwargs) -> None:
        """
        Create a gRPC channel to *endpoint*.

        Args:
            endpoint: ``host:port`` string (e.g. ``"localhost:50051"``).
            **kwargs: Forwarded to grpc.secure_channel / grpc.insecure_channel
                      as ``options`` override.

        Raises:
            ConnectionError: If the channel cannot be created.
        """
        try:
            self._endpoint = endpoint
            options = kwargs.get("options", _CHANNEL_OPTIONS)

            if self.credentials is not None:
                self._channel = grpc.secure_channel(
                    endpoint, self.credentials, options=options
                )
            elif self.use_tls:
                creds = grpc.ssl_channel_credentials()
                self._channel = grpc.secure_channel(endpoint, creds, options=options)
            else:
                self._channel = grpc.insecure_channel(endpoint, options=options)

            # Import the stub lazily so that missing grpcio is caught early
            from phantom_protocol_schemas import task_pb2_grpc

            self._stub = task_pb2_grpc.TaskDistributionStub(self._channel)
            self._is_connected = True
            logger.info("gRPC transport connected to %s", endpoint)

        except Exception as exc:
            logger.error("gRPC connection failed: %s", exc)
            raise ConnectionError(f"gRPC connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        """
        Close the gRPC channel.

        Raises:
            ConnectionError: If close fails.
        """
        try:
            if self._channel is not None:
                self._channel.close()
                self._channel = None
                self._stub = None

            self._is_connected = False
            logger.info("gRPC transport disconnected")

        except Exception as exc:
            logger.error("gRPC disconnect failed: %s", exc)
            raise ConnectionError(f"gRPC disconnect failed: {exc}") from exc

    async def send(
        self, message: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send a message (fire-and-forget).

        Note: gRPC is inherently request/response; this method sends the
        request and discards the response.  Use send_and_receive for the full
        round-trip.

        Args:
            message:  Serialized TaskRequest bytes.
            metadata: Optional dict; ``timeout`` key overrides default timeout.

        Raises:
            TransportError: If the RPC call fails.
        """
        await self.send_and_receive(message, metadata)

    async def receive(
        self, timeout: Optional[float] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        gRPC does not support standalone receive without a prior send.

        Raises:
            TransportError: Always – use send_and_receive instead.
        """
        raise TransportError(
            "gRPC transport does not support standalone receive; "
            "use send_and_receive for request/response."
        )

    async def send_and_receive(
        self,
        message: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Execute SubmitTask RPC and return the serialized response bytes.

        Args:
            message:  Serialized TaskRequest bytes (from ProtobufSerializer).
            metadata: Optional dict.  Keys:
                      - ``timeout`` (float): per-call timeout override.
                      - ``grpc_metadata`` (list): gRPC call metadata list.
            timeout:  Per-call timeout in seconds (takes precedence over
                      metadata["timeout"] and the instance default).

        Returns:
            Tuple of (TaskResult bytes, response metadata dict).

        Raises:
            TransportError: If the RPC call fails.
            TimeoutError:   If the deadline is exceeded.
        """
        if not self._is_connected or self._stub is None:
            raise TransportError("gRPC transport not connected")

        metadata = metadata or {}
        call_timeout = (
            timeout if timeout is not None else metadata.get("timeout", self.timeout)
        )
        grpc_metadata = metadata.get("grpc_metadata", ())

        try:
            from phantom_protocol_schemas import task_pb2

            # Deserialize the request bytes back into a proto Message so we
            # can pass it to the stub (which expects a proto object).
            request = task_pb2.TaskRequest()
            request.ParseFromString(message)

            response = self._stub.SubmitTask(
                request,
                timeout=call_timeout,
                metadata=grpc_metadata,
            )

            response_bytes = response.SerializeToString()
            response_meta = {
                "grpc_status": "OK",
                "content_type": "application/x-protobuf",
            }
            logger.debug(
                "gRPC SubmitTask completed: task_id=%s status=%s",
                response.task_id,
                response.status,
            )
            return response_bytes, response_meta

        except grpc.RpcError as exc:
            code = exc.code()  # type: ignore[union-attr]
            details = exc.details()  # type: ignore[union-attr]
            logger.error("gRPC RPC error %s: %s", code, details)
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise TimeoutError(
                    f"gRPC call timed out after {call_timeout}s: {details}"
                ) from exc
            raise TransportError(f"gRPC RPC failed [{code.name}]: {details}") from exc
        except Exception as exc:
            logger.error("gRPC send_and_receive failed: %s", exc)
            raise TransportError(f"gRPC send_and_receive failed: {exc}") from exc

    @property
    def is_connected(self) -> bool:
        """Check if gRPC channel is open"""
        return self._is_connected and self._channel is not None

    @property
    def name(self) -> str:
        """Transport name"""
        return "grpc"
