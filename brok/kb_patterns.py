"""Architectural pattern knowledge base — 10 entries.

Every `common_mistake` field is mandatory and explicit: it names the specific
wrong thing models confidently recommend, which is the core anti-hallucination
mechanism for the query engine.

Fields are intentionally verbose. Short one-liners hurt both semantic retrieval
and the calling model's ability to reason correctly about when to apply a pattern.
Every entry has a `citation` field pointing to an authoritative source.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternEntry:
    name: str
    aliases: list[str]
    when_to_use: str
    when_not_to_use: str
    operational_cost: str
    common_mistake: str
    citation: str


PATTERN_KB: list[PatternEntry] = [
    PatternEntry(
        name="CQRS",
        aliases=["command query responsibility segregation", "read write split",
                 "separate read write models", "cqrs pattern"],
        when_to_use=(
            "Use CQRS when your read and write workloads have fundamentally different "
            "scaling, model, or consistency requirements that cannot be satisfied by a "
            "single unified model. The classic signal is when your write model enforces "
            "strict domain invariants (complex business rules, validation, aggregates) "
            "and your read model needs to serve denormalized, pre-joined views that are "
            "expensive to derive on the fly from normalized write-side data. CQRS is "
            "also the right choice when you need to scale reads and writes independently "
            "— for example, routing reads to Elasticsearch while writes go to PostgreSQL. "
            "It pairs naturally with Event Sourcing, because events on the write side "
            "can be projected into multiple read-optimized query models."
        ),
        when_not_to_use=(
            "Do not use CQRS for simple CRUD applications where the read and write "
            "models are identical — the overhead of maintaining separate models, "
            "synchronizing them, and managing eventual consistency between the write "
            "and read sides adds complexity that simple CRUD does not justify. CQRS "
            "is the wrong choice when your team is small and does not have the "
            "experience to manage the eventual consistency window between writes and "
            "reads — users who write and immediately read will sometimes see stale "
            "data, which is confusing in a simple CRUD app. Avoid CQRS as a default "
            "architecture for new systems; start simple and introduce it only when "
            "a clear scaling or modeling need emerges."
        ),
        operational_cost=(
            "CQRS doubles the data model surface area — you must maintain both a write "
            "model and one or more read models, and keep them in sync. The synchronization "
            "mechanism (event bus, change data capture, batch projection) is a new "
            "component to operate, monitor, and debug. Read model inconsistency windows "
            "(time between write and read model update) must be acceptable to the product "
            "and communicated to users. Testing complexity roughly doubles because both "
            "models and their synchronization must be tested independently and together."
        ),
        common_mistake=(
            "The most common mistake is applying CQRS to a simple CRUD application "
            "where there is no read/write asymmetry. Teams add CQRS because it sounds "
            "sophisticated, then spend months managing event projections and eventual "
            "consistency for a system that would have been simpler and faster with a "
            "single PostgreSQL table. The overhead of separate read and write models "
            "is only justified when the read and write sides have genuinely different "
            "requirements — scaling needs, model shape, consistency guarantees. "
            "Another common mistake is assuming CQRS means the read and write databases "
            "are always separate physical systems; CQRS is a logical separation of "
            "commands and queries, not an infrastructure requirement."
        ),
        citation="https://martinfowler.com/bliki/CQRS.html",
    ),
    PatternEntry(
        name="Event Sourcing",
        aliases=["event store", "event sourced", "append-only log", "event driven persistence",
                 "event log database"],
        when_to_use=(
            "Use Event Sourcing when the history of how an entity reached its current "
            "state is as important as the current state itself — financial ledgers, "
            "audit logs, order lifecycle tracking, and collaborative editing are "
            "canonical examples. Event Sourcing stores every state change as an "
            "immutable event and derives the current state by replaying events from "
            "the beginning. This gives you a complete audit trail, the ability to "
            "replay history to debug issues or backfill new read models, and a "
            "natural fit with CQRS where events are projected into query-optimized "
            "read models. It is also powerful for temporal queries — you can ask "
            "'what was the state of this account at 2:00 PM yesterday?'"
        ),
        when_not_to_use=(
            "Do not use Event Sourcing for simple CRUD applications where the current "
            "state is all that matters and no audit trail is needed — the overhead of "
            "storing every change, managing event versioning, and replaying events "
            "to rebuild state is complex and unnecessary. Avoid it when your team "
            "is not experienced with event-driven systems: event schema versioning "
            "(upcasting old events to new schemas) is a subtle, ongoing operational "
            "challenge. Event Sourcing is also wrong when queries need to aggregate "
            "across many entities simultaneously — replaying thousands of event streams "
            "to answer one query is slow; you need pre-built read model projections, "
            "which adds more infrastructure."
        ),
        operational_cost=(
            "Event stores grow forever — events are immutable and never deleted, so "
            "storage costs compound over time. Rebuilding the current state from a "
            "long event stream on cold start (or after a bug fix) requires snapshots "
            "at regular intervals plus replay from the last snapshot. Schema evolution "
            "(an event's shape changes because business rules changed) requires "
            "upcasters that transform old events to new formats at read time, which "
            "is complex to implement and test. Every read model projection is a "
            "separate consumer that must handle replay, ordering, and idempotency."
        ),
        common_mistake=(
            "The most common mistake is treating Event Sourcing as a simple audit log "
            "add-on that can be bolted onto an existing CRUD system. In reality, "
            "Event Sourcing is a fundamentally different persistence model that "
            "requires redesigning aggregates, commands, and queries from the ground "
            "up. Teams that treat it as optional or additive end up maintaining both "
            "a traditional database (for CRUD operations) and an event log (for audit), "
            "doubling the complexity without the coherence benefits. Another mistake "
            "is ignoring event schema versioning until it becomes a crisis: once "
            "events are stored, changing their structure requires upcasters, and "
            "skipping this planning causes silent data corruption during replay."
        ),
        citation="https://martinfowler.com/eaaDev/EventSourcing.html",
    ),
    PatternEntry(
        name="Saga",
        aliases=["saga pattern", "choreography saga", "orchestration saga",
                 "2pc alternative", "two-phase commit alternative",
                 "distributed transaction microservices", "long running transaction"],
        when_to_use=(
            "Use the Saga pattern when you need to coordinate a multi-step business "
            "transaction that spans multiple microservices, each with its own database, "
            "and you need to handle partial failures with compensating transactions. "
            "Sagas are the standard alternative to two-phase commit (2PC) in "
            "microservice architectures because 2PC requires a distributed coordinator "
            "that blocks resources across services, which reduces availability and "
            "creates a single point of failure. Use Sagas for order fulfillment (reserve "
            "inventory, charge payment, ship) where each step can be compensated "
            "(release inventory, refund payment) if a later step fails."
        ),
        when_not_to_use=(
            "Do not use Sagas as a general substitute for database transactions within "
            "a single service — ACID transactions within one database are simpler, "
            "faster, and provide stronger isolation. Avoid Sagas when your steps are "
            "not independently reversible — some operations cannot be compensated "
            "(you cannot un-send an email, un-launch a rocket, or un-publish a "
            "regulatory filing). The two-phase commit approach it replaces is blocking "
            "and reduces availability, but two-phase commit does provide stronger "
            "atomicity guarantees; Sagas are eventually consistent, which means "
            "intermediate states are observable. Do not use Sagas when your team "
            "does not have a clear compensation strategy for every step."
        ),
        operational_cost=(
            "Sagas require a state machine or orchestrator to track which steps have "
            "completed and which compensations have been triggered. This state machine "
            "is a new component that must be durable (it must survive restarts) and "
            "idempotent (compensation steps may be retried). Orchestration Sagas "
            "have a central orchestrator that adds a coordination bottleneck; "
            "Choreography Sagas distribute the coordination into event handlers, which "
            "are harder to reason about when the flow grows complex. Debugging a "
            "partially-completed Saga with partially-applied compensations is "
            "significantly harder than debugging a failed database transaction."
        ),
        common_mistake=(
            "The most common mistake is using Sagas as a drop-in replacement for "
            "two-phase commit without understanding the consistency difference. Two-phase "
            "commit is blocking but provides ACID atomicity; Sagas are non-blocking but "
            "provide ACD only (no isolation). Because Saga steps execute sequentially "
            "and commit independently, intermediate states are visible to other transactions "
            "— a saga that reserves inventory but has not yet charged payment leaves the "
            "inventory in a 'reserved but not paid' state that other services can read. "
            "Teams that expect Saga to give them the same isolation as 2PC are surprised "
            "by this. Another common mistake is designing Sagas without compensation "
            "transactions for every step — if step 3 of a 5-step saga fails, and step 2 "
            "has no compensation defined, the system is stuck in a permanently partial state."
        ),
        citation="https://microservices.io/patterns/data/saga.html",
    ),
    PatternEntry(
        name="Outbox Pattern",
        aliases=["transactional outbox", "outbox table", "transactional outbox pattern",
                 "distributed transaction event", "database event publishing",
                 "reliable event publishing", "distributed transaction",
                 "atomic event publish database"],
        when_to_use=(
            "Use the Outbox pattern when you need to atomically update a database "
            "record and publish a message to a queue or event bus — specifically when "
            "you cannot afford to publish the message without the database commit "
            "succeeding, or vice versa. Without the Outbox pattern, a failure between "
            "the database commit and the message publish creates a split-brain: either "
            "the database is updated but no event was published (downstream services "
            "miss the event) or the event is published but the database was never "
            "updated (downstream services act on a write that was rolled back). The "
            "Outbox pattern writes the event to an outbox table in the same transaction "
            "as the business record update, then a separate relay process reads the "
            "outbox and publishes to the message bus."
        ),
        when_not_to_use=(
            "Do not use the Outbox pattern when the event publication does not need to "
            "be atomic with the database write — if losing an event occasionally is "
            "acceptable (metrics, logging, non-critical notifications), the outbox adds "
            "unnecessary complexity. Avoid it when you are already using a system that "
            "provides built-in transactional messaging (for example, Kafka Streams with "
            "its exactly-once transactional producer) that handles the atomic "
            "write-plus-publish problem natively. The Outbox pattern is also overkill "
            "for simple systems where a single-service architecture means there is no "
            "cross-service event to publish."
        ),
        operational_cost=(
            "The Outbox pattern requires a relay process (sometimes called the Outbox "
            "Relay or CDC relay) that polls or listens for new outbox table rows and "
            "publishes them to the message bus. This relay must be durable, highly "
            "available, and handle at-least-once semantics (the consumer must be "
            "idempotent). The outbox table grows indefinitely unless processed rows "
            "are deleted, which requires a cleanup job. Change Data Capture (Debezium "
            "reading PostgreSQL WAL) is a more efficient relay implementation than "
            "polling but adds operational complexity."
        ),
        common_mistake=(
            "The most common mistake is the dual-write anti-pattern: publishing the "
            "event directly after a database commit in application code without a "
            "transactional guarantee (db.commit(); bus.publish(event)). This looks "
            "correct 99.9% of the time but fails when the process crashes between "
            "the commit and the publish, leaving the database updated but the event "
            "permanently lost. Teams discover this in production during a deploy or "
            "crash and cannot explain why downstream services missed an event. The "
            "Outbox pattern solves this by making the event write part of the same "
            "database transaction as the business record write — either both succeed "
            "or both roll back, eliminating the dual-write inconsistency entirely."
        ),
        citation="https://microservices.io/patterns/data/transactional-outbox.html",
    ),
    PatternEntry(
        name="Circuit Breaker",
        aliases=["circuit breaker pattern", "fault tolerance", "automatic retry",
                 "service degradation", "hystrix"],
        when_to_use=(
            "Use the Circuit Breaker pattern when your service makes synchronous calls "
            "to a downstream dependency that can fail or become slow — external APIs, "
            "databases, downstream microservices. Without a circuit breaker, a slow "
            "downstream dependency causes all your threads to block waiting for "
            "responses, eventually exhausting your connection pool and crashing your "
            "service even though the problem started elsewhere. The circuit breaker "
            "tracks failure rates and automatically stops sending requests to a "
            "failing dependency for a configured period, immediately returning a "
            "fallback response. This prevents cascading failures from propagating "
            "through your service graph."
        ),
        when_not_to_use=(
            "Do not apply circuit breakers to every single internal method call — "
            "they are designed for network calls to external dependencies where the "
            "latency and failure characteristics are unpredictable. Applying circuit "
            "breakers to in-process calls adds overhead and complexity without benefit. "
            "Avoid circuit breakers for idempotent operations that should always be "
            "retried (simple reads with no side effects) — for those, a simple retry "
            "with exponential backoff is sufficient. Also avoid circuit breakers when "
            "the downstream dependency is a database you control — database outages "
            "should trigger alerting and failover, not circuit-breaking with fallback "
            "responses."
        ),
        operational_cost=(
            "Circuit breakers need configuration tuning: failure threshold (how many "
            "failures before opening), timeout (how long to stay open), and half-open "
            "probe behavior (how many requests to let through to test recovery). "
            "Getting these parameters wrong causes false-positive circuit trips "
            "(opening on transient errors) or false-negative stays (staying closed "
            "during a real outage). Fallback responses must be designed carefully — "
            "a fallback that silently returns empty data can be worse than a visible "
            "error if users do not realize they are seeing degraded results."
        ),
        common_mistake=(
            "The most common mistake is not setting a timeout on the downstream call — "
            "without a timeout, a hung connection never triggers the circuit breaker "
            "because no error is thrown, and the thread pool exhausts silently. Every "
            "circuit-broken call must have an explicit timeout set. The second common "
            "mistake is configuring the circuit breaker to retry indefinitely with no "
            "backoff before tripping, which floods the already-struggling downstream "
            "service with retries and makes the outage worse. A circuit breaker must be "
            "combined with exponential backoff and jitter. Also, forgetting to instrument "
            "circuit breaker state transitions means an open circuit serves degraded "
            "responses silently for minutes — state (closed, open, half-open) and trip "
            "events must be exposed as metrics and trigger alerts."
        ),
        citation="https://martinfowler.com/bliki/CircuitBreaker.html",
    ),
    PatternEntry(
        name="Bulkhead",
        aliases=["bulkhead pattern", "bulkhead isolation", "thread pool isolation",
                 "service isolation", "failure isolation", "resilience pattern",
                 "decoupled services resilience", "service decoupling fault tolerance"],
        when_to_use=(
            "Use the Bulkhead pattern when your service communicates with multiple "
            "downstream dependencies and you need to prevent a failure or slowdown "
            "in one dependency from exhausting all resources and affecting calls to "
            "other dependencies. The pattern partitions resources (thread pools, "
            "connection pools, semaphores) by dependency, so that a slow downstream "
            "service can only consume its own partition without starving others. "
            "The classic example: a service that calls both a payment provider and a "
            "product catalog uses separate thread pools for each — if the payment "
            "provider becomes slow, threads in its pool fill up but the product catalog "
            "pool is unaffected, and product browsing continues normally."
        ),
        when_not_to_use=(
            "Do not apply the Bulkhead pattern when you have a single downstream "
            "dependency — there is nothing to isolate from, and the pattern adds "
            "thread pool management overhead without benefit. Avoid it for very "
            "low-concurrency services where the total request volume is small and "
            "a single connection pool is sufficient — the added complexity of "
            "partitioned pools is not worth it at low scale. Bulkheads are also "
            "wrong for batch processing jobs where requests are sequential rather "
            "than concurrent, since thread pool isolation is meaningless when only "
            "one thread is active at a time."
        ),
        operational_cost=(
            "Bulkheads require sizing thread or connection pool partitions correctly, "
            "which requires understanding the expected concurrency for each dependency. "
            "Undersized pools reject requests prematurely; oversized pools waste "
            "resources. Monitoring must track pool saturation (queue depth, rejection "
            "rate) per partition, not just aggregate. Libraries like Resilience4J and "
            "Hystrix provide bulkhead implementations, but they add a framework "
            "dependency and require configuration management."
        ),
        common_mistake=(
            "The most common mistake is deploying a Bulkhead without monitoring the "
            "bulkhead pool metrics. An oversized bulkhead pool accepts all requests, "
            "including the burst that will eventually degrade the service — without "
            "metrics on pool utilization and rejection rate, you get no early warning. "
            "Another mistake is setting all bulkhead pool sizes identically rather "
            "than sizing them based on the expected concurrency per dependency — a "
            "dependency called 1,000 times per second needs a much larger pool than "
            "one called 10 times per second, and using the same size for both means "
            "either one is wasteful or the other is too small."
        ),
        citation="https://docs.microsoft.com/en-us/azure/architecture/patterns/bulkhead",
    ),
    PatternEntry(
        name="Strangler Fig",
        aliases=["strangler pattern", "strangler fig pattern", "incremental migration",
                 "monolith to microservices", "legacy migration pattern",
                 "phased migration"],
        when_to_use=(
            "Use the Strangler Fig pattern when migrating a large monolith to a new "
            "architecture (microservices, new technology stack, new database) "
            "incrementally rather than as a big-bang rewrite. The pattern works by "
            "routing traffic through a facade (reverse proxy or API gateway) that "
            "directs requests to either the legacy system or the new replacement "
            "depending on whether a feature has been migrated. As individual features "
            "are migrated and proven in production, traffic shifts from the legacy "
            "system to the new system. When all traffic routes to the new system, "
            "the legacy monolith is decommissioned. This is safer than a big-bang "
            "rewrite because the legacy system remains live as a fallback."
        ),
        when_not_to_use=(
            "Do not use the Strangler Fig pattern when the legacy system's internal "
            "data model is deeply coupled in a way that prevents incremental migration "
            "— if every feature shares the same database schema with tight coupling "
            "between tables, migrating one feature may require migrating the entire "
            "schema. Avoid it for small systems where a complete rewrite in a sprint "
            "is feasible — the strangler adds routing complexity, dual system "
            "maintenance, and data synchronization overhead that is overkill for a "
            "small migration. Also avoid when the business cannot tolerate the "
            "extended period of running both systems in parallel, as the dual-system "
            "phase can last months to years."
        ),
        operational_cost=(
            "Running two systems in parallel doubles the operational surface: both "
            "the legacy system and the new replacement must be deployed, monitored, "
            "and maintained. The routing facade is a new critical component that "
            "must be highly available and configurable. Data synchronization between "
            "the legacy and new databases during the transition period is the hardest "
            "part: bidirectional sync (writes to either system must reflect in both) "
            "is complex and error-prone. The migration timeline often extends longer "
            "than planned because 'the last 20%' of a monolith is always the most "
            "tangled."
        ),
        common_mistake=(
            "The most common mistake is using the Strangler Fig pattern as a justification "
            "to delay completing the migration — teams start the pattern, migrate 60-70% "
            "of traffic to the new service, then abandon it. The dual-system state "
            "becomes permanent because the next priority always seems more urgent than "
            "the final rewrite push. This is worse than a clean big-bang rewrite: you "
            "end up maintaining two systems indefinitely with no deadline forcing "
            "completion. The second common mistake is underestimating data migration "
            "complexity: teams focus on routing traffic (straightforward) but neglect "
            "bidirectional data sync for the period when both systems write to different "
            "databases, causing subtle inconsistencies."
        ),
        citation="https://martinfowler.com/bliki/StranglerFigApplication.html",
    ),
    PatternEntry(
        name="API Gateway",
        aliases=["api gateway pattern", "gateway aggregation", "backend for frontend",
                 "bff", "api proxy"],
        when_to_use=(
            "Use an API Gateway when your system has multiple client types (mobile, "
            "web, third-party) calling multiple backend microservices and you want a "
            "single entry point that handles cross-cutting concerns — authentication, "
            "rate limiting, request routing, protocol translation, and response "
            "aggregation. The API Gateway pattern reduces client-to-service coupling: "
            "clients call one gateway endpoint instead of knowing the addresses and "
            "protocols of every backend service. It also enables Backend for Frontend "
            "(BFF) where different gateways serve different client types with "
            "client-optimized API shapes — mobile clients often need fewer fields "
            "and different aggregations than desktop clients."
        ),
        when_not_to_use=(
            "Do not use an API Gateway for simple single-service applications where "
            "there is only one backend to route to — the gateway adds a network hop, "
            "configuration complexity, and a potential availability bottleneck without "
            "any of the benefits. Avoid a single API Gateway as the only entry point "
            "without horizontal scaling: a gateway that cannot scale becomes the "
            "bottleneck for the entire system. Also avoid using the API Gateway to "
            "implement business logic — it should be a dumb router and cross-cutting "
            "concern handler; business logic belongs in backend services."
        ),
        operational_cost=(
            "The API Gateway is a critical infrastructure component — if it goes down, "
            "all external traffic is blocked. It must be highly available, horizontally "
            "scalable, and monitored as carefully as any core service. Configuration "
            "management (routing rules, rate limit policies, auth configurations) grows "
            "with the number of services, and mistakes in gateway config can expose "
            "or break multiple services simultaneously. API gateways also add a "
            "network hop to every request, adding 1-5ms of latency that compounds "
            "when multiple services are called per request."
        ),
        common_mistake=(
            "The most common mistake is turning the API Gateway into a God Object by "
            "putting business logic, data transformation, or service orchestration into "
            "it. Once business logic lives in the gateway, it becomes impossible to "
            "test in isolation, difficult to version, and tightly coupled to every "
            "downstream service. The gateway should handle routing, auth, and rate "
            "limiting — nothing else. Another common mistake is deploying a single "
            "gateway instance without redundancy: any deploy, crash, or resource "
            "exhaustion on the gateway takes down all external access to the system."
        ),
        citation="https://microservices.io/patterns/apigateway.html",
    ),
    PatternEntry(
        name="Sidecar",
        aliases=["sidecar pattern", "sidecar proxy", "envoy sidecar", "service mesh sidecar",
                 "ambassador pattern"],
        when_to_use=(
            "Use the Sidecar pattern when you want to add cross-cutting infrastructure "
            "concerns (observability, security, traffic management, service discovery) "
            "to a service without modifying its code. A sidecar container runs alongside "
            "the main service container in the same pod, intercepting its network traffic "
            "and adding functionality transparently. Service meshes (Istio, Linkerd) use "
            "the Sidecar pattern to inject Envoy proxies that handle mTLS, distributed "
            "tracing, retries, and circuit breaking across all services without any "
            "application code changes. Use the Sidecar when standardizing infrastructure "
            "concerns across a polyglot microservice architecture where each service is "
            "in a different language."
        ),
        when_not_to_use=(
            "Do not use the Sidecar pattern for a simple single-service deployment — "
            "the operational complexity of managing sidecar lifecycles, versions, and "
            "configurations is only worthwhile when you have many services that "
            "benefit from uniform infrastructure treatment. Avoid using a service mesh "
            "sidecar for services with very strict latency requirements where the "
            "additional network hop through the sidecar proxy (typically 0.5-2ms) "
            "is unacceptable. Also avoid when your team does not have the operational "
            "maturity to manage a service mesh — Istio in particular is complex to "
            "configure, debug, and upgrade."
        ),
        operational_cost=(
            "Each sidecar container adds memory overhead (Envoy typically uses "
            "50-100MB per pod) and CPU overhead for traffic interception and "
            "telemetry. At cluster scale, this adds up: 1,000 pods with Envoy sidecars "
            "add 50-100GB of sidecar memory overhead. Sidecar versions must be managed "
            "and upgraded independently of the application containers. Debugging network "
            "issues through a sidecar proxy adds a layer of indirection — packet captures "
            "and proxy logs must be consulted alongside application logs."
        ),
        common_mistake=(
            "The most common mistake is adopting a full service mesh (Istio) for a "
            "small system because it provides the Sidecar pattern — the operational "
            "complexity of Istio (CRDs, control plane components, certificate management) "
            "is designed for large, polyglot microservice deployments and is massive "
            "overkill for fewer than 20 services. Teams spend more time fighting the "
            "service mesh than building features. For small systems, a lighter approach "
            "(manually injected logging agents, application-level observability libraries) "
            "achieves 90% of the benefit at 10% of the complexity."
        ),
        citation="https://docs.microsoft.com/en-us/azure/architecture/patterns/sidecar",
    ),
    PatternEntry(
        name="Rate Limiter",
        aliases=["rate limiting", "rate limit", "throttling", "token bucket", "leaky bucket",
                 "sliding window rate limit"],
        when_to_use=(
            "Use rate limiting when you need to protect a service or API from being "
            "overwhelmed by too many requests from a single client, tenant, or "
            "globally. Rate limiting is essential for any public API, multi-tenant "
            "SaaS platform, or service that calls a third-party API with usage quotas. "
            "The token bucket algorithm is the most common choice: each client gets "
            "a bucket that refills at a fixed rate, and requests consume tokens — "
            "when the bucket is empty, requests are rejected or queued. Rate limiting "
            "at the API Gateway level protects all downstream services from abuse; "
            "rate limiting at the service level protects individual services from "
            "internal overload."
        ),
        when_not_to_use=(
            "Do not apply rate limiting to internal service-to-service communication "
            "within your own infrastructure where you control both the caller and the "
            "callee — backpressure and circuit breakers are more appropriate for "
            "internal traffic management. Avoid rate limiting as the sole mechanism "
            "for capacity management when you actually need autoscaling: rate limiting "
            "rejects excess traffic, while autoscaling serves it. They solve different "
            "problems. Also avoid poorly tuned rate limits that are so tight they "
            "affect legitimate high-volume customers — over-aggressive rate limiting "
            "causes legitimate customer churn."
        ),
        operational_cost=(
            "Distributed rate limiting (enforcing a per-user limit across multiple "
            "service instances) requires a shared state store — typically Redis — "
            "to track the token bucket or sliding window counter. This adds a Redis "
            "read-write per request on the hot path. The shared state store must be "
            "highly available: if Redis goes down, you must decide whether to fail "
            "open (allow all traffic) or fail closed (reject all traffic). Rate limit "
            "configurations must be per-tenant and regularly reviewed as customer "
            "usage patterns change."
        ),
        common_mistake=(
            "The most common mistake is implementing rate limiting per-server "
            "instead of using shared state — if each instance tracks its own counter "
            "and the limit is 100 req/min per server with 10 servers, a single user "
            "can send 1,000 req/min by spreading requests across servers. Distributed "
            "rate limiting must track counts in a shared state store (Redis) so the "
            "limit is enforced globally. The limit seen by a single user is k*n where "
            "k is the per-server limit and n is the number of servers, which makes the "
            "protection meaningless at scale. Another mistake is returning a generic "
            "429 error without a Retry-After header — well-behaved clients need this "
            "to implement backoff, and omitting it causes uncoordinated retry storms."
        ),
        citation="https://www.cloudflare.com/learning/bots/what-is-rate-limiting/",
    ),
]
