import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from binder_campaign.runner import run_task


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "input.txt").write_text("original")

    def task(self, code):
        spec = {"cwd":str(self.root), "command":[sys.executable,"-c",code], "revision":"fixture-v1",
                "timeout_seconds":3, "inputs":["input.txt"], "outputs":[{"path":"metrics.json","kind":"metrics_json","finite_keys":["score"]}],
                "state":"state.json", "log":"run.log"}
        path = self.root / "task.json"
        path.write_text(json.dumps(spec))
        return path

    def test_resume_requires_identical_inputs_and_outputs(self):
        spec = self.task("import pathlib; pathlib.Path('metrics.json').write_text('{\"score\": 0.7}')")
        self.assertEqual(run_task(spec)["status"], "success")
        self.assertTrue(run_task(spec)["resumed"])
        (self.root / "input.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            run_task(spec)

    def test_changed_output_refuses_resume(self):
        spec = self.task("import pathlib; pathlib.Path('metrics.json').write_text('{\"score\": 0.7}')")
        run_task(spec)
        (self.root / "metrics.json").write_text('{"score": 0.9}')
        with self.assertRaisesRegex(ValueError, "changed"):
            run_task(spec)

    def test_exit_zero_without_output_is_failure(self):
        with self.assertRaises(ValueError):
            run_task(self.task("pass"))
        self.assertEqual(json.loads((self.root / "state.json").read_text())["status"], "failed")

    def test_nan_rejected(self):
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            run_task(self.task("import pathlib; pathlib.Path('metrics.json').write_text('{\"score\": NaN}')"))

    def test_failure_code_preserved(self):
        with self.assertRaises(RuntimeError):
            run_task(self.task("raise SystemExit(7)"))
        self.assertEqual(json.loads((self.root / "state.json").read_text())["exit_code"], 7)

    def test_preexisting_output_rejected(self):
        (self.root / "metrics.json").write_text('{"score": 0.7}')
        with self.assertRaisesRegex(ValueError, "already exist"):
            run_task(self.task("pass"))

    def test_timeout_recorded_and_lock_released(self):
        path = self.task("import time; time.sleep(30)")
        spec = json.loads(path.read_text()); spec["timeout_seconds"] = 0.05
        path.write_text(json.dumps(spec))
        with self.assertRaises(subprocess.TimeoutExpired):
            run_task(path)
        self.assertFalse((self.root / "state.json.lock").exists())
        self.assertEqual(json.loads((self.root / "state.json").read_text())["status"], "failed")

    def test_signal_interrupt_stops_child_and_preserves_failed_state(self):
        path = self.task("import time; time.sleep(30)")
        parent = subprocess.Popen([sys.executable, "-m", "binder_campaign", "run", str(path)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+5
            child = None
            while time.monotonic() < deadline:
                state = self.root / "state.json"
                if state.exists():
                    child = json.loads(state.read_text()).get("pid")
                    if child:
                        break
                time.sleep(0.02)
            self.assertIsNotNone(child)
            parent.terminate()
            parent.wait(timeout=6)
            record = json.loads(state.read_text())
            self.assertEqual(record["status"], "failed")
            self.assertIn("InterruptedError", record["error"])
            self.assertFalse((self.root / "state.json.lock").exists())
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
        finally:
            if parent.poll() is None:
                parent.kill(); parent.wait()

    def test_header_only_csv_is_not_a_result(self):
        path = self.task("import pathlib; pathlib.Path('metrics.json').write_text('trajectory\\n')")
        spec = json.loads(path.read_text())
        spec["outputs"] = [{"path":"metrics.json", "kind":"csv", "columns":["trajectory"]}]
        path.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError, "insufficient"):
            run_task(path)

    def native_task(self):
        code="import pathlib; p=pathlib.Path('checkpoint'); first=not p.exists(); p.write_text('done'); pathlib.Path('metrics.json').write_text('{\"score\": 0.7}'); raise SystemExit(9 if first else 0)"
        path=self.task(code); spec=json.loads(path.read_text());spec['native_resume']=True
        path.write_text(json.dumps(spec));return path

    def test_explicit_native_resume_retains_failed_attempt_and_checks_partial_hashes(self):
        path=self.native_task()
        with self.assertRaises(RuntimeError):run_task(path)
        result=run_task(path)
        self.assertEqual(result['status'],'success');self.assertEqual(result['attempt'],2)
        self.assertEqual(json.loads((self.root/'state-attempts/1.json').read_text())['exit_code'],9)

    def test_changed_partial_output_blocks_native_resume(self):
        path=self.native_task()
        with self.assertRaises(RuntimeError):run_task(path)
        (self.root/'metrics.json').write_text('{"score":0.9}')
        with self.assertRaisesRegex(ValueError,'already exist or changed'):run_task(path)

    def test_failed_attempt_cannot_silently_change_settings(self):
        path=self.task('raise SystemExit(7)')
        with self.assertRaises(RuntimeError):run_task(path)
        spec=json.loads(path.read_text());spec['revision']='different';path.write_text(json.dumps(spec))
        with self.assertRaisesRegex(ValueError,'changed'):run_task(path)


if __name__ == "__main__":
    unittest.main()
