"""Harmless loop/sg harness. Never invokes ssh-sync transport or a real hub.

TEST_BASH selects the shell (including a real Bash 3.2); default is PATH bash.
Real sg is additionally exercised when available and replica membership exists.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BASH = os.environ.get("TEST_BASH") or shutil.which("bash")


def executable(path, body):
    path.write_text(body)
    path.chmod(0o755)


class LoopTests(unittest.TestCase):
    def run_loop(self, *, symlink=False, heal=True, real_sg=False):
        with tempfile.TemporaryDirectory(prefix="loop ' space ") as temp:
            root = Path(temp)
            repo = root / "independent checkout '"
            repo.mkdir()
            for name in ("loop.sh", "platform_paths.py"):
                shutil.copy2(HERE / name, repo / name)
            entry = repo / "loop.sh"
            if symlink:
                entry = root / "linked entry '"
                entry.symlink_to(repo / "loop.sh")
            workspace = root / "workspace ' space"
            workspace.mkdir()
            bin_dir = root / "bin space"
            bin_dir.mkdir()
            calls = root / "calls.jsonl"
            sg_calls = root / "sg.jsonl"
            python = bin_dir / "python shim"
            executable(python, "#!" + sys.executable + "\n" + '''import json, os, pathlib, signal, sys
if len(sys.argv) > 1 and pathlib.Path(sys.argv[1]).name == 'ssh-sync.py':
    p = pathlib.Path(os.environ['TEST_CALLS'])
    with p.open('a') as f: f.write(json.dumps(sys.argv[1:]) + '\\n')
    if len(p.read_text().splitlines()) >= 2: os.kill(os.getppid(), signal.SIGTERM)
    raise SystemExit(7)
os.execv(sys.executable, [sys.executable] + sys.argv[1:])
''')
            executable(bin_dir / "id", "#!/bin/sh\nif [ \"$AGENTS_SYNC_SG_REEXEC\" = 1 ] && [ \"$TEST_HEAL\" = 1 ]; then echo users replica; else echo users; fi\n")
            real_sg_path = shutil.which("sg")
            executable(bin_dir / "sg", "#!" + sys.executable + "\n" + '''import json, os, sys
with open(os.environ['TEST_SG_CALLS'], 'a') as f: f.write(json.dumps(sys.argv[1:]) + '\\n')
if os.environ.get('TEST_REAL_SG'):
    os.execv(os.environ['TEST_REAL_SG'], [os.environ['TEST_REAL_SG']] + sys.argv[1:])
os.execv('/bin/sh', ['sh', '-c', sys.argv[3]])
''')
            executable(bin_dir / "sleep", "#!/bin/sh\nexec /bin/sleep 0.05\n")
            env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                   "PYTHON": str(python), "PLATFORM_WORKSPACE": str(workspace),
                   "AGENTS_SYNC_REMOTE": "fixture.invalid:/neutral tree",
                   "TEST_CALLS": str(calls), "TEST_SG_CALLS": str(sg_calls),
                   "TEST_HEAL": str(int(heal))}
            env.pop("AGENTS_SYNC_SG_REEXEC", None)
            if real_sg:
                env["TEST_REAL_SG"] = real_sg_path
            proc = subprocess.Popen([BASH, str(entry)], cwd=root, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True, text=True)
            try:
                stdout, stderr = proc.communicate(timeout=15)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            sg_rows = [json.loads(x) for x in sg_calls.read_text().splitlines()]
            self.assertEqual(len(sg_rows), 1)
            words = shlex.split(sg_rows[0][2])
            self.assertEqual(words[-2:], [str(Path(BASH).resolve()), str(repo / "loop.sh")])
            if not heal:
                self.assertEqual(proc.returncode, 1, stderr)
                self.assertIn("already attempted sg once", stderr)
                self.assertFalse(calls.exists())
                return
            self.assertEqual(proc.returncode, 0, stderr + stdout)
            rows = [json.loads(x) for x in calls.read_text().splitlines()]
            self.assertEqual(len(rows), 2)  # restart, not just the first entrance
            for row in rows:
                self.assertEqual(row, [str(repo / "ssh-sync.py"), "watch", str(workspace / "agents"),
                                      "fixture.invalid:/neutral tree", "--debounce", "0.5", "--min-cycle", "3", "--interval", "30"])
            log = (workspace / "run/logs/agents-sync.log").read_text()
            self.assertIn("restarting in 4s", log)
            self.assertIn("TERM/INT", log)

    def test_real_entry_and_second_watch(self):
        self.run_loop()

    def test_symlink_entry_and_second_watch(self):
        self.run_loop(symlink=True)

    def test_failed_heal_refuses_before_loop(self):
        self.run_loop(heal=False, symlink=True)

    @unittest.skipUnless(shutil.which("sg") and "replica" in subprocess.check_output(["id", "-Gn"], text=True).split(), "real sg/replica unavailable")
    def test_real_sg_shell_quoting(self):
        self.run_loop(real_sg=True, symlink=True)


if __name__ == "__main__":
    print(subprocess.check_output([BASH, "--version"], text=True).splitlines()[0], flush=True)
    unittest.main()
