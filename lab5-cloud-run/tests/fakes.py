"""An in-memory stand-in for deploy.gcloud.Gcloud that tracks traffic and tags."""
from deploy.gcloud import DeployFailed, Revision, Service, Target

SERVICE_URL = "https://lab5-forecast-fake.run.app"


class FakeGcloud:
    def __init__(self, traffic=None, revisions=None, refuse_deploy=False, fail_set_traffic_call=None):
        self.pct = dict(traffic or {})
        self.tags = {}
        self.exists = traffic is not None
        self.revisions = list(revisions or [])
        self.refuse_deploy = refuse_deploy
        self.fail_set_traffic_call = fail_set_traffic_call
        self.latest_created = next(iter(self.pct), "")
        self.deploys = []
        self.set_traffic_calls = []
        self.removed_tags = []
        self._n = len(self.revisions)

    # -- reads
    def get_service(self):
        if not self.exists:
            return None
        targets = []
        for rev, p in self.pct.items():
            if p > 0:
                tag = next((t for t, r in self.tags.items() if r == rev), None)
                targets.append(Target(rev, p, tag, f"https://{tag}---fake.run.app" if tag else None))
        for tag, rev in self.tags.items():
            if not any(t.tag == tag for t in targets):
                targets.append(Target(rev, 0, tag, f"https://{tag}---fake.run.app"))
        return Service("lab5-forecast", SERVICE_URL, tuple(targets), self.latest_created, self.latest_created)

    def list_revisions(self):
        return list(self.revisions)

    def identity_token(self):
        return "fake-token"

    # -- writes
    def deploy(self, image, *, env=None, no_traffic=False, tag=None):
        self.deploys.append({"image": image, "env": env, "no_traffic": no_traffic, "tag": tag})
        if self.refuse_deploy:
            raise DeployFailed(["run", "deploy"], 1, "startup probe failed")
        self._n += 1
        name = f"lab5-forecast-{self._n:05d}"
        self.revisions.append(Revision(name, True, f"2026-11-18T00:00:{self._n:02d}Z"))
        self.latest_created = name
        self.exists = True
        if tag:
            self.tags[tag] = name
        if not no_traffic:
            self.pct = {name: 100}

    def set_traffic(self, percents):
        self.set_traffic_calls.append(dict(percents))
        if self.fail_set_traffic_call == len(self.set_traffic_calls):
            raise RuntimeError("simulated gcloud failure")
        self.pct = dict(percents)

    def remove_tag(self, tag):
        self.removed_tags.append(tag)
        self.tags.pop(tag, None)
