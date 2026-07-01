"""Architectural pattern knowledge base — 10 entries.

Every `common_mistake` field is mandatory and explicit: it names the specific
wrong thing models confidently recommend, which is the core anti-hallucination
mechanism for the query engine.

Every entry has a `citation` URL.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternEntry:
    name: str
    aliases: list[str]
    when_to_use: str
    when_not_to_use: str
    operational_cost: str       # what you pay to run this pattern in production
    common_mistake: str         # the specific wrong use case models confidently recommend
    citation: str


PATTERN_KB: list[PatternEntry] = [
    PatternEntry(
        name="CQRS",
        aliases=[
            "command query responsibility segregation",
            "cqrs pattern", "command query separation",
        ],
        when_to_use=(
            "read and write loads differ significantly in shape or volume; "
            "read model needs denormalization the write model cannot provide; "
            "event-sourced systems that naturally produce separate read projections"
        ),
        when_not_to_use=(
            "simple CRUD applications, small teams, early-stage product; "
            "most apps have similar read and write shapes and gain nothing from the split"
        ),
        operational_cost=(
            "maintain two separate models and keep them in sync (event-driven or polling); "
            "two deployment units; reads are eventually consistent by default"
        ),
        common_mistake=(
            "applying CQRS by default to every service as overhead and complexity "
            "with no benefit; CRUD apps do not need CQRS and the dual codepath "
            "slows the team down for no architectural gain"
        ),
        citation="https://martinfowler.com/bliki/CQRS.html",
    ),
    PatternEntry(
        name="Event Sourcing",
        aliases=["event store", "event sourcing pattern", "event log"],
        when_to_use=(
            "audit trail required, temporal queries needed (what was the state at time T?), "
            "event-driven architecture, CQRS read model projection"
        ),
        when_not_to_use=(
            "simple state storage with no audit requirements; "
            "small team — adds event store, projection complexity, and schema evolution challenges"
        ),
        operational_cost=(
            "event store grows indefinitely and needs snapshotting; "
            "projections must be rebuilt on schema change; "
            "eventual consistency between events and projections"
        ),
        common_mistake=(
            "using Event Sourcing because it sounds modern on simple CRUD apps; "
            "the overhead of event store, projection rebuild, and schema evolution "
            "is only justified when temporal queries or audit trails are core requirements"
        ),
        citation="https://martinfowler.com/eaaDev/EventSourcing.html",
    ),
    PatternEntry(
        name="Saga",
        aliases=["saga pattern", "distributed saga", "choreography saga", "orchestration saga", "2pc alternative", "two-phase commit alternative", "distributed transaction coordinator", "saga vs 2pc"],
        when_to_use=(
            "distributed transactions spanning multiple services where two-phase commit "
            "is not viable; long-running business processes; microservices data consistency"
        ),
        when_not_to_use=(
            "single service with a single database — use a plain DB transaction; "
            "strong consistency required across services (Saga gives eventual consistency only)"
        ),
        operational_cost=(
            "compensating transactions for each step to handle rollback; "
            "choreography adds event coupling between services; "
            "orchestration adds a coordinator that is a potential SPOF"
        ),
        common_mistake=(
            "using two-phase commit (2PC) instead of Saga for distributed transactions at scale — "
            "2PC is a blocking protocol that becomes unavailable if the coordinator fails, "
            "causing all participants to block indefinitely waiting for a resolution"
        ),
        citation="https://microservices.io/patterns/data/saga.html",
    ),
    PatternEntry(
        name="Outbox Pattern",
        aliases=["transactional outbox", "outbox", "inbox outbox pattern", "distributed transaction event", "reliable event publishing", "microservices messaging"],
        when_to_use=(
            "reliable event publishing alongside a database write; "
            "prevents dual-write failure: writing to DB and publishing to a queue "
            "separately can fail halfway, leaving them out of sync"
        ),
        when_not_to_use=(
            "single service with no downstream event bus; "
            "synchronous request-response only, no async event consumers"
        ),
        operational_cost=(
            "outbox table in the database; "
            "CDC (Change Data Capture) process or polling relay to forward events; "
            "additional infrastructure and monitoring"
        ),
        common_mistake=(
            "dual write without the Outbox Pattern — writing to the database "
            "and then publishing to a queue without a transaction boundary; "
            "if the publish step fails after a successful DB write, the event is silently lost"
        ),
        citation="https://microservices.io/patterns/data/transactional-outbox.html",
    ),
    PatternEntry(
        name="Circuit Breaker",
        aliases=["circuit breaker pattern", "resilience4j", "hystrix", "breaker"],
        when_to_use=(
            "calls to unreliable downstream services; "
            "prevent cascade failures when a dependency is slow or temporarily unavailable"
        ),
        when_not_to_use=(
            "internal in-process method calls; "
            "dependencies that are always reliable and fast; "
            "adds state machine complexity for no benefit"
        ),
        operational_cost=(
            "state machine per dependency (closed/open/half-open); "
            "threshold and timeout tuning; "
            "monitoring the open state; fallback logic required for every breaker"
        ),
        common_mistake=(
            "adding Circuit Breakers without first setting timeouts — "
            "a slow dependency with no timeout still blocks the caller thread pool "
            "even with a breaker in place; set timeouts first, then layer the breaker on top"
        ),
        citation="https://martinfowler.com/bliki/CircuitBreaker.html",
    ),
    PatternEntry(
        name="Bulkhead",
        aliases=["bulkhead pattern", "bulkhead isolation", "thread pool isolation", "resource isolation", "failure isolation", "service decoupling", "resilience pattern"],
        when_to_use=(
            "isolate resource pools (thread pools, connection pools) per tenant or "
            "downstream service to prevent one failing consumer from exhausting shared resources"
        ),
        when_not_to_use=(
            "single tenant or single downstream dependency; "
            "resource partitioning adds overhead and wastes capacity for simple deployments"
        ),
        operational_cost=(
            "separate thread pools or connection pools per consumer; "
            "total resource usage increases vs a shared pool; "
            "monitoring and tuning per pool"
        ),
        common_mistake=(
            "sharing a single thread pool or connection pool across all downstream calls — "
            "one slow or failing dependency saturates the shared pool and blocks "
            "all other calls, causing cascade failures across unrelated services"
        ),
        citation="https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead",
    ),
    PatternEntry(
        name="Strangler Fig",
        aliases=["strangler fig pattern", "strangler pattern", "incremental migration", "legacy migration", "monolith to microservices", "monolith decomposition", "legacy modernization"],
        when_to_use=(
            "incrementally migrate a legacy monolith to a new architecture without "
            "a big-bang rewrite; routes traffic to new and old systems simultaneously"
        ),
        when_not_to_use=(
            "greenfield project with no legacy system; "
            "small system where a direct cutover is fast and low risk"
        ),
        operational_cost=(
            "proxy or facade layer routes traffic between old and new; "
            "dual system operation during migration — two systems to maintain and monitor; "
            "traffic splitting and rollback complexity"
        ),
        common_mistake=(
            "attempting a big-bang rewrite of a legacy system instead of incremental replacement — "
            "big-bang rewrites have higher risk, longer timelines, and are harder to validate "
            "because nothing is live until the full rewrite ships"
        ),
        citation="https://martinfowler.com/bliki/StranglerFigApplication.html",
    ),
    PatternEntry(
        name="API Gateway",
        aliases=["api gateway pattern", "backend for frontend", "bff pattern", "gateway"],
        when_to_use=(
            "multiple client types needing different data shapes (mobile vs web), "
            "cross-cutting concerns (auth, rate limiting, logging) in one place, "
            "microservices fan-out aggregation"
        ),
        when_not_to_use=(
            "single client type or simple monolith API; "
            "small team — gateway becomes a bottleneck and a single point of failure"
        ),
        operational_cost=(
            "single point of failure if not made redundant; "
            "added network hop for every request; "
            "must actively prevent business logic creep into the gateway"
        ),
        common_mistake=(
            "putting business logic in the API Gateway — it should only handle routing, "
            "auth, and protocol translation; logic in the gateway creates a distributed monolith "
            "that is harder to test and deploy than the services it was meant to decouple"
        ),
        citation="https://microservices.io/patterns/apigateway.html",
    ),
    PatternEntry(
        name="Sidecar",
        aliases=["sidecar pattern", "sidecar proxy", "envoy sidecar", "service mesh sidecar"],
        when_to_use=(
            "cross-cutting concerns (mTLS, logging, tracing, retries) in a polyglot "
            "microservices environment where each service cannot implement them independently"
        ),
        when_not_to_use=(
            "simple homogeneous services where a shared library is sufficient; "
            "sidecar adds an extra process per pod and significant operational overhead"
        ),
        operational_cost=(
            "extra process per pod (resource overhead); "
            "service mesh control plane required for configuration; "
            "debugging is split across the main process and sidecar logs"
        ),
        common_mistake=(
            "putting service-specific business logic in the sidecar — "
            "it should only handle infrastructure concerns (proxy, observability); "
            "domain logic in the sidecar creates a hidden dependency that is "
            "invisible to service owners and breaks the separation of concerns"
        ),
        citation="https://learn.microsoft.com/en-us/azure/architecture/patterns/sidecar",
    ),
    PatternEntry(
        name="Rate Limiter",
        aliases=["rate limiting", "token bucket", "sliding window", "leaky bucket", "rate limit"],
        when_to_use=(
            "protect API from abuse, enforce fair usage per tenant, "
            "prevent cascade failures from traffic spikes; always at public API boundaries"
        ),
        when_not_to_use=(
            "trusted internal service-to-service calls where rate limiting adds "
            "latency with no protection benefit"
        ),
        operational_cost=(
            "shared state required for distributed rate limiting (typically Redis); "
            "algorithm choice matters — token bucket vs sliding window log vs fixed window; "
            "per-key storage grows with unique caller count"
        ),
        common_mistake=(
            "per-server rate limits without shared state — "
            "each server independently allows N requests, "
            "so with K servers a caller gets K*N requests before being blocked; "
            "always use shared state (Redis) for distributed rate limiting"
        ),
        citation="https://stripe.com/blog/rate-limiters",
    ),
]
