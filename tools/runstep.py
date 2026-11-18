# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Run one `run:` step of a workflow job outside Actions, the way the runner would.

usage: runstep.py WORKFLOW JOB STEP-NAME-OR-ID [KEY=VALUE ...]
Env = workflow env + job env + step env (later wins), then GITHUB_ENV written by earlier
steps (state dir), then KEY=VALUE overrides. Any value still containing ${{ }} must be
overridden, or the step aborts. cwd = $WORKDIR (default .). Outputs go to $STATE/outputs.
"""
import os, subprocess, sys, yaml

wf_path, job, step_key, *kv = sys.argv[1:]
wf = yaml.safe_load(open(wf_path))
j = wf["jobs"][job]
steps = [s for s in j["steps"] if s.get("name") == step_key or s.get("id") == step_key]
if len(steps) != 1:
    sys.exit(f"step {step_key!r} not found once in {job}: {[s.get('name') or s.get('id') for s in j['steps']]}")
step = steps[0]
state = os.environ.get("STATE", "/tmp/state")
os.makedirs(f"{state}/tmp", exist_ok=True)
env = dict(os.environ)
for src in (wf.get("env") or {}, j.get("env") or {}, step.get("env") or {}):
    # an expression-valued entry is supplied by the caller's environment (stands in for the runner)
    env.update({k: str(v) for k, v in src.items() if not ("${{" in str(v) and k in os.environ)})
genv = f"{state}/github_env"
if os.path.exists(genv):
    for line in open(genv):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            env[k] = v
for item in kv:
    k, v = item.split("=", 1)
    env[k] = v
bad = [k for k, v in env.items() if "${{" in v]
if bad:
    sys.exit(f"unresolved expressions in env: {bad}")
env.update(GITHUB_ENV=genv, GITHUB_OUTPUT=f"{state}/outputs", RUNNER_TEMP=f"{state}/tmp")
script = step["run"]
r = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script], env=env, cwd=env.get("WORKDIR", "."))
sys.exit(r.returncode)
