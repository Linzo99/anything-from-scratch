# Run: python message_queue.py
# A thread-based producer/consumer queue with a worker pool absorbing a burst.
import queue
import threading
import time

work_queue = queue.Queue()
processed = []
processed_lock = threading.Lock()


def slow_task(job):
    time.sleep(0.01)               # simulate slow work (e.g. send email)
    with processed_lock:
        processed.append(job)


def worker(worker_id):
    while True:
        job = work_queue.get()     # blocks until a job is available
        if job is None:            # sentinel to stop
            work_queue.task_done()
            break
        slow_task(job)
        work_queue.task_done()     # acknowledge completion


def producer(n):
    start = time.time()
    for i in range(n):
        work_queue.put(f"job-{i}")  # enqueue and move on immediately
    return time.time() - start


NUM_JOBS = 1000
NUM_WORKERS = 8

threads = [threading.Thread(target=worker, args=(i,), daemon=True)
           for i in range(NUM_WORKERS)]
for t in threads:
    t.start()

enqueue_time = producer(NUM_JOBS)
print(f"Enqueued {NUM_JOBS} jobs in {enqueue_time*1000:.1f} ms "
      f"(producer returns immediately)")

process_start = time.time()
work_queue.join()                  # blocks until every task_done()
process_time = time.time() - process_start
print(f"Drained {NUM_JOBS} jobs with {NUM_WORKERS} workers in {process_time:.2f} s")
print(f"Processed count: {len(processed)}")
print(f"\nThroughput: ~{NUM_JOBS/process_time:.0f} jobs/sec with {NUM_WORKERS} workers")
print("Producer latency stayed ~0; the slow work moved off the request path.")

for _ in range(NUM_WORKERS):
    work_queue.put(None)
