"""Prometheus metrics (opt-in via METRICS_ENABLED).

Labels are deliberately low-cardinality: HTTP paths use the matched route template
("/api/tasks/{task_id}"), never the raw URL, and no user or task identifiers appear.
"""

from typing import Any, Mapping

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

registry = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "orbit_http_requests_total",
    "HTTP requests handled",
    ["method", "path", "status"],
    registry=registry,
)
HTTP_LATENCY = Histogram(
    "orbit_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=registry,
)
AGENT_RUNS = Counter(
    "orbit_agent_runs_total",
    "Agent graph executions",
    ["intent", "status"],
    registry=registry,
)
AGENT_LATENCY = Histogram(
    "orbit_agent_run_duration_seconds",
    "End to end agent run time in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
    registry=registry,
)
TOOL_CALLS = Counter(
    "orbit_tool_calls_total",
    "Agent tool invocations",
    ["tool"],
    registry=registry,
)
NOTIFICATIONS = Counter(
    "orbit_notifications_total",
    "Notification deliveries by outcome",
    ["type", "status"],
    registry=registry,
)


def record_http(method: str, path: str, status: int, seconds: float) -> None:
    HTTP_REQUESTS.labels(method, path, str(status)).inc()
    HTTP_LATENCY.labels(method, path).observe(seconds)


def record_agent_run(trace: Mapping[str, Any]) -> None:
    """Record one orchestrator result (the same dict persisted as a trace row)."""
    AGENT_RUNS.labels(str(trace.get("intent") or "UNKNOWN"), str(trace.get("status") or "UNKNOWN")).inc()
    AGENT_LATENCY.observe(float(trace.get("total_duration_ms") or 0.0) / 1000.0)
    for tool in trace.get("tool_calls_made") or []:
        TOOL_CALLS.labels(str(tool)).inc()


def record_notification(type_: str, status: str) -> None:
    NOTIFICATIONS.labels(type_, status).inc()


def render() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
