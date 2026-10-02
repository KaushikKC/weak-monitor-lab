# Amendment to 2026-10-01 pre-registration: disk threshold (2026-10-02)

Operational only. No change to data, detectors, outcomes or analysis.

* The original rule started the Part 2 agent run only if at least 15 GB was free. At launch, 13 GB was
  free and memory pressure was low (68% free).
* Change: Part 2 starts with 13 GB free, guarded by a watchdog that interrupts the run cleanly (SIGINT →
  checkpoint + `interrupted.jsonl`) if free space falls below 3 GB. An interrupted run is resumed with
  `wml resume` once space is freed. Interruption affects timing only.
* Reason: the user asked to run now. A clean interrupt is safer than letting the disk fill completely,
  which previously crashed the session's tooling.
