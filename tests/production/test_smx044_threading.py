from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.request import Request, urlopen

from splashmx.editor.browser_server import run_server


class SMX044ThreadedBrowserBoundaryTests(unittest.TestCase):
    def test_threaded_http_requests_keep_people_store_thread_affine_and_semantically_serial(self):
        """ThreadingHTTPServer must not share one SQLite connection across request threads."""
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "browser.sqlite3"
            server = run_server(
                "127.0.0.1",
                0,
                project_id="smx044-threaded",
                store_path=store_path,
            )
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"

            def state_request(url: str):
                with urlopen(f"{url}/api/state", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    return json.loads(response.read().decode("utf-8"))["state"]

            def create_request(url: str, index: int):
                payload = json.dumps(
                    {
                        "action": "createThing",
                        "data": {"label": f"Concurrent {index}"},
                    }
                ).encode("utf-8")
                request = Request(
                    f"{url}/api/action",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    return json.loads(response.read().decode("utf-8"))["state"]

            try:
                # This exact fan-out reproduced the pre-fix SQLite thread-affinity
                # failure: the People store was constructed on the server owner thread
                # and then touched by arbitrary ThreadingHTTPServer request threads.
                with ThreadPoolExecutor(max_workers=8) as pool:
                    snapshots = list(pool.map(lambda _: state_request(base_url), range(24)))
                self.assertTrue(
                    all(snapshot["people"]["plane"] == "collaboration" for snapshot in snapshots)
                )
                self.assertTrue(
                    all(snapshot["together"]["plane"] == "runtime-networking" for snapshot in snapshots)
                )

                # Concurrent semantic writes have one bridge order. Generated stable
                # identities must remain monotonic across People publication rather than
                # resetting each time a local revision is durably recorded.
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda index: create_request(base_url, index), range(8)))

                final = state_request(base_url)
                self.assertEqual(len(final["canonical"]["things"]), 8)
                self.assertEqual(
                    final["canonical"]["project_revision_id"],
                    final["people"]["head_revision_id"],
                )
                self.assertFalse(final["people"]["unsynced_local_work"])
                self.assertEqual(
                    {thing["thing_id"] for thing in final["canonical"]["things"]},
                    {f"thing-{index:06d}" for index in range(1, 9)},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())

            # Reopening from collaboration history must recover the generated-identity
            # floor as well as the canonical head, or the first post-restart authoring
            # action can collide with an existing stable ThingId.
            reopened = run_server(
                "127.0.0.1",
                0,
                project_id="smx044-threaded",
                store_path=store_path,
            )
            reopened_thread = Thread(target=reopened.serve_forever, daemon=True)
            reopened_thread.start()
            reopened_url = f"http://127.0.0.1:{reopened.server_address[1]}"
            try:
                create_request(reopened_url, 9)
                recovered = state_request(reopened_url)
                self.assertEqual(len(recovered["canonical"]["things"]), 9)
                self.assertIn(
                    "thing-000009",
                    {thing["thing_id"] for thing in recovered["canonical"]["things"]},
                )
                self.assertEqual(
                    recovered["canonical"]["project_revision_id"],
                    recovered["people"]["head_revision_id"],
                )
            finally:
                reopened.shutdown()
                reopened.server_close()
                reopened_thread.join(timeout=5)
                self.assertFalse(reopened_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
