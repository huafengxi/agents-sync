# Recovery and standalone adaptation — task/rd6-y-171006

## Scope and source

Original main is `573dabf7cf0dbffe49e956760dae1a29d900bde1`. Original named refs, source remote-ref mappings and exact OIDs are in `source-refs.json`; these describe the **preservation baseline**, not the advancing restored main. Preserve refs must stay unchanged; original main must remain an ancestor.

The source baseline is agent-platform `990253da3b5c5ec83fd43a2a463f39ed6d42aadf`. Every original main path/mode/blob matches its import under `agents-sync/`. Initial freeze was `fb758234da0bd717d511dd41999679fa0bbf4427`. Closing source/origin advanced to `4ac4631fbdbf27f3c400805b233dc1d7a9892d46` (c8tpr5 pi-wrap thinking changes); this is appended as a no-op for this module, not copied from its earlier dirty tree. Final source worktree is clean. No in-flight source working-tree content was used.

`source-map.json` lists every source first-parent commit, including no-ops; full source SHA, parent, paths, target paths, before/after blobs/modes/deletions and projected target SHA are explicit. No whole cross-module cherry-pick or filter rewrite was used. Only these source selections project executable content:

- `agents-sync/**` → repository root, unchanged bytes/modes.
- `platform_paths.py` and `test_platform_paths.py` → root. These are the owned local helper's source, subsequently adapted.
- root `README.md`: documentation scope is mapped separately in `root-readme-map.json`; integrated multi-module assembly/deployment material is not copied as a standalone runtime dependency. Relevant local mechanisms are restated in README, while source versions remain in preserved source history.

There are three nonempty source projections (9809211…, 4dd1b8e…, 8418404…); all other source commits are recorded no-ops for the selected executable paths. No source deletion/reversal affects these selected paths in this interval; removed portable installers are outside this module and are not resurrected. `delete_contract.py` and its producer/consumer changes project together from 8418404, preserving ownership here.

`projection-checks.json` and `projection-verification.json` give per-path and per-commit exact content/mode checks **before adaptation**. `net-path-map.json` records original main, projected source and adapted file identity for each non-recovery path, with per-path adaptation explanations. Recovery documents are new provenance artifacts, not source-projected code. All source changes and original history remain distinguishable from adaptation.

## Deliberate adaptation (separate commit)

| Paths | Difference and contract |
|---|---|
| `platform_paths.py`, `test_platform_paths.py` | Local thin helper; no MODULES deployment roster, parent-marker or sibling import. Nonempty PLATFORM_WORKSPACE wins (expanduser + absolute); default is real source repo parent; relative overrides retain cwd semantics. Tests use independent unmarked layouts and a hostile parent helper. |
| `gc.py`, `ssh-sync.py`, `replica-tag.py` | Import from real local source directory, never unified parent. delete_contract is local. Runtime deployment values become caller injection: AGENTS_SYNC_REMOTE, AGENTS_SYNC_HUB, AGENTS_SYNC_HUB_DIR. SSH_SYNC_CONFIG remains explicit, default becomes conventional ~/.ssh/config rather than a caller workspace secret layout. GC priority and legacy workspace fallback remain; callers must supply their actual neutral hub path. |
| `loop.sh` | Resolve real entry once, use local helper; SG command POSIX-quotes all arguments and carries resolved workspace/Python/current Bash/entry. Every loop child uses the real local ssh-sync path. No cwd=$workspace + agents-sync/loop.sh assumption. Existing replica name, one-attempt heal/refusal, backoff thresholds and child TERM handling retained. No production profile/match changes. |
| `test_replica_tag.py` | Existing synthetic topology explicitly injects its own hub identity, never relies on a live deployment value. Classification rules unchanged. |
| `test_loop.py`, `test_independent.py` | New harmless regression fixtures: actual sg plus fake credential check/transport, second watch invocation, real and symlink paths with spaces/apostrophes, failed-heal refusal, isolated module CLI/imports and caller configuration. No actual SSH or production-root deletion. |
| `README.md` | Standalone mechanism/configuration/test contract; no integrated deployment coordinates or unimplemented installer/caller activation. |
| `mac-rsync-patch/install.sh`, `mac-rsync-patch/README.md` | Inherited optional installer smoke no longer uses a shared fixed deletion path or deployment gid; fresh retained temporary tree and group-name assertion. Formula commit uses an explicit path. No brew install/uninstall or deployment was run. Only Bash syntax checked in this recovery. |

Hub star topology, zero-originals, single-writer gate, producer/consumer delete-list format and protections, replica group identity, offline cumulative deletion and detector reconnection logic are not redesigned. Missing required endpoint/hub configuration fails before network/tagging; this is explicit standalone configuration, not the declined D6 automatic guard. Full source behavior remains inspectable in projected commits.

## Tests and boundaries

Task-local staging root contains `run_isolated.py` (reproduction entry) and `harness/` with complete `test_*.log` and `results.json`. Runner creates HOME/TMPDIR/workspace under this self-owned root and runs all eight test files in separate processes. It loads an exact read-only copy of `agentd/safe_delete.py` from source freeze `fb758234da0bd717d511dd41999679fa0bbf4427`; historical suite shutil.rmtree calls are redirected through safe_rmtree with only the self-created harness/tmp as authorized root. The helper is **test harness only**, not a sibling/production runtime dependency or a second deletion policy in this repo. Its SHA and provenance are in the task report. No cleanup root is production, retired or archive.

Results: gc 335, watch 65 (zero skips), replica-tag 82; delete-contract 3, protect 2, local-root 3, independent import/config 3, loop 4. All pass. Watch's real rsync/inotify tests operate on synthetic local trees; command-construction tests intercept subprocess calls, with no actual SSH. Real sg is exercised by loop tests, but watch itself is replaced by a harmless recorder.

A real GNU Bash 3.2.0(2) was built in this task's isolated root from upstream bash-3.2.tar.gz; the same 4 loop cases all pass under it, including real sg, and both loop/optional installer pass Bash3.2 `-n`. macOS worker was offline, so this is a genuine Linux Bash3.2 test, **not** a claim of live macOS transport/installer validation.

First runner execution passed historical script suites but passed an extra filename to unittest; fixed sys.argv in the outer runner and reran all suites successfully. No source behavior failure was hidden. Complete first/second/final runner logs remain in task artifacts.

No model call, production fetch test, production sync/deletion, service change, profile edit or restart. Candidate source only; independent review and production authorization remain external gates.
