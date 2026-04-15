from __future__ import annotations

import asyncio
import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QCoreApplication
    from gui.views.analysis import AnalysisWorker
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    QCoreApplication = None
    AnalysisWorker = None


class _StreamingAgent:
    def __init__(self) -> None:
        self.asyncgen_closed = False

    async def run(self, task, history, on_chunk):
        async def _gen():
            try:
                yield "a"
                await asyncio.sleep(0.05)
                yield "b"
            finally:
                self.asyncgen_closed = True

        agen = _gen()
        _ = await agen.__anext__()
        on_chunk("chunk")
        await asyncio.sleep(0.02)
        return "done"


class _CancellableAgent:
    async def run(self, task, history, on_chunk):
        while True:
            on_chunk(".")
            await asyncio.sleep(0.01)


@unittest.skipUnless(QCoreApplication is not None and AnalysisWorker is not None, "PyQt6 not available")
class AnalysisWorkerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def _pump_until_done(self, worker, timeout_s: float = 5.0) -> None:
        deadline = time.time() + timeout_s
        while worker.isRunning() and time.time() < deadline:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        worker.wait(int(timeout_s * 1000))
        # Flush queued signals onto main thread.
        for _ in range(10):
            QCoreApplication.processEvents()
            time.sleep(0.005)

    def test_worker_finishes_and_shuts_asyncgens(self) -> None:
        agent = _StreamingAgent()
        worker = AnalysisWorker(agent, "task", [])

        finished_event = threading.Event()
        result_holder: list[str] = []
        errors: list[str] = []

        worker.finished.connect(lambda text: (result_holder.append(text), finished_event.set()))
        worker.error.connect(lambda err: errors.append(err))

        worker.start()
        self._pump_until_done(worker)

        self.assertTrue(finished_event.is_set(), "finished signal not emitted")
        self.assertEqual(result_holder, ["done"])
        self.assertEqual(errors, [])
        self.assertTrue(agent.asyncgen_closed, "async generator was not finalized")

    def test_worker_cancel_emits_cancelled(self) -> None:
        agent = _CancellableAgent()
        worker = AnalysisWorker(agent, "task", [])

        cancelled_event = threading.Event()
        cancelled_count = [0]
        worker.cancelled.connect(
            lambda: (cancelled_count.__setitem__(0, cancelled_count[0] + 1), cancelled_event.set())
        )

        worker.start()
        time.sleep(0.08)
        worker.cancel()
        self._pump_until_done(worker)

        self.assertTrue(cancelled_event.is_set(), "cancelled signal not emitted")
        self.assertEqual(cancelled_count[0], 1)

    def test_worker_can_restart_without_leaked_state(self) -> None:
        results: list[str] = []

        for _ in range(2):
            agent = _StreamingAgent()
            worker = AnalysisWorker(agent, "task", [])
            worker.finished.connect(lambda text: results.append(text))
            worker.start()
            self._pump_until_done(worker)

        self.assertEqual(results, ["done", "done"])


if __name__ == "__main__":
    unittest.main()
