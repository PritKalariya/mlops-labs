"""Champion/challenger gate: a retrained model replaces the champion only if
it scores higher on the fixed held-out set. A tie keeps the champion; a
regression fails the job."""
import argparse
import json
import os
from pathlib import Path

CHAMPION = Path("champion.json")


def decide(challenger_f1, champion_f1):
    if champion_f1 is None or challenger_f1 > champion_f1:
        return "promote"
    if challenger_f1 == champion_f1:
        return "keep"
    return "block"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", type=str, required=True)
    timestamp = parser.parse_args().timestamp

    challenger = json.loads(Path(f"{timestamp}_metrics.json").read_text())["F1_Score"]
    champion = json.loads(CHAMPION.read_text())["F1_Score"] if CHAMPION.exists() else None

    decision = decide(challenger, champion)
    print(f"challenger {challenger:.4f} vs champion {champion}: {decision}")

    if decision == "promote":
        record = {"F1_Score": challenger, "timestamp": timestamp,
                  "run_id": os.environ.get("GITHUB_RUN_ID", "local")}
        CHAMPION.write_text(json.dumps(record, indent=4) + "\n")

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write(f"decision={decision}\n")

    if decision == "block":
        raise SystemExit("Challenger scored below the champion: not promoting.")
