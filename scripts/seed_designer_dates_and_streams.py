"""One-off data seed: designer joining dates, Mold Design stream, extra streams."""

from __future__ import annotations

from datetime import date
from difflib import SequenceMatcher

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.models import Stream, User

# DD-MM-YYYY from the provided roster.
DESIGNER_DATES: list[dict[str, object]] = [
    {"name": "Anurag Mohanan", "joining": date(2021, 9, 1), "first_job": date(2013, 3, 11)},
    {"name": "Binil JR", "joining": date(2024, 9, 17), "first_job": date(2015, 6, 1)},
    {"name": "Sarath Babu K", "joining": date(2024, 11, 4), "first_job": date(2019, 6, 1)},
    {"name": "Ranjith Karayappath", "joining": date(2023, 4, 17), "first_job": date(2003, 8, 1)},
    {"name": "Logesh", "joining": date(2023, 6, 19), "first_job": date(2020, 3, 1)},
    {"name": "Umesh Patil", "joining": date(2021, 8, 23), "first_job": date(2013, 7, 8)},
    {"name": "Abhay CK", "joining": date(2026, 3, 16), "first_job": date(2024, 12, 1)},
    {"name": "Akhil VB", "joining": date(2026, 3, 2), "first_job": date(2022, 7, 1)},
    {"name": "Sandrarag CM", "joining": date(2026, 3, 9), "first_job": date(2020, 7, 1)},
]

EXTRA_STREAMS = [
    "Mold Design",
    "Fixture Design",
    "Electrode Design",
    "Product Design",
    "Die Casting Design",
    "CAM Programming",
    "BIW Design",
    "Plastic Design",
    "Checking / QC",
]


def _norm(value: str) -> str:
    return " ".join(value.lower().replace(".", " ").split())


def _tokens(value: str) -> set[str]:
    return {token for token in _norm(value).split() if token}


def score_match(roster_name: str, user: User) -> float:
    full = f"{user.first_name} {user.last_name}".strip()
    roster_n = _norm(roster_name)
    full_n = _norm(full)
    first_n = _norm(user.first_name or "")
    last_n = _norm(user.last_name or "")

    if roster_n == full_n:
        return 1.0
    if roster_n == first_n or roster_n == last_n:
        return 0.95

    roster_tokens = _tokens(roster_name)
    user_tokens = _tokens(full)
    if roster_tokens and roster_tokens.issubset(user_tokens):
        return 0.92
    if user_tokens and user_tokens.issubset(roster_tokens):
        return 0.9
    # First-name exact + last initial / partial last
    if first_n and first_n in roster_tokens:
        for token in roster_tokens - {first_n}:
            if last_n.startswith(token) or token.startswith(last_n) or token in last_n:
                return 0.88
        if len(roster_tokens) == 1:
            return 0.85

    ratio = SequenceMatcher(None, roster_n, full_n).ratio()
    # Soft bonus when first name matches anywhere
    if first_n and first_n in roster_n:
        ratio = max(ratio, 0.75)
    return ratio


def ensure_streams(db) -> dict[str, Stream]:
    by_name: dict[str, Stream] = {}
    existing = db.scalars(select(Stream)).all()
    for stream in existing:
        by_name[stream.name.strip().lower()] = stream

    for name in EXTRA_STREAMS:
        key = name.strip().lower()
        if key in by_name:
            stream = by_name[key]
            if not stream.is_active:
                stream.is_active = True
            continue
        # Fuzzy: treat "mold design" / "Mold Design Stream" as same
        matched = None
        for existing_key, stream in by_name.items():
            if name.lower() in existing_key or existing_key in name.lower():
                matched = stream
                break
        if matched is not None:
            by_name[key] = matched
            continue
        stream = Stream(name=name, description=f"{name} engineering stream", is_active=True)
        db.add(stream)
        db.flush()
        by_name[key] = stream
        print(f"  + stream created: {name}")
    return by_name


def match_user(roster_name: str, users: list[User], used_ids: set) -> tuple[User | None, float]:
    ranked: list[tuple[float, User]] = []
    for user in users:
        if user.id in used_ids:
            continue
        ranked.append((score_match(roster_name, user), user))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return None, 0.0
    best_score, best_user = ranked[0]
    if best_score < 0.72:
        return None, best_score
    return best_user, best_score


def main() -> None:
    db = SessionLocal()
    try:
        print("Ensuring streams…")
        streams = ensure_streams(db)
        mold = streams.get("mold design")
        if mold is None:
            raise RuntimeError("Mold Design stream missing after ensure_streams")

        users = db.scalars(
            select(User).where(User.is_deleted.is_(False), User.is_active.is_(True))
        ).all()
        print(f"Active users: {len(users)}")
        for user in users:
            print(f"  - {user.first_name} {user.last_name}")

        used: set = set()
        unmatched: list[str] = []
        print("\nApplying designer dates + Mold Design stream…")
        for row in DESIGNER_DATES:
            name = str(row["name"])
            user, score = match_user(name, users, used)
            if user is None:
                unmatched.append(f"{name} (best score {score:.2f})")
                print(f"  ! no match for {name} (best={score:.2f})")
                continue
            used.add(user.id)
            user.joining_date = row["joining"]  # type: ignore[assignment]
            user.first_job_date = row["first_job"]  # type: ignore[assignment]
            user.stream_id = mold.id
            if not user.primary_tool:
                user.primary_tool = "NX Local"
            if not user.work_function:
                user.work_function = "Design/Surfacing"
            print(
                f"  OK {name} -> {user.first_name} {user.last_name} "
                f"(score={score:.2f}) join={user.joining_date} first={user.first_job_date}"
            )

        db.commit()
        print("\nStreams now:")
        for stream in db.scalars(select(Stream).order_by(Stream.name)).all():
            count = db.scalar(
                select(func.count()).select_from(User).where(User.stream_id == stream.id)
            )
            print(f"  - {stream.name} ({count} users)")

        if unmatched:
            print("\nUnmatched roster rows:")
            for item in unmatched:
                print(f"  - {item}")
        else:
            print("\nAll roster rows matched.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
