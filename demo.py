import json
import time
from agents import ask_codex, ask_gemini

SYSTEM = (
    "You are Vera, the safecracker on the heist crew, speaking to the player "
    "(the lookout) through an earpiece. Reply in <=2 sentences, in-character. "
    "End every reply with a single line starting with 'INTENT:' describing "
    "what your character does next."
)

INITIAL_STATE = {
    "turn": 1,
    "location": "vault_antechamber",
    "alarm": False,
    "crew": {"safecracker": "ok", "lookout": "ok"},
    "loot_kg": 0,
    "guards_visible": 1,
}


def first_prompt(state: dict, situation: str) -> str:
    return (
        f"{SYSTEM}\n\n"
        f"<state>{json.dumps(state)}</state>\n\n"
        f"<situation>{situation}</situation>"
    )


def next_prompt(state: dict, situation: str) -> str:
    return (
        f"<state>{json.dumps(state)}</state>\n\n"
        f"<situation>{situation}</situation>"
    )


def run(label: str, ask):
    print(f"\n========== {label} ==========")
    state = dict(INITIAL_STATE)

    t0 = time.monotonic()
    t1 = ask(first_prompt(state, "You just cracked the outer door. Report what you see."))
    print(f"\nT1  session={t1.session_id[:8]}  ({time.monotonic() - t0:.1f}s)")
    print(t1.text)

    state.update(turn=2, guards_visible=2, alarm=True)

    t0 = time.monotonic()
    t2 = ask(
        next_prompt(state, "Alarm just tripped. Two guards now. What do you do?"),
        session_id=t1.session_id,
    )
    print(f"\nT2  session={t2.session_id[:8]}  ({time.monotonic() - t0:.1f}s)")
    print(t2.text)

    print(f"\nSame session across turns? {t1.session_id == t2.session_id}")


if __name__ == "__main__":
    run("codex", ask_codex)
    run("gemini", ask_gemini)
