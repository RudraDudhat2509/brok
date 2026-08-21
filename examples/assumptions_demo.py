"""Worked example: the assumptions engine catching design claims that cannot hold.

Run with:  python examples/assumptions_demo.py
"""

from __future__ import annotations

from brok.assumptions import Channel, DataStore, ask, check_contradictions, explain


def banner(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def show_contradictions(entity) -> None:
    found = check_contradictions(entity)
    if not found:
        print("  no contradictions\n")
        return
    for c in found:
        certainty = "all facts declared" if c.all_declared else "rests on an inferred fact"
        print(f"  [{c.rule_id}] {c.explanation}")
        print(f"      confidence {c.confidence:.2f} ({certainty})")
        print(f"      cites: {c.citation}\n")


# 1. The headline case: all three legs of CAP claimed at once.
banner("1. CAP - claiming consistency, availability, and partition tolerance")
impossible = (
    DataStore(name="wishful_db")
    .declare("strong_consistency", True)
    .declare("available_under_partition", True)
    .declare("partition_tolerant", True)
)
show_contradictions(impossible)


# 2. The same theorem used forwards, deriving a fact nobody stated.
banner("2. CAP - deriving the third leg instead of flagging it")
cp_store = (
    DataStore(name="etcd")
    .declare("strong_consistency", True)
    .declare("partition_tolerant", True)
)
print(explain("available_under_partition", cp_store))
print("\n  No contrapositive was written for this. It falls out of the exclusion.\n")


# 3. Finding 1: quorum overlap buys fresh reads, never linearizability.
banner("3. Quorum - W=2 R=2 N=3, the 'strongly consistent quorum' claim")
cassandra = (
    DataStore(name="cassandra")
    .declare("replicated", True)
    .declare("sloppy_quorum", False)
    .with_quorum(n=3, w=2, r=2)
)
print(explain("read_sees_latest_acked_write", cassandra))
print()
print(explain("strong_consistency", cassandra))
print(
    "\n  Overlap gives fresh reads. It does NOT give linearizability - concurrent\n"
    "  writes stay unordered - so the engine answers UNKNOWN rather than agreeing\n"
    "  with the folk claim. This is the guarantee most write-ups get wrong.\n"
)


# 4. Arithmetic contradicting a stated claim, across domains.
banner("4. Quorum - W=1 R=1 N=3 while claiming strong consistency")
wishful = (
    DataStore(name="fast_and_correct")
    .declare("replicated", True)
    .declare("strong_consistency", True)
    .with_quorum(n=3, w=1, r=1)
)
show_contradictions(wishful)
print("  Chain: W+R=2 is not > N=3, so stale reads are possible [Q-D1 -> Q2],")
print("  while strong consistency entails fresh reads [Q3]. Those collide [Q4].\n")


# 5. PACELC: the trade-off that bites even with a healthy network.
banner("5. PACELC - replicated, linearizable, and low latency")
greedy = (
    DataStore(name="have_it_all")
    .declare("replicated", True)
    .declare("strong_consistency", True)
    .declare("low_latency_under_normal_operation", True)
)
show_contradictions(greedy)


# 6. Idempotency, and how provenance changes the report.
banner("6. Idempotency - exactly-once claimed over an at-least-once queue")
payments = (
    Channel(name="payments_queue")
    .declare("at_least_once_delivery", True)
    .declare("exactly_once_processing", True)
    .infer("idempotent_handler", False, confidence=0.6, evidence="api/charge.py:88")
    .infer("deduplication", False, confidence=0.9, evidence="no idempotency key column")
)
show_contradictions(payments)
print(
    "  Confidence 0.60, not 1.00: the chain runs through a 0.6 reading of\n"
    "  api/charge.py:88, and a conclusion is never more certain than its weakest\n"
    "  input. Compare case 1, where the same machinery reported 1.00 because every\n"
    "  supporting fact was stated outright. Same engine, different weight.\n"
)

# Drop the exactly-once claim and the contradiction goes away - but the duplicate
# charge it was hiding is still there, now stated plainly.
honest = (
    Channel(name="payments_queue")
    .declare("at_least_once_delivery", True)
    .infer("idempotent_handler", False, confidence=0.6, evidence="api/charge.py:88")
    .infer("deduplication", False, confidence=0.9, evidence="no idempotency key column")
)
print(explain("duplicate_side_effects_possible", honest))


# 7. Closed world: silence is not a denial.
banner("7. Closed world - what the engine refuses to say")
unknown_store = DataStore(name="undocumented_service")
print(explain("strong_consistency", unknown_store))
print(f"\n  ask() -> {ask('strong_consistency', unknown_store).truth.value}")
print(
    "\n  Not False. Nothing was declared, so nothing is claimed. Answering False here\n"
    "  would let a caller act on a guarantee that was never established.\n"
)
