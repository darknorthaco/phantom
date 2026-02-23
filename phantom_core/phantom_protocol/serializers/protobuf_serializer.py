"""
Protobuf serializer implementation

Serializes Python dicts/dataclasses to/from Protobuf binary format using the
phantom_protocol_schemas generated stubs.  The serializer works with generic
dicts (for any channel) and has first-class support for TaskRequest /
TaskResult messages used on the task_distribution channel.

This module requires the optional [grpc] extras:
    pip install .[grpc]

If grpcio / protobuf are not installed a clear ImportError is raised when the
module is first imported so that the factory layer can surface a helpful
message instead of silently falling back to JSON.
"""

import logging
from typing import Any, Optional, Type

try:
    from google.protobuf import json_format as _json_format
    from google.protobuf.message import Message as _ProtoMessage
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Protobuf support requires the [grpc] extras. "
        "Install with:  pip install .[grpc]"
    ) from exc

from ..interfaces import MessageSerializer, SerializationError, DeserializationError

logger = logging.getLogger(__name__)

# Schema version embedded in every message
SCHEMA_VERSION = "1"


class ProtobufSerializer(MessageSerializer):
    """
    Protobuf serialization for Phantom protocol messages.

    Uses the generated stubs in phantom_protocol_schemas to encode messages as
    binary Protobuf.  For generic (non-task) channels the serializer falls back
    to wrapping dicts as a TaskRequest with the dict fields stored in the
    ``parameters`` map.

    Typical usage (config-driven, see factory.py)::

        from phantom_protocol.serializers.protobuf_serializer import ProtobufSerializer
        s = ProtobufSerializer()
        data = s.serialize({"task_id": "t1", "task_type": "gpu_compute"})
        obj  = s.deserialize(data)
    """

    def __init__(self) -> None:
        # Import lazily so that the ImportError is deferred to instantiation
        # (the module-level import already guards against missing deps above).
        from phantom_protocol_schemas import task_pb2  # noqa: F401 – availability check

        self._task_pb2 = task_pb2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def serialize(self, obj: Any) -> bytes:
        """
        Convert Python object to Protobuf bytes.

        Supported input types:
        - dict with keys matching TaskRequest fields  → TaskRequest proto
        - dict with keys matching TaskResult fields   → TaskResult proto
        - google.protobuf.Message subclass            → SerializeToString()
        - dataclass                                   → converted to dict first

        Args:
            obj: Python object to serialize

        Returns:
            Binary Protobuf bytes

        Raises:
            SerializationError: If object cannot be serialized
        """
        try:
            # Already a proto Message – serialize directly
            if isinstance(obj, _ProtoMessage):
                return obj.SerializeToString()

            # Dataclass → dict
            if hasattr(obj, "__dataclass_fields__"):
                from dataclasses import asdict

                obj = asdict(obj)

            # Pydantic model → dict
            if hasattr(obj, "dict") and callable(obj.dict):
                obj = obj.dict()

            if not isinstance(obj, dict):
                raise SerializationError(
                    f"Protobuf serializer cannot handle type {type(obj).__name__}. "
                    "Pass a dict, dataclass, Pydantic model, or proto Message."
                )

            proto_msg = self._dict_to_proto(obj)
            return proto_msg.SerializeToString()

        except SerializationError:
            raise
        except Exception as exc:
            logger.error("Protobuf serialization failed: %s", exc)
            raise SerializationError(f"Protobuf serialization failed: {exc}") from exc

    def deserialize(self, data: bytes, message_type: Optional[Type] = None) -> Any:
        """
        Convert Protobuf bytes to Python object.

        Args:
            data: Binary Protobuf bytes
            message_type: Optional proto Message class to decode into.
                          If None, TaskResult is assumed (task_distribution default).

        Returns:
            dict representation of the deserialized message

        Raises:
            DeserializationError: If bytes cannot be deserialized
        """
        try:
            if message_type is None or message_type is dict:
                # Default: decode as TaskResult (controller receiving from worker)
                message_type = self._task_pb2.TaskResult

            if isinstance(message_type, type) and issubclass(
                message_type, _ProtoMessage
            ):
                msg = message_type()
                msg.ParseFromString(data)
                # Convert to plain dict for uniform downstream handling
                return _json_format.MessageToDict(msg, preserving_proto_field_name=True)

            # Fallback: try TaskResult then TaskRequest
            for proto_cls in (
                self._task_pb2.TaskResult,
                self._task_pb2.TaskRequest,
            ):
                try:
                    msg = proto_cls()
                    msg.ParseFromString(data)
                    return _json_format.MessageToDict(
                        msg, preserving_proto_field_name=True
                    )
                except Exception:
                    continue

            raise DeserializationError(
                "Could not decode Protobuf bytes as TaskResult or TaskRequest"
            )

        except DeserializationError:
            raise
        except Exception as exc:
            logger.error("Protobuf deserialization failed: %s", exc)
            raise DeserializationError(
                f"Protobuf deserialization failed: {exc}"
            ) from exc

    @property
    def content_type(self) -> str:
        """MIME type for Protobuf binary format"""
        return "application/x-protobuf"

    @property
    def name(self) -> str:
        """Serializer name"""
        return "protobuf"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dict_to_proto(self, d: dict) -> _ProtoMessage:
        """
        Heuristically map a dict to the appropriate proto Message type.

        TaskRequest is chosen when ``task_id`` and ``task_type`` are present.
        TaskResult is chosen when ``task_id`` and ``status`` are present.
        Otherwise TaskRequest is used as the default envelope.
        """
        task_pb2 = self._task_pb2

        # Determine message type
        if "task_type" in d:
            proto_msg = task_pb2.TaskRequest()
            proto_msg.task_id = str(d.get("task_id", ""))
            proto_msg.task_type = str(d.get("task_type", ""))
            proto_msg.schema_version = str(d.get("schema_version", SCHEMA_VERSION))
            proto_msg.correlation_id = str(d.get("correlation_id", ""))
            # Copy arbitrary parameters
            params = d.get("parameters", {})
            if isinstance(params, dict):
                for k, v in params.items():
                    proto_msg.parameters[str(k)] = str(v)
            # Copy remaining top-level keys into parameters
            _skip = {
                "task_id",
                "task_type",
                "schema_version",
                "correlation_id",
                "parameters",
            }
            for k, v in d.items():
                if k not in _skip:
                    proto_msg.parameters[str(k)] = str(v)
        elif "status" in d:
            proto_msg = task_pb2.TaskResult()
            proto_msg.task_id = str(d.get("task_id", ""))
            proto_msg.status = str(d.get("status", ""))
            proto_msg.schema_version = str(d.get("schema_version", SCHEMA_VERSION))
            proto_msg.correlation_id = str(d.get("correlation_id", ""))
            result = d.get("result", {})
            if isinstance(result, dict):
                for k, v in result.items():
                    proto_msg.result[str(k)] = str(v)
        else:
            # Generic fallback: wrap everything in parameters of a TaskRequest
            proto_msg = task_pb2.TaskRequest()
            proto_msg.schema_version = SCHEMA_VERSION
            for k, v in d.items():
                proto_msg.parameters[str(k)] = str(v)

        return proto_msg
