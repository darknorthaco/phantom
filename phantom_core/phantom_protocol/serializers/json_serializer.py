"""JSON serializer implementation"""

import json
import logging
from typing import Any, Optional, Type
from datetime import datetime
from ..interfaces import MessageSerializer, SerializationError, DeserializationError

logger = logging.getLogger(__name__)


class JSONSerializer(MessageSerializer):
    """
    JSON serialization implementation

    Converts Python objects to/from JSON format. Supports:
    - Dict, list, str, int, float, bool, None
    - Pydantic models (via .dict() method)
    - Dataclasses (via dataclasses.asdict)
    - Custom objects with __dict__ attribute
    """

    def __init__(self, ensure_ascii: bool = False, indent: Optional[int] = None):
        """
        Initialize JSON serializer

        Args:
            ensure_ascii: If True, escape non-ASCII characters
            indent: Indentation level for pretty-printing (None for compact)
        """
        self.ensure_ascii = ensure_ascii
        self.indent = indent

    def serialize(self, obj: Any) -> bytes:
        """
        Convert Python object to JSON bytes

        Args:
            obj: Python object to serialize

        Returns:
            UTF-8 encoded JSON bytes

        Raises:
            SerializationError: If object cannot be serialized
        """
        try:
            # Handle Pydantic models
            if hasattr(obj, "dict") and callable(obj.dict):
                obj = obj.dict()

            # Handle dataclasses
            elif hasattr(obj, "__dataclass_fields__"):
                from dataclasses import asdict

                obj = asdict(obj)

            # Handle datetime objects
            def default_handler(o):
                if isinstance(o, datetime):
                    return o.isoformat()
                elif hasattr(o, "__dict__"):
                    return o.__dict__
                raise TypeError(f"Object of type {type(o)} is not JSON serializable")

            json_str = json.dumps(
                obj,
                ensure_ascii=self.ensure_ascii,
                indent=self.indent,
                default=default_handler,
            )

            return json_str.encode("utf-8")

        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed: {e}")
            raise SerializationError(f"JSON serialization failed: {e}") from e

    def deserialize(self, data: bytes, message_type: Optional[Type] = None) -> Any:
        """
        Convert JSON bytes to Python object

        Args:
            data: UTF-8 encoded JSON bytes
            message_type: Optional type hint for deserialization (Pydantic model, etc.)

        Returns:
            Deserialized Python object

        Raises:
            DeserializationError: If bytes cannot be deserialized
        """
        try:
            json_str = data.decode("utf-8")
            obj = json.loads(json_str)

            # If message_type is provided and is a Pydantic model, instantiate it
            if message_type is not None:
                if hasattr(message_type, "parse_obj"):
                    # Pydantic model
                    return message_type.parse_obj(obj)
                elif hasattr(message_type, "__dataclass_fields__"):
                    # Dataclass
                    return message_type(**obj)
                else:
                    # Try direct instantiation
                    return (
                        message_type(obj) if not isinstance(obj, message_type) else obj
                    )

            return obj

        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"JSON deserialization failed: {e}")
            raise DeserializationError(f"JSON deserialization failed: {e}") from e

    @property
    def content_type(self) -> str:
        """MIME type for JSON"""
        return "application/json"

    @property
    def name(self) -> str:
        """Serializer name"""
        return "json"
