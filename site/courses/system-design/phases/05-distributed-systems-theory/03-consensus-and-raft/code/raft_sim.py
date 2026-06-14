# Run: python raft_sim.py
# Simplified Raft: leader election + majority-commit log replication (single process).
import random

random.seed(7)


class Node:
    def __init__(self, node_id):
        self.id = node_id
        self.term = 0
        self.state = "follower"
        self.voted_for = None
        self.log = []          # list of (term, command)
        self.alive = True


class Cluster:
    def __init__(self, n):
        self.nodes = [Node(i) for i in range(n)]

    def majority(self):
        return len(self.nodes) // 2 + 1

    def elect(self, candidate_id):
        cand = self.nodes[candidate_id]
        if not cand.alive:
            return None
        cand.term += 1
        cand.state = "candidate"
        cand.voted_for = cand.id
        votes = 1                          # votes for itself
        for node in self.nodes:
            if node.id == cand.id or not node.alive:
                continue
            if cand.term > node.term:      # grant vote if candidate's term is newer
                node.term = cand.term
                node.voted_for = cand.id
                node.state = "follower"
                votes += 1
        if votes >= self.majority():
            cand.state = "leader"
            for node in self.nodes:
                if node.id != cand.id and node.alive:
                    node.state = "follower"
            return cand
        cand.state = "follower"
        return None

    def replicate(self, leader, command):
        if leader.state != "leader":
            return False, 0
        entry = (leader.term, command)
        leader.log.append(entry)
        acks = 1                           # leader stores it
        for node in self.nodes:
            if node.id == leader.id or not node.alive:
                continue
            node.log.append(entry)         # follower stores it
            acks += 1
        committed = acks >= self.majority()
        return committed, acks


cluster = Cluster(5)
print(f"5-node cluster, majority = {cluster.majority()}")

leader = cluster.elect(0)
print(f"Election: node {leader.id} became LEADER (term {leader.term})")

committed, acks = cluster.replicate(leader, "x=5")
print(f"Replicate 'x=5': acks={acks}/5 -> committed={committed}")

# Kill 2 of 5 (a minority) -> still have majority -> still works
cluster.nodes[3].alive = False
cluster.nodes[4].alive = False
committed, acks = cluster.replicate(leader, "y=9")
print(f"\n2 nodes down (minority): acks={acks}/5 -> committed={committed}")

# Kill one more (now 3 of 5 down = majority gone) -> cannot commit
cluster.nodes[2].alive = False
committed, acks = cluster.replicate(leader, "z=1")
print(f"3 nodes down (no majority): acks={acks}/5 -> committed={committed}")
print("Consensus needs a MAJORITY: 5 nodes tolerate 2 failures, not 3.")
