"""Move 100% of traffic to a named earlier revision.

python -m deploy.rollback --to <revision>

--to is required: the target is always chosen by name, never guessed. A revision the
gate refused is Ready (its probes passed) and could look like a good candidate.

Exit codes: 0 rolled back and ready, 1 refused (not found, not Ready), 2 traffic moved
but readiness on the service URL did not return 200. Running without --to exits 2 from
the argument parser before any gcloud call.
"""
import argparse
import sys

import httpx

from . import config
from .gcloud import Gcloud, fmt_traffic

EXIT_OK, EXIT_REFUSED, EXIT_NOT_READY = 0, 1, 2


def check_target(revisions, to):
    """Return an error string, or None when `to` exists and is Ready."""
    rev = next((r for r in revisions if r.name == to), None)
    if rev is None:
        return f"revision {to} does not exist"
    if not rev.ready:
        return f"revision {to} is not Ready, refusing"
    return None


def default_ready_check(url, token):
    r = httpx.get(url.rstrip("/") + config.READY_PATH, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    return r.status_code


def run(gc, to, out=print, ready_check=default_ready_check):
    svc = gc.get_service()
    if svc is None:
        out("RESULT outcome=refused reason=no-service")
        return EXIT_REFUSED
    out(f"traffic now: {fmt_traffic(svc.targets)}")
    error = check_target(gc.list_revisions(), to)
    if error:
        out(f"refused: {error}")
        out(f"RESULT outcome=refused target={to} traffic=[{fmt_traffic(svc.targets)}]")
        return EXIT_REFUSED
    gc.set_traffic({to: 100})
    svc = gc.get_service()
    out(f"traffic after: {fmt_traffic(svc.targets)}")
    status = ready_check(svc.url, gc.identity_token())
    out(f"readiness on {svc.url}: HTTP {status}")
    ok = status == 200
    out(f"RESULT outcome={'rolled-back' if ok else 'rolled-back-not-ready'} target={to} traffic=[{fmt_traffic(svc.targets)}]")
    return EXIT_OK if ok else EXIT_NOT_READY


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--to", required=True, help="revision name to receive 100%% of traffic")
    args = ap.parse_args(argv)
    return run(Gcloud(), args.to)


if __name__ == "__main__":
    sys.exit(main())
