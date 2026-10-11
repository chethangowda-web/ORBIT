"""Memory Agent: Checkpointer provider, lifecycle management, and conversation coreference resolution."""

import time
import json
import logging
import random
import re
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence
import redis.asyncio as aioredis
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.memory import MemorySaver

from config import settings

logger = logging.getLogger(__name__)


class AsyncRedisCheckpointer(BaseCheckpointSaver):
    """Durable asynchronous Redis checkpoint saver for LangGraph."""

    def __init__(self, client: aioredis.Redis, ttl: int = 86400):
        super().__init__()
        self.client = client
        self.ttl = ttl

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        cp_id = str(checkpoint["id"])
        c = checkpoint.copy()
        values: dict[str, Any] = c.pop("channel_values", {})

        pipe = self.client.pipeline(transaction=True)
        for k, v in new_versions.items():
            blob_key = f"orbit:blob:{thread_id}:{checkpoint_ns}:{k}:{v}"
            blob_type, blob_bytes = self.serde.dumps_typed(values[k]) if k in values else ("empty", b"")
            payload = json.dumps({"type": blob_type, "data": blob_bytes.hex()})
            pipe.set(blob_key, payload, ex=self.ttl)

        parent_id = config["configurable"].get("checkpoint_id")
        c_type, c_bytes = self.serde.dumps_typed(c)
        m_type, m_bytes = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))

        cp_key = f"orbit:checkpoint:{thread_id}:{checkpoint_ns}:{cp_id}"
        cp_data = json.dumps({
            "checkpoint": {"type": c_type, "data": c_bytes.hex()},
            "metadata": {"type": m_type, "data": m_bytes.hex()},
            "parent_id": parent_id,
            "id": cp_id,
            "ts": checkpoint.get("ts"),
        })
        pipe.set(cp_key, cp_data, ex=self.ttl)

        # High-resolution monotonic timestamp score for deterministic latest checkpoint resolution
        thread_index_key = f"orbit:threads:{thread_id}:{checkpoint_ns}"
        score = time.time()
        pipe.zadd(thread_index_key, {cp_id: score})
        pipe.expire(thread_index_key, self.ttl)

        await pipe.execute()

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": cp_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate pending writes linked to a checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        writes_key = f"orbit:writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

        pipe = self.client.pipeline(transaction=True)
        for channel, val in writes:
            v_type, v_bytes = self.serde.dumps_typed(val)
            record = json.dumps({
                "task_id": task_id,
                "channel": channel,
                "type": v_type,
                "data": v_bytes.hex(),
                "task_path": task_path,
            })
            pipe.rpush(writes_key, record)
        pipe.expire(writes_key, self.ttl)
        await pipe.execute()

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if not checkpoint_id:
            thread_index_key = f"orbit:threads:{thread_id}:{checkpoint_ns}"
            latest = await self.client.zrevrange(thread_index_key, 0, 0)
            if not latest:
                return None
            checkpoint_id = latest[0].decode("utf-8") if isinstance(latest[0], bytes) else str(latest[0])

        cp_key = f"orbit:checkpoint:{thread_id}:{checkpoint_ns}:{checkpoint_id}"
        raw = await self.client.get(cp_key)
        if not raw:
            return None

        cp_data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
        c_raw = cp_data["checkpoint"]
        m_raw = cp_data["metadata"]

        checkpoint: Checkpoint = self.serde.loads_typed((c_raw["type"], bytes.fromhex(c_raw["data"])))
        metadata: CheckpointMetadata = self.serde.loads_typed((m_raw["type"], bytes.fromhex(m_raw["data"])))
        parent_id = cp_data.get("parent_id")

        # Load channel values
        channel_values = {}
        for k, v in checkpoint.get("channel_versions", {}).items():
            blob_key = f"orbit:blob:{thread_id}:{checkpoint_ns}:{k}:{v}"
            blob_raw = await self.client.get(blob_key)
            if blob_raw:
                b_parsed = json.loads(blob_raw if isinstance(blob_raw, str) else blob_raw.decode("utf-8"))
                # Skip empty blobs — channel had no value at checkpoint time
                if b_parsed.get("type") == "empty":
                    continue
                try:
                    channel_values[k] = self.serde.loads_typed((b_parsed["type"], bytes.fromhex(b_parsed["data"])))
                except Exception as deser_err:
                    logger.warning("Skipping undeserializable channel %s (type=%s): %s", k, b_parsed.get("type"), deser_err)
        checkpoint["channel_values"] = channel_values

        # Load pending intermediate writes
        writes_key = f"orbit:writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}"
        raw_writes = await self.client.lrange(writes_key, 0, -1)
        pending_writes: list[tuple[str, str, Any]] = []
        for raw_w in raw_writes:
            try:
                w_parsed = json.loads(raw_w if isinstance(raw_w, str) else raw_w.decode("utf-8"))
                w_val = self.serde.loads_typed((w_parsed["type"], bytes.fromhex(w_parsed["data"])))
                pending_writes.append((w_parsed["task_id"], w_parsed["channel"], w_val))
            except Exception as write_err:
                logger.warning("Failed to deserialize pending write: %s", write_err)

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_id,
                }
            } if parent_id else None,
            pending_writes=pending_writes,
        )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Asynchronously list checkpoints matching criteria."""
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        config_cp_id = get_checkpoint_id(config)
        before_cp_id = get_checkpoint_id(before) if before else None

        thread_index_key = f"orbit:threads:{thread_id}:{checkpoint_ns}"
        cp_ids_raw = await self.client.zrevrange(thread_index_key, 0, -1)
        if not cp_ids_raw:
            return

        yielded_count = 0
        for cp_item in cp_ids_raw:
            cp_id = cp_item.decode("utf-8") if isinstance(cp_item, bytes) else str(cp_item)

            # Filter by specific checkpoint_id if provided
            if config_cp_id and cp_id != config_cp_id:
                continue

            # Filter by before_checkpoint_id if provided
            if before_cp_id and cp_id >= before_cp_id:
                continue

            # Check limit
            if limit is not None and yielded_count >= limit:
                break

            # Fetch tuple
            cp_tuple = await self.aget_tuple({
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": cp_id,
                }
            })
            if not cp_tuple:
                continue

            # Filter by metadata if requested
            if filter and not all(query_val == cp_tuple.metadata.get(query_key) for query_key, query_val in filter.items()):
                continue

            yield cp_tuple
            yielded_count += 1

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"


# Global checkpointer state
_redis_client: Optional[aioredis.Redis] = None
_checkpointer_instance: Optional[BaseCheckpointSaver] = None
_checkpointer_mode: str = "uninitialized"
_is_durable: bool = False
_redis_connected: bool = False


async def init_checkpointer() -> BaseCheckpointSaver:
    """Initialize checkpointer with Redis or explicit dev fallback."""
    global _redis_client, _checkpointer_instance, _checkpointer_mode, _is_durable, _redis_connected

    if getattr(settings, "CHECKPOINTER_BACKEND", "redis") == "redis":
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=getattr(settings, "REDIS_CONNECT_TIMEOUT", 3.0),
                socket_timeout=getattr(settings, "REDIS_SOCKET_TIMEOUT", 5.0),
                decode_responses=False,
            )
            await client.ping()
            _redis_client = client
            _checkpointer_instance = AsyncRedisCheckpointer(client)
            _checkpointer_mode = "redis"
            _is_durable = True
            _redis_connected = True
            logger.info("Durable Redis Checkpointer initialized successfully at %s", settings.REDIS_URL)
            return _checkpointer_instance
        except Exception as exc:
            _redis_connected = False
            if getattr(settings, "ENVIRONMENT", "development") == "production" and not getattr(
                settings, "ALLOW_IN_MEMORY_CHECKPOINTER_FALLBACK", False
            ):
                _checkpointer_mode = "error"
                _is_durable = False
                logger.critical("Redis checkpointer failed in production: %s", exc)
                raise RuntimeError(f"Durable checkpointer unavailable: {exc}") from exc

            logger.warning(
                "Redis unavailable (%s). Using explicit development fallback to MemorySaver (is_durable=False).",
                exc,
            )
            _checkpointer_instance = MemorySaver()
            _checkpointer_mode = "memory_fallback"
            _is_durable = False
            return _checkpointer_instance
    else:
        _checkpointer_instance = MemorySaver()
        _checkpointer_mode = "memory"
        _is_durable = False
        _redis_connected = False
        return _checkpointer_instance


async def close_checkpointer() -> None:
    """Close Redis client connections on shutdown."""
    global _redis_client, _checkpointer_instance, _redis_connected
    if _redis_client:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning("Error closing checkpointer Redis client: %s", e)
        _redis_client = None
        _redis_connected = False


def get_checkpointer() -> BaseCheckpointSaver:
    """Returns the currently active checkpointer instance."""
    global _checkpointer_instance
    if _checkpointer_instance is None:
        _checkpointer_instance = MemorySaver()
    return _checkpointer_instance


async def get_checkpointer_status() -> Dict[str, Any]:
    """Retrieve detailed checkpointer health, backend, and durability status."""
    global _redis_client, _checkpointer_mode, _is_durable, _redis_connected
    connected = False
    if _redis_client:
        try:
            await _redis_client.ping()
            connected = True
        except Exception:
            connected = False

    return {
        "backend": "redis" if _is_durable else "memory",
        "is_durable": _is_durable,
        "connected": connected,
        "mode": _checkpointer_mode,
    }


def make_thread_id(space_id: str, user_id: str) -> str:
    """Generates standard thread ID: space_id:user_id."""
    return f"{space_id}:{user_id}"


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# Whole words only: "it" must not match "edit" or "submit", nor "the task" inside "the task deadline".
_REFERENCE_RE = re.compile(r"\b(it|that task|this task|the task|same task|that one|this one)\b", re.IGNORECASE)


def extract_task_id_from_text(text: str) -> Optional[str]:
    """Extracts a task UUID from message text. Only a full UUID counts: a looser pattern turned
    ordinary words such as "task deadline" into the id "dead"."""
    match = _UUID_RE.search(text)
    return match.group(0) if match else None


def mentions_previous_task(text: str) -> bool:
    """True when the message refers back to a task ("make it high priority", "that task")."""
    return bool(_REFERENCE_RE.search(text))


def resolve_references(raw_message: str, messages: list[BaseMessage]) -> Optional[str]:
    """Resolves 'it', 'that task', 'the task' to the most recently mentioned task ID in conversation history."""
    if not mentions_previous_task(raw_message):
        return None

    for m in reversed(messages):
        if isinstance(m, AIMessage) or hasattr(m, "content"):
            content = str(m.content)
            found_id = extract_task_id_from_text(content)
            if found_id:
                return found_id
    return None
