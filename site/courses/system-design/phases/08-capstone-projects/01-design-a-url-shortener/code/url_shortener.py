# Run: python url_shortener.py
# A URL shortener core: base62 encoding + cache-aside read path.

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)   # 62


def encode(num):
    if num == 0:
        return ALPHABET[0]
    s = []
    while num > 0:
        num, rem = divmod(num, BASE)
        s.append(ALPHABET[rem])
    return "".join(reversed(s))


def decode(code):
    num = 0
    for ch in code:
        num = num * BASE + ALPHABET.index(ch)
    return num


class URLShortener:
    def __init__(self):
        self.db = {}                 # short_code -> long_url  (the "database")
        self.cache = {}              # short_code -> long_url  (the "Redis cache")
        self.counter = 1000          # unique ID source (Snowflake in production)
        self.db_hits = 0
        self.cache_hits = 0

    def shorten(self, long_url):
        code = encode(self.counter)  # base62 of a guaranteed-unique ID
        self.counter += 1
        self.db[code] = long_url
        return code

    def resolve(self, code):
        if code in self.cache:       # read path: cache first
            self.cache_hits += 1
            return self.cache[code]
        url = self.db.get(code)      # cache miss -> DB replica
        if url:
            self.db_hits += 1
            self.cache[code] = url   # populate cache (cache-aside)
        return url


print("Base62 encoding of IDs:")
for n in (0, 61, 62, 125, 999999, 3_521_614_606_207):   # last = 62^7 - 1
    print(f"  {n:>15} -> '{encode(n)}'  (decode -> {decode(encode(n))})")

s = URLShortener()
codes = {}
for url in ["https://example.com/a", "https://example.com/b", "https://python.org"]:
    code = s.shorten(url)
    codes[code] = url
    print(f"\nshorten {url} -> sho.rt/{code}")

print("\nResolving (first time = DB miss, then cached):")
for code in codes:
    print(f"  {code} -> {s.resolve(code)}   [1st: DB]")
for code in codes:                       # second round: all cache hits
    s.resolve(code)

# Read-heavy traffic: each link resolved many times
for _ in range(100):
    for code in codes:
        s.resolve(code)

total = s.db_hits + s.cache_hits
print(f"\nAfter read-heavy traffic:")
print(f"  DB hits:    {s.db_hits}")
print(f"  cache hits: {s.cache_hits}")
print(f"  cache hit ratio: {100*s.cache_hits/total:.1f}%  <- DB shielded from reads")
