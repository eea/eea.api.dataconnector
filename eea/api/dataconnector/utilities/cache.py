"""Generic caching utilities for plone.memoize.ram"""

import json
import logging
import os
import hashlib
from threading import local

from zope import component
from zope.interface import implementer
from zope.ramcache.interfaces.ram import IRAMCache

from plone.memoize.interfaces import ICacheChooser
from plone.memoize.ram import AbstractDict, RAMCacheAdapter

logger = logging.getLogger(__name__)


class MemcacheAdapter(AbstractDict):
    """Memcache adapter with TTL support using JSON serialization."""

    def __init__(self, client, globalkey, ttl=300):
        super().__init__()
        self.client = client
        self.globalkey = globalkey
        self.ttl = ttl

    def _make_key(self, key):
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key
        return hashlib.sha1(key_bytes).hexdigest()

    def _storage_key(self, key):
        return f"{self.globalkey}:{self._make_key(key)}"

    def __contains__(self, key):
        value = self.client.get(self._storage_key(key))
        return value is not None

    def __getitem__(self, key):
        value = self.client.get(self._storage_key(key))
        if value is None:
            raise KeyError(key)
        return json.loads(value)

    def __setitem__(self, key, value):
        self.client.set(self._storage_key(key), json.dumps(value), time=self.ttl)

    def __delitem__(self, key):
        self.client.delete(self._storage_key(key))


class RedisCacheAdapter(AbstractDict):
    """Dict-like adapter that stores cache entries in Redis."""

    def __init__(self, client, globalkey, ttl=300):
        super().__init__()
        self.client = client
        self.globalkey = globalkey
        self.ttl = ttl

    def _redis_key(self, key):
        return f"{self.globalkey}:{key}"

    def __contains__(self, key):
        return self.client.exists(self._redis_key(key))

    def __getitem__(self, key):
        value = self.client.get(self._redis_key(key))
        if value is None:
            raise KeyError(key)
        return json.loads(value)

    def __setitem__(self, key, value):
        self.client.setex(self._redis_key(key), self.ttl, json.dumps(value))

    def __delitem__(self, key):
        self.client.delete(self._redis_key(key))


@implementer(ICacheChooser)
class CacheChooser:
    """ICacheChooser with cascading fallback: Redis -> Memcached -> RAM.

    Configuration via environment variables:
    - CACHE_BACKEND_ORDER: Comma-separated list of backends (default: redis,memcached,ram)
    - CACHE_TTL: Cache TTL in seconds (default: 300)

    Redis configuration:
    - REDIS_ENABLED: Enable/disable Redis (default: false)
    - REDIS_SERVER: Redis host (default: localhost)
    - REDIS_PORT: Redis port (default: 6379)
    - REDIS_DB: Redis database index (default: 0)
    - REDIS_TIMEOUT: Socket connect timeout (default: 5)

    Memcached configuration:
    - MEMCACHED_ENABLED: Enable/disable Memcached (default: false)
    - MEMCACHED_SERVER: Comma-separated servers (default: 127.0.0.1:11211)
    - MEMCACHED_TIMEOUT: Connection timeout (default: 5)
    """

    _v_thread_local = local()

    @property
    def backend_order(self):
        order = os.environ.get("CACHE_BACKEND_ORDER", "redis,memcached,ram")
        return [b.strip().lower() for b in order.split(",")]

    @property
    def ttl(self):
        try:
            return int(os.environ.get("CACHE_TTL", 300))
        except ValueError:
            return 300

    @property
    def redis_enabled(self):
        return os.environ.get("REDIS_ENABLED", "false").lower() != "false"

    @property
    def memcached_enabled(self):
        return os.environ.get("MEMCACHED_ENABLED", "false").lower() != "false"

    @property
    def redis_timeout(self):
        try:
            return int(os.environ.get("REDIS_TIMEOUT", 5))
        except ValueError:
            return 5

    @property
    def redis_db(self):
        try:
            return int(os.environ.get("REDIS_DB", 0))
        except ValueError:
            return 0

    @property
    def redis_server(self):
        return os.environ.get("REDIS_SERVER", "localhost")

    @property
    def redis_port(self):
        try:
            return int(os.environ.get("REDIS_PORT", 6379))
        except Exception:
            return 6379

    @property
    def memcached_servers(self):
        return os.environ.get("MEMCACHED_SERVER", "127.0.0.1:11211")

    @property
    def memcached_timeout(self):
        try:
            return int(os.environ.get("MEMCACHED_TIMEOUT", 5))
        except ValueError:
            return 5

    def _get_redis_client(self):
        if not self.redis_enabled:
            return None

        conn = getattr(self._v_thread_local, "redis_connection", None)
        if conn == "broken":
            return None
        if conn is not None:
            try:
                conn.ping()
                return conn
            except Exception:
                self._v_thread_local.redis_connection = "broken"
                return None

        if conn is None:
            try:
                from redis import Redis

                conn = Redis(
                    host=self.redis_server,
                    port=self.redis_port,
                    db=self.redis_db,
                    socket_connect_timeout=self.redis_timeout,
                    decode_responses=True,
                )
                conn.ping()
                self._v_thread_local.redis_connection = conn
                return conn
            except Exception as err:
                logger.warning("Redis unavailable: %s", err)
                self._v_thread_local.redis_connection = "broken"
                return None
        return conn

    def _get_memcache_client(self):
        if not self.memcached_enabled:
            return None

        client = getattr(self._v_thread_local, "memcache_connection", None)

        if client == "broken":
            return None

        if client is not None:
            try:
                stats = client.get_stats()
                if not stats:
                    self._v_thread_local.memcache_connection = "broken"
                    return None
            except Exception:
                self._v_thread_local.memcache_connection = "broken"
                return None
            return client

        try:
            import memcache

            servers = [s.strip() for s in self.memcached_servers.split(",")]
            client = memcache.Client(servers, socket_timeout=self.memcached_timeout)
            self._v_thread_local.memcache_connection = client
            return client
        except Exception as err:
            logger.warning("Memcached unavailable: %s", err)
            self._v_thread_local.memcache_connection = "broken"
            return None

    def __call__(self, fun_name):
        for backend in self.backend_order:
            if backend == "redis":
                client = self._get_redis_client()
                if client is not None:
                    logger.debug("Using Redis cache for %s", fun_name)
                    return RedisCacheAdapter(
                        client=client,
                        globalkey=fun_name,
                        ttl=self.ttl,
                    )

            elif backend == "memcached":
                client = self._get_memcache_client()
                if client is not None:
                    logger.debug("Using Memcached cache for %s", fun_name)
                    return MemcacheAdapter(
                        client=client,
                        globalkey=fun_name,
                        ttl=self.ttl,
                    )

            elif backend == "ram":
                logger.debug("Using RAM cache for %s", fun_name)
                return RAMCacheAdapter(
                    ramcache=component.queryUtility(IRAMCache),
                    globalkey=fun_name,
                )

        logger.debug("Using RAM cache for %s", fun_name)
        return RAMCacheAdapter(
            ramcache=component.queryUtility(IRAMCache),
            globalkey=fun_name,
        )
