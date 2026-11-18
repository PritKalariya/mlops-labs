"""The only module that runs gcloud. Argument lists only, never a shell.

Identity tokens come from `gcloud auth print-identity-token` and live in memory:
they are not printed, logged, or written anywhere.
"""
import json
import subprocess
from dataclasses import dataclass

from . import config


class GcloudError(RuntimeError):
    def __init__(self, args_, returncode, stderr):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"gcloud {' '.join(args_[:3])} failed (rc={returncode}): {stderr.strip()[-600:]}")


class DeployFailed(GcloudError):
    """`run deploy` returned non-zero: Cloud Run refused the revision."""


@dataclass(frozen=True)
class Target:
    revision: str
    percent: int
    tag: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Service:
    name: str
    url: str
    targets: tuple[Target, ...]
    latest_created: str
    latest_ready: str

    def tagged(self, tag):
        return next((t for t in self.targets if t.tag == tag), None)

    def serving(self):
        """Targets with traffic, tag-only entries excluded."""
        return [t for t in self.targets if t.percent > 0]


@dataclass(frozen=True)
class Revision:
    name: str
    ready: bool
    created: str


def fmt_traffic(targets):
    live = [f"{t.revision}={t.percent}%" for t in targets if t.percent > 0]
    tags = [f"{t.tag}->{t.revision}" for t in targets if t.tag]
    return ", ".join(live) + (f"  tags: {', '.join(tags)}" if tags else "")


PROBE_FLAGS = [
    "--startup-probe=httpGet.path=/health/ready,httpGet.port=8080,periodSeconds=2,timeoutSeconds=1,failureThreshold=30",
    "--liveness-probe=httpGet.path=/health/live,httpGet.port=8080,periodSeconds=10,timeoutSeconds=1,failureThreshold=3",
]


class Gcloud:
    def __init__(self, service=config.SERVICE, project=config.PROJECT, region=config.REGION, binary="gcloud"):
        self.service, self.project, self.region, self.binary = service, project, region, binary

    def _run(self, args, *, capture=True):
        cmd = [self.binary, *args, "--project", self.project]
        proc = subprocess.run(cmd, capture_output=capture, text=True, check=False)
        return proc

    def _regional(self, args):
        return self._run([*args, "--region", self.region])

    def get_service(self):
        proc = self._regional(["run", "services", "describe", self.service, "--format=json"])
        if proc.returncode != 0:
            if "Cannot find service" in proc.stderr or "not found" in proc.stderr.lower():
                return None
            raise GcloudError(["run", "services", "describe"], proc.returncode, proc.stderr)
        doc = json.loads(proc.stdout)
        status = doc.get("status", {})
        targets = tuple(
            Target(revision=t.get("revisionName", ""), percent=int(t.get("percent", 0)),
                   tag=t.get("tag"), url=t.get("url"))
            for t in status.get("traffic", [])
        )
        return Service(name=self.service, url=status.get("url", ""), targets=targets,
                       latest_created=status.get("latestCreatedRevisionName", ""),
                       latest_ready=status.get("latestReadyRevisionName", ""))

    def deploy(self, image, *, env=None, no_traffic=False, tag=None):
        """Every setting is passed on every deploy, so a revision never inherits a
        stale env var or probe from the one before it."""
        args = [
            "run", "deploy", self.service, "--image", image,
            "--service-account", config.SERVICE_ACCOUNT,
            "--no-allow-unauthenticated",
            "--concurrency", "10", "--cpu", "1", "--memory", "512Mi",
            "--min-instances", "0", "--max-instances", "2",
            "--port", "8080", "--labels", config.LABEL,
            *PROBE_FLAGS,
        ]
        if env:
            args += ["--set-env-vars", ",".join(f"{k}={v}" for k, v in env.items())]
        else:
            args += ["--clear-env-vars"]
        if no_traffic:
            args += ["--no-traffic"]
        if tag:
            args += ["--tag", tag]
        proc = self._regional(args)
        if proc.returncode != 0:
            raise DeployFailed(args, proc.returncode, proc.stderr)

    def set_traffic(self, percents):
        spec = ",".join(f"{rev}={pct}" for rev, pct in percents.items())
        proc = self._regional(["run", "services", "update-traffic", self.service, "--to-revisions", spec])
        if proc.returncode != 0:
            raise GcloudError(["run", "services", "update-traffic"], proc.returncode, proc.stderr)

    def remove_tag(self, tag):
        proc = self._regional(["run", "services", "update-traffic", self.service, "--remove-tags", tag])
        if proc.returncode != 0:
            raise GcloudError(["run", "services", "update-traffic"], proc.returncode, proc.stderr)

    def list_revisions(self):
        proc = self._regional(["run", "revisions", "list", "--service", self.service, "--format=json"])
        if proc.returncode != 0:
            raise GcloudError(["run", "revisions", "list"], proc.returncode, proc.stderr)
        out = []
        for doc in json.loads(proc.stdout):
            conds = doc.get("status", {}).get("conditions", [])
            ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
            meta = doc.get("metadata", {})
            out.append(Revision(name=meta.get("name", ""), ready=ready, created=meta.get("creationTimestamp", "")))
        return out

    def identity_token(self):
        proc = self._run(["auth", "print-identity-token"])
        if proc.returncode != 0:
            raise GcloudError(["auth", "print-identity-token"], proc.returncode, "no token (not echoed)")
        return proc.stdout.strip()
