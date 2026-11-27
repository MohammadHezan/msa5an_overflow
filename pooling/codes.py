"""Ride codes the driver checks at the meeting point."""
import random
import secrets


def new_code(existing: set[str], rng: random.Random | None = None) -> str:
    """Return a code like 'CC-4821' that is not in `existing`."""
    draw = rng.randrange if rng else secrets.randbelow
    for _ in range(10_000):
        code = f"CC-{draw(10_000):04d}"
        if code not in existing:
            return code
    raise RuntimeError("No free ride codes left.")
