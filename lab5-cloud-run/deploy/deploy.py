"""Ship one revision: 0% behind a tag, gate it, canary 10%, promote to 100%.

python -m deploy.deploy --image <registry/forecast@sha256:...> --expect-version 1.1.0 [--env K=V ...]

Exit codes
  0  promoted (or first release live)
  1  first release failed, traffic was split at start, or bad arguments
  2  refused by Cloud Run (startup probe), traffic unchanged
  3  refused by the gate, tag removed, traffic unchanged
  4  canary failed, traffic restored to the previous revision
  5  unexpected error, traffic restored to its state at the start
"""
import argparse
import asyncio
import sys

from . import config, gate
from .gcloud import DeployFailed, Gcloud, GcloudError, fmt_traffic

EXIT_OK, EXIT_START, EXIT_REFUSED, EXIT_GATE, EXIT_CANARY, EXIT_ERROR = 0, 1, 2, 3, 4, 5


class Deployer:
    def __init__(self, gc, gate_fn, canary_fn, out=print, tag=config.CAND_TAG):
        self.gc, self.gate_fn, self.canary_fn, self.out, self.tag = gc, gate_fn, canary_fn, out, tag

    # -- helpers -----------------------------------------------------------------
    def _traffic_line(self, label):
        svc = self.gc.get_service()
        self.out(f"traffic {label}: {fmt_traffic(svc.targets) if svc else '(no service)'}")
        return svc

    def _remove_tag_if_present(self):
        svc = self.gc.get_service()
        if svc and svc.tagged(self.tag):
            self.gc.remove_tag(self.tag)

    def _summary(self, outcome, new, previous):
        svc = self.gc.get_service()
        traffic = fmt_traffic(svc.targets) if svc else "(no service)"
        self.out(f"RESULT outcome={outcome} new={new or '-'} previous={previous or '-'} traffic=[{traffic}]")

    def _restore(self, previous, new):
        """Put 100% back on `previous` and drop the tag. Best effort, never raises."""
        try:
            self.gc.set_traffic({previous: 100})
        except Exception as exc:  # noqa: BLE001 - restoring must not mask the original error
            self.out(f"WARNING: restoring traffic failed: {exc}")
        try:
            self._remove_tag_if_present()
        except Exception as exc:  # noqa: BLE001
            self.out(f"WARNING: removing tag failed: {exc}")

    # -- the release -------------------------------------------------------------
    def run(self, image, expect_version, env=None):
        svc = self.gc.get_service()
        if svc is None:
            return self._first_release(image, expect_version, env)

        serving = svc.serving()
        if len(serving) != 1 or serving[0].percent != 100:
            self.out(f"traffic is split or unclear, refusing to deploy: {fmt_traffic(svc.targets)}")
            self._summary("split-traffic", None, None)
            return EXIT_START
        previous = serving[0].revision
        self.out(f"previous revision (100%): {previous}")
        new = None
        try:
            try:
                self.gc.deploy(image, env=env, no_traffic=True, tag=self.tag)
            except DeployFailed as exc:
                self.out(f"refused by Cloud Run: {str(exc)[:400]}")
                self._traffic_line("after refusal (unchanged expected)")
                self._remove_tag_if_present()
                self._summary("refused-by-cloud-run", None, previous)
                return EXIT_REFUSED

            svc = self.gc.get_service()
            new = svc.latest_created
            cand = svc.tagged(self.tag)
            if cand is None or not cand.url:
                raise RuntimeError(f"tag {self.tag!r} missing after deploy")
            self.out(f"new revision {new} deployed at 0%, gating {cand.url}")

            result = self.gate_fn(cand.url, expect_version)
            self.out(result.report())
            if not result.ok:
                self._remove_tag_if_present()
                self._traffic_line("after gate failure (unchanged expected)")
                self._summary("refused-by-gate", new, previous)
                return EXIT_GATE

            self.gc.set_traffic({previous: 90, new: 10})
            self.out(f"canary: {previous}=90% {new}=10%, sending requests to {svc.url}")
            bad = self.canary_fn(svc.url)
            if bad:
                self.out(f"canary failed: {len(bad)} bad responses (first: {bad[0]})")
                self._restore(previous, new)
                self._traffic_line("after canary failure")
                self._summary("canary-failed", new, previous)
                return EXIT_CANARY
            self.out("canary passed")

            self.gc.set_traffic({new: 100})
            self._remove_tag_if_present()
            self._traffic_line("after promote")
            self._summary("promoted", new, previous)
            return EXIT_OK
        except Exception as exc:  # noqa: BLE001 - anything unexpected must leave traffic as it was
            self.out(f"unexpected error: {exc!r}")
            self._restore(previous, new)
            self._traffic_line("after restore")
            self._summary("error-restored", new, previous)
            return EXIT_ERROR

    def _first_release(self, image, expect_version, env):
        self.out("no service yet: first release, 100% traffic")
        try:
            self.gc.deploy(image, env=env)
        except GcloudError as exc:
            self.out(f"first release deploy failed: {str(exc)[:400]}")
            self._summary("first-release-failed", None, None)
            return EXIT_START
        svc = self.gc.get_service()
        new = svc.latest_created
        result = self.gate_fn(svc.url, expect_version)
        self.out(result.report())
        if not result.ok:
            self._summary("first-release-gate-failed", new, None)
            return EXIT_START
        # Pin the revision by name so later --no-traffic deploys cannot move traffic.
        self.gc.set_traffic({new: 100})
        self._summary("first-release", new, None)
        return EXIT_OK


def build_checks(gc, settings):
    cases = gate.load_golden()
    limit = config.gate_p95_ms(settings)
    n, conc = int(settings["GATE_REQUESTS"]), int(settings["GATE_CONCURRENCY"])
    canary_n = int(settings["CANARY_REQUESTS"])

    def gate_fn(url, expect_version):
        return gate.run_gate(url, gc.identity_token(), cases, expect_version, limit, n=n, concurrency=conc)

    def canary_fn(url):
        return asyncio.run(gate.run_requests(url, gc.identity_token(), canary_n, concurrency=conc))

    return gate_fn, canary_fn


def parse_env(pairs):
    env = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise SystemExit(f"--env expects KEY=VALUE, got {pair!r}")
        env[key] = value
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True, help="image reference by digest: <name>@sha256:<hex>")
    ap.add_argument("--expect-version", required=True, help="model_version the gate must see")
    ap.add_argument("--env", action="append", help="runtime env var KEY=VALUE (repeatable)")
    args = ap.parse_args(argv)
    if "@sha256:" not in args.image:
        print("refusing to deploy by tag: --image must be name@sha256:<digest>", file=sys.stderr)
        return EXIT_START
    gc = Gcloud()
    gate_fn, canary_fn = build_checks(gc, config.load())
    return Deployer(gc, gate_fn, canary_fn).run(args.image, args.expect_version, parse_env(args.env))


if __name__ == "__main__":
    sys.exit(main())
