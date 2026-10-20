"""Retained asymmetric transport fixtures; not real SSH/rsync validation."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

BASE = Path(os.environ['DECLARATION_SYNC_OUTPUT']).resolve()
BASE.mkdir(mode=0o700)
S = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('declaration_sync', S / 'declaration-sync.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class Tests(unittest.TestCase):
    def setUp(self):
        self.area = BASE / self._testMethodName; self.area.mkdir()
        self.fake = self.area / 'rsync'
        self.fake.write_text('#!' + sys.executable + '''
import json,sys,shutil
from pathlib import Path
src,dst=sys.argv[-2:]
p=Path(__file__).parent
with (p/'calls').open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
src=src.split(':',1)[-1];dst=dst.split(':',1)[-1]
shutil.copyfile(src,dst)
''')
        self.fake.chmod(0o700)
        self.remote = self.area / 'master.json'; self.local = self.area / 'worker.json'
        self.observation = self.area / 'actual.json'; self.readback = self.area / 'readback.json'
        self.config = dict(desiredRemote='fixture:' + str(self.remote), desiredLocal=str(self.local),
                           observationLocal=str(self.observation), observationRemote='fixture:' + str(self.readback),
                           sshConfig=str(self.area / 'ssh-config'), rsync=str(self.fake), interval=.1)

    def test_one_way_reconnect_and_repeat(self):
        self.remote.write_text('version 1'); self.observation.write_text('real snapshot')
        link = module.Link(self.config)
        self.assertEqual(link.cycle(), (True, True))
        self.assertEqual(self.local.read_text(), 'version 1')
        # No active link while the controller moves directly to its newest state.
        self.remote.write_text('version 3')
        self.local.write_text('worker must not publish this')
        self.assertEqual(link.cycle(), (True, True))
        self.assertEqual(self.remote.read_text(), 'version 3')
        self.assertEqual(self.local.read_text(), 'version 3')
        self.assertEqual(self.readback.read_text(), 'real snapshot')
        link.cycle()
        calls = [json.loads(line) for line in (self.area / 'calls').read_text().splitlines()]
        self.assertTrue(all('--delete' not in args for args in calls))
        self.assertEqual([c[-2] for c in calls[::2]], [self.config['desiredRemote']] * 3)
        link.stop(); count = len(calls); link.cycle()
        self.assertEqual(len((self.area / 'calls').read_text().splitlines()), count)

    def test_real_foreground_stop_waits_child(self):
        self.fake.write_text('#!' + sys.executable + '''
import os,time
from pathlib import Path
Path(__file__).with_name('child-pid').write_text(str(os.getpid()))
time.sleep(60)
''')
        self.remote.write_text('state')
        config = self.area / 'config.json'; config.write_text(json.dumps(self.config))
        with (self.area / 'stdout').open('wb') as out, (self.area / 'stderr').open('wb') as err:
            child = subprocess.Popen([sys.executable, str(S / 'declaration-sync.py'), '--config', str(config)], stdout=out, stderr=err)
            try:
                end = time.monotonic() + 5
                while not (self.area / 'child-pid').exists() and time.monotonic() < end: time.sleep(.01)
                self.assertTrue((self.area / 'child-pid').exists())
                pid = int((self.area / 'child-pid').read_text())
                child.send_signal(signal.SIGTERM)
                self.assertEqual(child.wait(timeout=5), 0)
                with self.assertRaises(ProcessLookupError): os.kill(pid, 0)
            finally:
                if child.poll() is None: child.terminate(); child.wait(timeout=5)

    def test_invalid_endpoints_refused(self):
        for key, value in [('desiredRemote', '-bad:/file'), ('desiredLocal', 'relative'),
                           ('observationRemote', 'host:relative'), ('timeout', 0)]:
            with self.assertRaises(ValueError): module.Link(dict(self.config, **{key: value}))


if __name__ == '__main__': unittest.main(verbosity=2)
