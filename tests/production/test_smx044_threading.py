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

            def state_request(_: int = 0):
                with urlopen(f"{base_url}/api/state", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    return json.loads(response.read().decode("utf-8"))["state"]

            def create_request(index: int):
                payload = json.dumps(
                    {
                        "action": "createThing",
                        "data": {
                            "label": f"Concurrent {index}",
                            "thing_id": f"concurrent-{index}",
                        },
                    }
                ).encode("utf-8")
                request = Request(
                    f"{base_url}/api/action",
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
                    snapshots = list(pool.map(state_request, range(24)))
                self.assertTrue(
                    all(snapshot["people"]["plane"] == "collaboration" for snapshot in snapshots)
                )
                self.assertTrue(
                    all(snapshot["together"]["plane"] == "runtime-networking" for snapshot in snapshots)
                )

                # Concurrent semantic writes have one bridge order and each accepted
                # edit is durably reflected by the local-first collaboration head.
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(create_request, range(8)))

                final = state_request()
                self.assertEqual(len(final["canonical"]["things"]), 8)
                self.assertEqual(
                    final["canonical"]["project_revision_id"],
                    final["people"]["head_revision_id"],
                )
                self.assertFalse(final["people"]["unsynced_local_work"])
                self.assertEqual(
                    {thing["thing_id"] for thing in final["canonical"]["things"]},
                    {f"concurrent-{index}" for index in range(8)},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
