# Run: python pubsub.py
# A topic-based pub/sub broker: one event fans out to many subscribers.
from collections import defaultdict


class Broker:
    def __init__(self):
        self.subscribers = defaultdict(list)   # topic -> [callbacks]

    def subscribe(self, topic, callback):
        self.subscribers[topic].append(callback)

    def publish(self, topic, event):
        for callback in self.subscribers[topic]:   # fan-out: copy to each
            callback(event)


delivered = {"email": [], "billing": [], "analytics": [], "inventory": []}


def email_service(event):
    delivered["email"].append(event)
    print(f"  [email]     welcome email for {event['user']}")


def billing_service(event):
    delivered["billing"].append(event)
    print(f"  [billing]   created billing profile for {event['user']}")


def analytics_service(event):
    delivered["analytics"].append(event)
    print(f"  [analytics] recorded event {event.get('type','?')}")


def inventory_service(event):
    delivered["inventory"].append(event)
    print(f"  [inventory] reserved stock for order {event.get('order')}")


broker = Broker()
broker.subscribe("user.signed_up", email_service)
broker.subscribe("user.signed_up", billing_service)
broker.subscribe("user.signed_up", analytics_service)
broker.subscribe("order.placed", inventory_service)
broker.subscribe("order.placed", analytics_service)

print("Publish user.signed_up (fans out to 3 services):")
broker.publish("user.signed_up", {"type": "user.signed_up", "user": "ada"})

print("\nPublish order.placed (fans out to 2 services):")
broker.publish("order.placed", {"type": "order.placed", "order": 1001})

print("\nDelivery counts:")
for svc, events in delivered.items():
    print(f"  {svc:10}: {len(events)} event(s)")
print("\nThe publisher never named a single subscriber — adding a new one")
print("means calling broker.subscribe(), with zero changes to the publisher.")

broker.subscribe("user.signed_up", lambda e: print("  [sales]     notified about", e["user"]))
print("\nAfter adding a 4th subscriber and publishing again:")
broker.publish("user.signed_up", {"type": "user.signed_up", "user": "grace"})
