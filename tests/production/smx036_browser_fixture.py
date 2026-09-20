from __future__ import annotations

import signal

from splashmx.canonical.core import CanonicalDocument, ProjectId, ProjectRevisionId
from splashmx.canonical.serialization import CanonicalProjectRevision
from splashmx.packages.model import ResolutionLock
from splashmx.publishing.browser_server import run_server
from splashmx.publishing.generic import CreationId, HostedReleaseId, HostedReleaseStore, publish_creation


def creation(revision: str, *, required_features=()):
    project = CanonicalProjectRevision(CanonicalDocument(ProjectId("browser-project"), ProjectRevisionId(revision)), {})
    return publish_creation(CreationId("browser-creation"), project, ResolutionLock("browser-catalog", {}), {}, required_features=required_features)


def main() -> int:
    store = HostedReleaseStore()
    store.publish_release(HostedReleaseId("release-good"), creation("project-good"))
    store.publish_release(HostedReleaseId("release-unsupported"), creation("project-unsupported", required_features=("future.browser.feature",)))
    store.retarget_alias("play", HostedReleaseId("release-good"))
    store.retarget_alias("unsupported", HostedReleaseId("release-unsupported"))
    server = run_server("127.0.0.1", 0, store)
    print(f"SMX036 READY http://127.0.0.1:{server.server_address[1]}", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: server.shutdown())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
