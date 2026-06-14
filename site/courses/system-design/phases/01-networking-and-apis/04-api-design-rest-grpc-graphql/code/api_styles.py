# Run: python api_styles.py
# Compare REST, gRPC, and GraphQL payloads for the same screen.
import json

DB = {
    42: {
        "id": 42, "name": "Ada", "email": "ada@example.com",
        "bio": "Mathematician", "created": "1815-12-10", "followers": 9999,
        "posts": [
            {"id": 1, "title": "On the Analytical Engine", "body": "..." * 50},
            {"id": 2, "title": "Note G", "body": "..." * 50},
            {"id": 3, "title": "Poetical Science", "body": "..." * 50},
        ],
    }
}


# --- REST: fixed responses; over-fetch and under-fetch ---
def rest_get_user(uid):
    return DB[uid]                  # whole user object (over-fetch)


def rest_get_posts(uid):
    return DB[uid]["posts"]         # second round trip (under-fetch)


rest_payload = json.dumps(rest_get_user(42)) + json.dumps(rest_get_posts(42))


# --- gRPC: compact, fixed message (content approximated by declared fields) ---
def grpc_get_user(uid):
    u = DB[uid]
    return {"id": u["id"], "name": u["name"], "email": u["email"]}


grpc_payload = json.dumps(grpc_get_user(42))


# --- GraphQL: client requests exactly the fields it needs, one round trip ---
def graphql_query(uid, fields, last_posts=0):
    u = DB[uid]
    out = {f: u[f] for f in fields if f in u}
    if last_posts:
        out["posts"] = [{"title": p["title"]} for p in u["posts"][-last_posts:]]
    return out


graphql_payload = json.dumps(graphql_query(42, ["name"], last_posts=3))


print("=== Payload size to render 'name + last 3 post titles' ===")
print(f"REST (user + posts, 2 round trips): {len(rest_payload):5} bytes")
print(f"gRPC GetUser (1 call, fixed msg):   {len(grpc_payload):5} bytes")
print(f"GraphQL (1 call, exact shape):      {len(graphql_payload):5} bytes")
print()
print("REST over-fetches (bio, email, followers, full post bodies) AND")
print("under-fetches (needs a 2nd call for posts).")
print("GraphQL returns exactly the requested shape in one round trip.")
