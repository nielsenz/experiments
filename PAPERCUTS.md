# Papercuts

Small frictions logged in the moment — dead-end tool calls, misleading errors,
undocumented setup steps, flaky commands. Not blocking on their own; together
they show where this repo needs sanding down. Append-only, newest at the bottom.

2026-09-04T04:54:37.373Z - gpt-5.6-sol - znielsen

The weather-capture ensemble archive documents a rolling 93-day upstream limit but hard-codes start_date=2026-04-25 and writes a single archive.json.gz that resumability will skip forever; by 2026-09-03 a fresh call requests 131 past days and fails, while a successful old file prevents the periodic extension the README promises.

2026-09-04T04:55:47.570Z - gpt-5.6-sol - znielsen

The documented weather-capture unittest command fails in a fresh checkout because requests is not installed and the README does not tell test runners to install requirements first; only check_gaps tests run, while test_backfill and test_fetch fail during import.

2026-09-04T04:57:15.356Z - gpt-5.6-sol - znielsen

The resumable ensemble_mean backfill was planned for 24 calls, but the exec session reported completion after 10 files with no exit status or summary; the 3-second per-call pacing makes the full job exceed the wrapper's apparent ~30-second lifecycle despite yielding a cell, so repeated invocations are required.

2026-09-04T16:22:04.073Z - gpt-5.6-sol - znielsen

The weather-capture test command had passed earlier with uv --with requests, but a repeat still tried to resolve PyPI and failed on sandbox DNS instead of using the populated task cache. Reliable offline tests need requests declared in the project environment or a locked cache path.

2026-09-04T16:23:48.395Z - gpt-5.6-sol - znielsen

Creating the archive commit produced Git's auto-detected author warning because this checkout has no explicit user.name/user.email. Repository setup should document or initialize commit identity before automated contributor workflows.

2026-09-04T16:24:40.713Z - gpt-5.6-sol - znielsen

Pushing the weather archive branch triggered GitHub's 50 MB warning for the unrelated existing blob papyri-linkedin/papyri_graph_5k_canonical.json (62.23 MB). The repo history carries a large non-LFS object, so otherwise small branch pushes surface a distracting storage warning.

2026-09-04T16:25:31.423Z - gpt-5.6-sol - znielsen

After opening the weather-capture PR, gh pr checks reported no checks on the branch. The repository has no PR validation for the 100-test suite or archive integrity check, so local results are the only automated evidence.
