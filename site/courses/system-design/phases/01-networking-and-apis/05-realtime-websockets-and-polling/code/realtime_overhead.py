# Run: python realtime_overhead.py
# Compare request count, overhead, and latency of four realtime techniques.

WINDOW_SECONDS = 60          # observation window
EVENTS = 4                   # actual updates the user should receive in the window
HEADER_BYTES = 700           # approx HTTP header overhead per request
WS_FRAME_BYTES = 4           # per-message framing once a WebSocket is open


def short_polling(interval=5):
    requests = WINDOW_SECONDS // interval     # one request every `interval` seconds
    overhead = requests * HEADER_BYTES
    worst_latency = interval                   # up to a full interval late
    return requests, overhead, worst_latency


def long_polling():
    requests = EVENTS + 1                       # one held request per event + one waiting
    overhead = requests * HEADER_BYTES
    worst_latency = 0                           # responds the instant an event occurs
    return requests, overhead, worst_latency


def sse():
    requests = 1                                # one long-lived connection
    overhead = HEADER_BYTES + EVENTS * 0        # events stream in the body, no new headers
    worst_latency = 0
    return requests, overhead, worst_latency


def websockets():
    requests = 1                                # one upgrade handshake
    overhead = HEADER_BYTES + EVENTS * WS_FRAME_BYTES
    worst_latency = 0
    return requests, overhead, worst_latency


rows = [
    ("Short polling (5s)", *short_polling(5)),
    ("Long polling",       *long_polling()),
    ("SSE",                *sse()),
    ("WebSockets",         *websockets()),
]

print(f"Window: {WINDOW_SECONDS}s, {EVENTS} real updates to deliver\n")
print(f"{'Technique':20} {'Requests':>9} {'Overhead(B)':>12} {'WorstLatency(s)':>16}")
for name, reqs, ovh, lat in rows:
    print(f"{name:20} {reqs:>9} {ovh:>12} {lat:>16}")
print("\nFewer requests + lower overhead + lower latency = better, but persistent")
print("connections (SSE/WS) cost an open socket per client at scale.")
