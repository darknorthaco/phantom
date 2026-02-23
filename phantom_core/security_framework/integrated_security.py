"""
Integrated Security Framework for Phantom Distributed System
Ground-up security integration with multiple security levels
"""

import asyncio
import logging
import hashlib
import secrets
import jwt
import time
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import ipaddress

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    DISABLED = "disabled"
    BASIC = "basic"
    ENHANCED = "enhanced"
    ENTERPRISE = "enterprise"


@dataclass
class SecurityConfig:
    level: SecurityLevel
    api_keys_enabled: bool = False
    jwt_tokens_enabled: bool = False
    rate_limiting_enabled: bool = False
    ip_filtering_enabled: bool = False
    session_management_enabled: bool = False
    audit_logging_enabled: bool = False
    encryption_enabled: bool = False


class SecurityManager:
    """Integrated security manager with multiple security levels"""

    def __init__(self, security_level: str = "disabled"):
        self.security_level = SecurityLevel(security_level)
        self.config = self._create_config()

        # Security state
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        self.jwt_secret = secrets.token_urlsafe(32)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.rate_limits: Dict[str, List[float]] = {}
        self.blocked_ips: Set[str] = set()
        self.allowed_ips: Set[str] = set()

        # Audit logging
        self.audit_log: List[Dict[str, Any]] = []
        self.max_audit_entries = 10000

        # Security metrics
        self.metrics = {
            "authentication_attempts": 0,
            "authentication_failures": 0,
            "rate_limit_violations": 0,
            "blocked_requests": 0,
            "security_events": 0,
        }

    def _create_config(self) -> SecurityConfig:
        """Create security configuration based on level"""
        if self.security_level == SecurityLevel.DISABLED:
            return SecurityConfig(
                level=self.security_level,
                api_keys_enabled=False,
                jwt_tokens_enabled=False,
                rate_limiting_enabled=False,
                ip_filtering_enabled=False,
                session_management_enabled=False,
                audit_logging_enabled=False,
                encryption_enabled=False,
            )

        elif self.security_level == SecurityLevel.BASIC:
            return SecurityConfig(
                level=self.security_level,
                api_keys_enabled=True,
                jwt_tokens_enabled=False,
                rate_limiting_enabled=True,
                ip_filtering_enabled=False,
                session_management_enabled=False,
                audit_logging_enabled=True,
                encryption_enabled=False,
            )

        elif self.security_level == SecurityLevel.ENHANCED:
            return SecurityConfig(
                level=self.security_level,
                api_keys_enabled=True,
                jwt_tokens_enabled=True,
                rate_limiting_enabled=True,
                ip_filtering_enabled=True,
                session_management_enabled=True,
                audit_logging_enabled=True,
                encryption_enabled=False,
            )

        elif self.security_level == SecurityLevel.ENTERPRISE:
            return SecurityConfig(
                level=self.security_level,
                api_keys_enabled=True,
                jwt_tokens_enabled=True,
                rate_limiting_enabled=True,
                ip_filtering_enabled=True,
                session_management_enabled=True,
                audit_logging_enabled=True,
                encryption_enabled=True,
            )

    async def initialize(self):
        """Initialize security framework"""
        try:
            logger.info(
                f"🔒 Initializing security framework (level: {self.security_level.value})"
            )

            if self.config.api_keys_enabled:
                await self._initialize_api_keys()

            if self.config.jwt_tokens_enabled:
                await self._initialize_jwt()

            if self.config.ip_filtering_enabled:
                await self._initialize_ip_filtering()

            if self.config.session_management_enabled:
                await self._initialize_session_management()

            # Start background tasks
            if self.security_level != SecurityLevel.DISABLED:
                asyncio.create_task(self._security_maintenance_loop())

            logger.info(
                f"✅ Security framework initialized ({self.security_level.value})"
            )

        except Exception as e:
            logger.error(f"Security framework initialization failed: {e}")
            raise

    async def _initialize_api_keys(self):
        """Initialize API key system"""
        # Create default API keys for development
        if self.security_level == SecurityLevel.BASIC:
            await self.create_api_key("development", ["read", "write"], expires_days=30)
        else:
            await self.create_api_key("admin", ["admin"], expires_days=7)
            await self.create_api_key("worker", ["worker"], expires_days=30)
            await self.create_api_key("ui", ["read"], expires_days=1)

        logger.info("🔑 API key system initialized")

    async def _initialize_jwt(self):
        """Initialize JWT token system"""
        # JWT configuration
        self.jwt_config = {
            "algorithm": "HS256",
            "access_token_expire_minutes": 60,
            "refresh_token_expire_days": 7,
        }

        logger.info("🎫 JWT token system initialized")

    async def _initialize_ip_filtering(self):
        """Initialize IP filtering"""
        # Default allowed IPs for development
        self.allowed_ips.update(
            [
                "127.0.0.1",
                "::1",
                "192.168.1.0/24",  # Local network
                "10.0.0.0/8",  # Private network
                "172.16.0.0/12",  # Private network
            ]
        )

        logger.info("🌐 IP filtering initialized")

    async def _initialize_session_management(self):
        """Initialize session management"""
        self.session_config = {
            "session_timeout_minutes": 30,
            "max_sessions_per_user": 5,
            "session_cleanup_interval": 300,  # 5 minutes
        }

        logger.info("📋 Session management initialized")

    async def authenticate_request(self, request) -> Dict[str, Any]:
        """Authenticate incoming request"""
        if self.security_level == SecurityLevel.DISABLED:
            return {"user_id": "anonymous", "permissions": ["all"]}

        try:
            # Extract client IP
            client_ip = self._get_client_ip(request)

            # Check IP filtering
            if self.config.ip_filtering_enabled:
                if not await self._check_ip_allowed(client_ip):
                    await self._log_security_event("ip_blocked", {"ip": client_ip})
                    raise SecurityException("IP address not allowed")

            # Check rate limiting
            if self.config.rate_limiting_enabled:
                if not await self._check_rate_limit(client_ip):
                    await self._log_security_event(
                        "rate_limit_exceeded", {"ip": client_ip}
                    )
                    raise SecurityException("Rate limit exceeded")

            # Extract authentication credentials
            auth_header = request.headers.get("Authorization", "")
            api_key = request.headers.get("X-API-Key", "")

            user_info = None

            # Try JWT authentication first
            if self.config.jwt_tokens_enabled and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                user_info = await self._authenticate_jwt(token)

            # Try API key authentication
            elif self.config.api_keys_enabled and api_key:
                user_info = await self._authenticate_api_key(api_key)

            # Require authentication for non-disabled levels
            if not user_info:
                self.metrics["authentication_failures"] += 1
                await self._log_security_event(
                    "authentication_failed", {"ip": client_ip}
                )
                raise SecurityException("Authentication required")

            # Update session if enabled
            if self.config.session_management_enabled:
                await self._update_session(user_info, client_ip)

            self.metrics["authentication_attempts"] += 1
            await self._log_security_event(
                "authentication_success",
                {"user_id": user_info.get("user_id"), "ip": client_ip},
            )

            return user_info

        except SecurityException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise SecurityException("Authentication failed")

    async def _authenticate_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate JWT token"""
        try:
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_config["algorithm"]]
            )

            # Check expiration
            if payload.get("exp", 0) < time.time():
                return None

            return {
                "user_id": payload.get("sub"),
                "permissions": payload.get("permissions", []),
                "auth_method": "jwt",
            }

        except jwt.InvalidTokenError:
            return None

    async def _authenticate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Authenticate API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        if key_hash in self.api_keys:
            key_info = self.api_keys[key_hash]

            # Check expiration
            if key_info.get("expires_at") and datetime.now() > key_info["expires_at"]:
                return None

            return {
                "user_id": key_info["name"],
                "permissions": key_info["permissions"],
                "auth_method": "api_key",
            }

        return None

    async def _check_ip_allowed(self, client_ip: str) -> bool:
        """Check if IP address is allowed"""
        if client_ip in self.blocked_ips:
            return False

        if not self.allowed_ips:
            return True  # No restrictions if no allowed IPs configured

        try:
            client_addr = ipaddress.ip_address(client_ip)

            for allowed in self.allowed_ips:
                if "/" in allowed:
                    # CIDR notation
                    if client_addr in ipaddress.ip_network(allowed, strict=False):
                        return True
                else:
                    # Single IP
                    if str(client_addr) == allowed:
                        return True

            return False

        except ValueError:
            # Invalid IP address
            return False

    async def _check_rate_limit(self, client_ip: str) -> bool:
        """Check rate limiting for client IP"""
        current_time = time.time()

        # Rate limit configuration based on security level
        if self.security_level == SecurityLevel.BASIC:
            max_requests = 100
            window_seconds = 60
        elif self.security_level == SecurityLevel.ENHANCED:
            max_requests = 50
            window_seconds = 60
        else:  # ENTERPRISE
            max_requests = 30
            window_seconds = 60

        # Get request history for this IP
        if client_ip not in self.rate_limits:
            self.rate_limits[client_ip] = []

        request_times = self.rate_limits[client_ip]

        # Remove old requests outside the window
        cutoff_time = current_time - window_seconds
        request_times[:] = [t for t in request_times if t > cutoff_time]

        # Check if limit exceeded
        if len(request_times) >= max_requests:
            self.metrics["rate_limit_violations"] += 1
            return False

        # Add current request
        request_times.append(current_time)
        return True

    async def _update_session(self, user_info: Dict[str, Any], client_ip: str):
        """Update user session"""
        user_id = user_info.get("user_id")
        session_id = hashlib.sha256(
            f"{user_id}:{client_ip}:{time.time()}".encode()
        ).hexdigest()

        # Clean up old sessions for this user
        user_sessions = [
            sid
            for sid, session in self.active_sessions.items()
            if session.get("user_id") == user_id
        ]

        if len(user_sessions) >= self.session_config["max_sessions_per_user"]:
            # Remove oldest session
            oldest_session = min(
                user_sessions, key=lambda sid: self.active_sessions[sid]["created_at"]
            )
            del self.active_sessions[oldest_session]

        # Create new session
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "client_ip": client_ip,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
        }

    async def create_api_key(
        self, name: str, permissions: List[str], expires_days: Optional[int] = None
    ) -> str:
        """Create a new API key"""
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)

        self.api_keys[key_hash] = {
            "name": name,
            "permissions": permissions,
            "created_at": datetime.now(),
            "expires_at": expires_at,
        }

        logger.info(f"🔑 Created API key for {name} with permissions {permissions}")
        return api_key

    async def create_jwt_token(
        self, user_id: str, permissions: List[str]
    ) -> Dict[str, str]:
        """Create JWT access and refresh tokens"""
        current_time = time.time()

        # Access token
        access_payload = {
            "sub": user_id,
            "permissions": permissions,
            "iat": current_time,
            "exp": current_time + (self.jwt_config["access_token_expire_minutes"] * 60),
        }

        access_token = jwt.encode(
            access_payload, self.jwt_secret, algorithm=self.jwt_config["algorithm"]
        )

        # Refresh token
        refresh_payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": current_time,
            "exp": current_time
            + (self.jwt_config["refresh_token_expire_days"] * 24 * 60 * 60),
        }

        refresh_token = jwt.encode(
            refresh_payload, self.jwt_secret, algorithm=self.jwt_config["algorithm"]
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.jwt_config["access_token_expire_minutes"] * 60,
        }

    async def _log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security event for audit"""
        if not self.config.audit_logging_enabled:
            return

        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details,
        }

        self.audit_log.append(event)
        self.metrics["security_events"] += 1

        # Keep audit log size manageable
        if len(self.audit_log) > self.max_audit_entries:
            self.audit_log = self.audit_log[-self.max_audit_entries // 2 :]

        # Log critical events
        if event_type in ["authentication_failed", "rate_limit_exceeded", "ip_blocked"]:
            logger.warning(f"Security event: {event_type} - {details}")

    def _get_client_ip(self, request) -> str:
        """Extract client IP from request.

        Only the direct connection IP is used to avoid IP-spoofing via
        proxy headers (X-Forwarded-For, etc.).  When running behind a
        trusted reverse proxy, configure the proxy to set the real client
        IP on the connection itself (e.g. using PROXY protocol or
        uvicorn's ``--proxy-headers`` with a trusted front-end).
        """
        if hasattr(request, "client") and hasattr(request.client, "host"):
            return request.client.host

        return "unknown"

    async def _security_maintenance_loop(self):
        """Background security maintenance tasks"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up expired sessions
                if self.config.session_management_enabled:
                    await self._cleanup_expired_sessions()

                # Clean up rate limit history
                await self._cleanup_rate_limits()

                # Clean up expired API keys
                await self._cleanup_expired_api_keys()

            except Exception as e:
                logger.error(f"Security maintenance error: {e}")

    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.now()
        timeout = timedelta(minutes=self.session_config["session_timeout_minutes"])

        expired_sessions = [
            sid
            for sid, session in self.active_sessions.items()
            if current_time - session["last_activity"] > timeout
        ]

        for session_id in expired_sessions:
            del self.active_sessions[session_id]

        if expired_sessions:
            logger.debug(f"Cleaned up {len(expired_sessions)} expired sessions")

    async def _cleanup_rate_limits(self):
        """Clean up old rate limit entries"""
        current_time = time.time()
        cutoff_time = current_time - 3600  # Keep 1 hour of history

        for ip in list(self.rate_limits.keys()):
            self.rate_limits[ip] = [t for t in self.rate_limits[ip] if t > cutoff_time]

            # Remove empty entries
            if not self.rate_limits[ip]:
                del self.rate_limits[ip]

    async def _cleanup_expired_api_keys(self):
        """Clean up expired API keys"""
        current_time = datetime.now()

        expired_keys = [
            key_hash
            for key_hash, key_info in self.api_keys.items()
            if key_info.get("expires_at") and current_time > key_info["expires_at"]
        ]

        for key_hash in expired_keys:
            del self.api_keys[key_hash]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired API keys")

    async def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status"""
        return {
            "security_level": self.security_level.value,
            "config": {
                "api_keys_enabled": self.config.api_keys_enabled,
                "jwt_tokens_enabled": self.config.jwt_tokens_enabled,
                "rate_limiting_enabled": self.config.rate_limiting_enabled,
                "ip_filtering_enabled": self.config.ip_filtering_enabled,
                "session_management_enabled": self.config.session_management_enabled,
                "audit_logging_enabled": self.config.audit_logging_enabled,
                "encryption_enabled": self.config.encryption_enabled,
            },
            "metrics": self.metrics,
            "active_sessions": len(self.active_sessions),
            "api_keys_count": len(self.api_keys),
            "blocked_ips_count": len(self.blocked_ips),
            "allowed_ips_count": len(self.allowed_ips),
            "audit_log_size": len(self.audit_log),
        }

    async def block_ip(self, ip_address: str, reason: str = "Manual block"):
        """Block an IP address"""
        self.blocked_ips.add(ip_address)
        await self._log_security_event(
            "ip_manually_blocked", {"ip": ip_address, "reason": reason}
        )
        logger.info(f"🚫 Blocked IP address: {ip_address} ({reason})")

    async def unblock_ip(self, ip_address: str):
        """Unblock an IP address"""
        self.blocked_ips.discard(ip_address)
        await self._log_security_event("ip_unblocked", {"ip": ip_address})
        logger.info(f"✅ Unblocked IP address: {ip_address}")

    async def revoke_api_key(self, api_key: str):
        """Revoke an API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if key_hash in self.api_keys:
            key_name = self.api_keys[key_hash]["name"]
            del self.api_keys[key_hash]
            await self._log_security_event("api_key_revoked", {"key_name": key_name})
            logger.info(f"🔑 Revoked API key: {key_name}")


class SecurityException(Exception):
    """Security-related exception"""

    pass


# Security configuration presets
SECURITY_PRESETS = {
    "development": {
        "level": "basic",
        "allowed_ips": ["127.0.0.1", "::1", "192.168.0.0/16"],
        "rate_limit": {"requests": 1000, "window": 60},
    },
    "staging": {
        "level": "enhanced",
        "allowed_ips": ["10.0.0.0/8", "172.16.0.0/12"],
        "rate_limit": {"requests": 100, "window": 60},
    },
    "production": {
        "level": "enterprise",
        "allowed_ips": [],  # Configure as needed
        "rate_limit": {"requests": 50, "window": 60},
    },
}


# Utility functions
async def create_security_manager(preset: str = "development") -> SecurityManager:
    """Create and initialize security manager with preset configuration"""
    if preset not in SECURITY_PRESETS:
        raise ValueError(f"Unknown security preset: {preset}")

    config = SECURITY_PRESETS[preset]
    manager = SecurityManager(config["level"])

    await manager.initialize()

    # Apply preset configuration
    if config.get("allowed_ips"):
        manager.allowed_ips.update(config["allowed_ips"])

    return manager


# Example usage and testing
if __name__ == "__main__":

    async def test_security_framework():
        print("Testing Security Framework...")

        # Test different security levels
        for level in ["disabled", "basic", "enhanced", "enterprise"]:
            print(f"\n--- Testing {level.upper()} security level ---")

            manager = SecurityManager(level)
            await manager.initialize()

            status = await manager.get_security_status()
            print(f"Security status: {status}")

            if level != "disabled":
                # Create test API key
                api_key = await manager.create_api_key("test", ["read", "write"])
                print(f"Created API key: {api_key[:16]}...")

                # Create JWT token
                if manager.config.jwt_tokens_enabled:
                    tokens = await manager.create_jwt_token("test_user", ["read"])
                    print(f"Created JWT token: {tokens['access_token'][:32]}...")

    asyncio.run(test_security_framework())
