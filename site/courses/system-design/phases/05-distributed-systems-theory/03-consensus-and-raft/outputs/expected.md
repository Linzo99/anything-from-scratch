# Expected Output

Running `python raft_sim.py` should produce:

```
5-node cluster, majority = 3
Election: node 0 became LEADER (term 1)
Replicate 'x=5': acks=5/5 -> committed=True

2 nodes down (minority): acks=3/5 -> committed=True
3 nodes down (no majority): acks=2/5 -> committed=False
Consensus needs a MAJORITY: 5 nodes tolerate 2 failures, not 3.
```

What to notice:
- **Election**: node 0 increments its term to 1, votes for itself, and collects a
  majority — it's the leader for term 1.
- **'x=5' commits with 5/5** acks: all nodes store it, well past the majority of 3.
- **'y=9' commits with 3/5** acks: two nodes are down, but 3 alive ≥ majority 3, so
  it still commits. A minority failure does not stop progress.
- **'z=1' fails with 2/5** acks: now three nodes are down, only 2 remain — below the
  majority of 3 — so it cannot commit. The system chooses safety (no commit) over
  availability. This is a CP system in CAP terms.

The takeaway: a 5-node cluster tolerates **2** failures (needs 3 for majority),
not 3. That's why clusters are sized odd.

Common issues:
- **'z=1' shows committed=True:** check `majority()` returns `len//2 + 1` (= 3 for
  5 nodes) and that dead nodes don't ack.
- **Different leader/term:** the seed is fixed, but the election logic is
  deterministic here (node 0 is elected), so output should match exactly.
