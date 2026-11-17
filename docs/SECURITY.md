# Sandbox security

Submissions are arbitrary Python written by users. This page describes what the
sandbox is meant to stop, how, and what it does not cover. Each mitigation listed
under "Enforced" has a test in `backend/tests/test_sandbox.py` that runs hostile code
in the real container.

## What we protect

1. The host and the other services (database, queue, other users' data).
2. The hidden objective functions and instance parameters.
3. The integrity of results: a submission must not be able to report its own score.
4. Availability: one submission must not starve the machine.

## Design

- One container per run, removed afterwards. Nothing persists between runs.
- The objective function, instance seeds, shifts and rotations are never copied into
  the container. The container holds Python, NumPy, SciPy and a small harness. The
  submission receives only objective values for the points it sends.
- The judge process, outside the container, counts evaluations, enforces the budget
  and records the trace. Messages from the container are treated as untrusted: sizes
  are bounded, a request for more points than the budget allows ends the run, and a
  malformed message is reported as a crashed run.
- The submission's source is passed over the protocol pipe, so no host directory is
  mounted into the container.

## Enforced

| Threat | Mitigation |
|---|---|
| Network access, data exfiltration | `--network none` |
| Writing to the image or filesystem | `--read-only` root filesystem |
| Filling the disk | `/tmp` is a 16 MB `tmpfs`, mounted `noexec,nosuid` |
| Running as root | `--user 65534:65534` |
| Privilege escalation | `--cap-drop ALL`, `--security-opt no-new-privileges` |
| Fork bomb | `--pids-limit 64` |
| Memory exhaustion | `--memory` with swap disabled (default 512 MB) |
| CPU starvation | `--cpus` (default 1) |
| Infinite loop | Wall-clock timeout (default 120 s); the container is killed |
| Output flood | The log is read continuously and truncated to 64 kB |
| Corrupting the protocol by printing | stdout/stderr are redirected to the log before user code is loaded |
| Reading the hidden function | It is not in the container |
| Contributed fitness functions | Evaluated only in their own container with the same limits (`sandbox/evaluator.py`); the worker relays points over a pipe and treats a stalled evaluator as failed evaluations |
| Hidden data reaching a language model | Prompts get the code and relative precisions only; seeds, shifts, rotations, reference values and held-out results are never included (`backend/ai/features.py`) |

Every failure is reported to the user as a run status (`error`, `timeout` or
`crashed`) with a message. A failed run scores 0.

## Not covered

- Container escape through a kernel vulnerability. Containers share the host kernel.
  Setting `SANDBOX_RUNTIME=runsc` runs submissions under gVisor where it is installed;
  this path is supported by the runner but has not been tested in this project yet.
- The submission can find the protocol pipe inside its own process and write garbage
  to it. This only breaks its own run.
- A submission can learn about an instance through the values it is given, which is
  the point of the exercise. Final rankings are meant to use instance seeds that are
  never exposed in public runs.
- Timing side channels and hardware attacks are out of scope.

## Accounts

- Passwords are hashed with Argon2. Session tokens are held in httpOnly, SameSite=Lax
  cookies (Secure outside development); refresh tokens are single-use.
- State-changing requests from another origin are refused.
- Code, logs and error messages of a submission are visible only to its author and admins.
- Sign-in lock: after `LOGIN_MAX_FAILURES` wrong passwords for one email within
  `LOGIN_WINDOW_MIN` minutes, sign-in to that account is refused (429) until the window
  has passed or the password is reset. Unknown emails are counted the same way, so a
  lock does not reveal whether an account exists. The count is per email address, not
  per IP address: the API sits behind the frontend proxy and cannot trust client
  addresses on its own. Limit attempts per IP at the reverse proxy (see
  `DEPLOYMENT.md`) to slow down guessing across many accounts.
- Email confirmation and password reset use signed links (JWT) that expire after two
  days and one hour. Each link carries a fingerprint of the account's email and
  password hash, so a reset link works once and every earlier link stops working when
  the password changes. At most three links of each kind are sent per address per
  hour. "Forgot password" answers the same way whether or not the account exists.
- A password reset signs the account out on every device (all refresh tokens are
  deleted). With `REQUIRE_VERIFIED_EMAIL=true`, submissions and contributions need a
  confirmed email address.
- A daily worker job deletes expired refresh tokens and account events older than a day.

## Operating notes

- The process that launches containers needs access to the Docker daemon, which is
  equivalent to root on that host. Run the worker on a dedicated VM, not next to
  unrelated services.
- In the Compose setup the worker container mounts the host Docker socket. Treat that
  container as privileged.
- Keep the sandbox image and Docker up to date.
