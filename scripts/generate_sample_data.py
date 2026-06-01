"""
Sample data generator - writes a batch of synthetic events to a local
JSON file and drops it in the S3 raw bucket. Local dev only.

Usage:
    python scripts/generate_sample_data.py --rows 10000 --output ./sample/events.json
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

EVENT_TYPES = [
    ("click", 0.45, 0.0),
    ("view", 0.25, 0.0),
    ("scroll", 0.10, 0.0),
    ("purchase", 0.05, (5.0, 250.0)),
    ("refund", 0.01, (5.0, 250.0)),
    ("subscribe", 0.04, (9.99, 99.99)),
    ("unsubscribe", 0.02, 0.0),
    ("signup", 0.04, 0.0),
    ("login", 0.03, 0.0),
    ("logout", 0.01, 0.0),
]
USERS = [f"u{i:05d}" for i in range(1, 1001)]
SOURCES = ["ios", "android", "web", "kiosk", "api"]


def generate(n: int, days: int = 7) -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    for _ in range(n):
        chosen = random.choices(
            EVENT_TYPES,
            weights=[w for _, w, _ in EVENT_TYPES],
            k=1,
        )[0]
        et = chosen[0]
        prob = chosen[1]
        amount = chosen[2]

        amount = round(random.uniform(amount[0], amount[1]), 2) if isinstance(amount, tuple) and len(amount) == 2 and isinstance(amount[0], (int, float)) else 0.0
        ts = now - timedelta(
            days=random.randint(0, days - 1),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        out.append(
            {
                "event_id": str(uuid.uuid4()),
                "user_id": random.choice(USERS),
                "event_type": et,
                "amount": amount,
                "ingested_at": ts.isoformat(),
                "source": random.choice(SOURCES),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=10_000)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--output", type=str, default="./sample/events.json")
    args = ap.parse_args()

    data = generate(args.rows, args.days)

    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {len(data)} events → {args.output}")


if __name__ == "__main__":
    main()
