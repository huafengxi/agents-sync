#!/usr/bin/env python3
"""Foreground, asymmetric file transport for controller-owned declarations.

Caller supplies every path/endpoint. This is NOT the replica/group/GC agents
transport. Desired input is pulled only; the sole reverse direction is one
explicit observation file. No deletes, remote commands, activation or callbacks.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time


class Link:
    def __init__(self, config):
        required = {'desiredRemote', 'desiredLocal', 'observationLocal', 'observationRemote', 'sshConfig', 'rsync'}
        if not required <= config.keys() or config.keys() - required - {'interval', 'timeout'}:
            raise ValueError('invalid declaration transport fields')
        for key in ('desiredLocal', 'observationLocal', 'sshConfig', 'rsync'):
            if not isinstance(config[key], str) or not Path(config[key]).is_absolute():
                raise ValueError('absolute ' + key + ' required')
        for key in ('desiredRemote', 'observationRemote'):
            value = config[key]
            if not isinstance(value, str) or ':' not in value or value.startswith('-') or any(c.isspace() for c in value):
                raise ValueError('explicit host:/absolute/file remote required')
            host, path = value.split(':', 1)
            if not host or not path.startswith('/') or '..' in Path(path).parts:
                raise ValueError('invalid remote file')
        for key, default, minimum, maximum in (('interval', 5, .1, 3600), ('timeout', 60, 1, 600)):
            value = config.get(key, default)
            if type(value) not in (int, float) or not minimum <= value <= maximum:
                raise ValueError('invalid ' + key)
        self.config = config
        self.stopped = False
        self.child = None

    def stop(self, *unused):
        self.stopped = True
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()

    def transfer(self, source, destination):
        if self.stopped:
            return False
        c = self.config
        ssh = shlex.join(['ssh', '-F', c['sshConfig'], '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                          '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ControlPersist=no',
                          '-o', 'PermitLocalCommand=no'])
        argv = [c['rsync'], '-tc', '--protect-args', '-e', ssh, '--', source, destination]
        self.child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # A signal can arrive between the pre-spawn check and Popen publication.
        if self.stopped and self.child.poll() is None:
            self.child.terminate()
        try:
            try:
                out, err = self.child.communicate(timeout=c.get('timeout', 60))
            except subprocess.TimeoutExpired:
                self.child.terminate()
                try:
                    out, err = self.child.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    self.child.kill()
                    out, err = self.child.communicate()
            rc = self.child.returncode
            if rc:
                print(json.dumps(dict(event='transfer-failed', source=source, exitCode=rc,
                                      diagnostic=err.decode(errors='replace')[-1500:])), flush=True)
            return rc == 0
        finally:
            # communicate owns the real direct wait. External Runtime retains
            # native process-group closure for rsync/ssh descendants.
            if self.child.poll() is None:
                self.child.terminate()
                self.child.wait()
            self.child = None

    def cycle(self):
        c = self.config
        pulled = self.transfer(c['desiredRemote'], c['desiredLocal'])
        pushed = False
        if not self.stopped and Path(c['observationLocal']).is_file():
            pushed = self.transfer(c['observationLocal'], c['observationRemote'])
        return pulled, pushed

    def run(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self.stop)
        while not self.stopped:
            try:
                self.cycle()
            except OSError as error:
                print(json.dumps(dict(event='transport-error', diagnostic=str(error))), flush=True)
            end = time.monotonic() + self.config.get('interval', 5)
            while not self.stopped and time.monotonic() < end:
                time.sleep(.1)
        return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--once', action='store_true')
    args = p.parse_args()
    link = Link(json.loads(args.config.read_text()))
    if args.once:
        return 0 if all(link.cycle()) else 1
    return link.run()


if __name__ == '__main__':
    raise SystemExit(main())
