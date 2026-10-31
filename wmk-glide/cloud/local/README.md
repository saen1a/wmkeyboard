# Local backends runbook (RX 9060 XT, WSL Ubuntu 24.04)

What the four scripts do, how to invoke them, and what was measured.

## Backends, status

| Backend | Role | Status | Source |
|---|---|---|---|
| **ROCm / WSL** | primary training backend | works; **1.32 steps/s** single-run (batch 256, d256/6/4/768/ctx 40, with distill, 2026-10-28); **1.03 steps/s** while two other trainers shared the box (2026-10-31, same shape) | `~/wmlm-de/out/student.log`; `wmk-glide/plans/teacher-free-results.md` §6 |
| **DirectML** | second training backend / probe | **works with `distill_impl=index`**: 2 000 steps at **1.04 steps/s**, batch 64, loss curve identical to CPU. `distill_impl=gather` still crashes (`DirectML scatter doesn't allow partially modified dimensions`); `onehot` fails (`aten::eye` unsupported) | measured 2026-10-31: `directml_probe.py`, `run_dml_gate.log`; `teacher-free-results.md` §5 |
| **ONNX Runtime DirectML** | inference-only EP | docs explicitly say "accelerates inference of ONNX models"; training build exposes kernels only for CPU and CUDA | <https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html> |
| **CPU (Ubuntu 26.04 venv)** | verification / convergence gate | works: **0.66 steps/s** at batch 64 measured 2026-10-31 (1.52 s/step); an older single-run figure was 0.52 s/step | `teacher-free-results.md` §6; `wmlm-training-windows.md` §3.1 |

**DirectML is now a real (second) training path, not inference-only.** The
historical crash is a platform limit of `torch.gather`, not of the loss:
`logits.reshape(-1,V)[row, id]` and `torch.take_along_dim` both pass backward
on DirectML 0.2.5.dev240914. `train.py` selects it with `device=dml` and
**must** be combined with `distill_impl=index`.

`dml_env.ps1` is the only place that installs torch-directml; it uses a venv
outside the repo and outside `/opt/wmlm-venv`.

## Files

| File | One-line |
|---|---|
| `bench_steps.py` | honest training-throughput probe (warmup + timed steps, JSON). Imports `tools/wmlm/train.py`, does not copy model code |
| `directml_probe.py` | reproduces the gather-backward crash and tries three scatter-free alternatives; CPU is the reference profile |
| `dml_env.ps1` | creates a SEPARATE `.venv-dml` in a temp dir (`$env:TEMP\wmkl-dml-venv`), installs `torch-directml==0.2.5.dev240914` + `torch==2.4.1`, then runs `directml_probe.py`. Never touches `/opt/wmlm-venv` |
| `run_rocm.sh` | WSL Ubuntu 24.04 wrapper: exports the ROCm 7.2.1 env, precondition-checks `torch.cuda.is_available()` + device name, then runs `bench_steps.py` or `train.py` (`MODE=bench|train`) |
| `cpu_gate.sh` | 2 000-step CPU convergence gate on Ubuntu 26.04's CPU venv: asserts `device cpu` in the log, no `nan`/`inf`, and that the running *training* loss at the last step is below its first value (heldout ppl rises on a small slice and is printed as a diagnostic) |

## One-line commands

### ROCm (training backend, WSL Ubuntu 24.04)

All commands use `ART=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out`
(the artifacts live under `wmk-glide/`, not at the repo root).

```bash
# precondition
wsl -d Ubuntu-24.04 -- bash -lc '/opt/wmlm-venv/bin/python -c "import torch;print(torch.__version__,torch.cuda.is_available(),torch.cuda.get_device_name(0))"'
# bench (ART must be expanded by the caller; run_rocm.sh takes key=value args)
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/g/C0ding/git/wmkeyboard-wmlm && ART=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out bash wmk-glide/cloud/local/run_rocm.sh MODE=bench data=$ART/de_lm_2m_slice10k distill=$ART/de_lm_2m_slice10k/soft.npz mask=$ART/de_lm_2m_slice10k/masks.keep.kd.npz weight=$ART/de_lm_2m_slice10k/masks.masks.npz steps=200 batch=256 out=/tmp/bench'
# long train (do not start unattended from this stage — caller decides)
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/g/C0ding/git/wmkeyboard-wmlm && ART=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out bash wmk-glide/cloud/local/run_rocm.sh MODE=train data=$ART/de_lm_2m distill=$ART/de_soft_2m.npz steps=1000 batch=256 out=/tmp/train'
```

### CPU (verification backend, Ubuntu 26.04)

```bash
# gate (bash, not python: cpu_gate.sh is a shell script)
wsl -d Ubuntu-26.04 -- bash -lc 'cd /mnt/g/C0ding/git/wmkeyboard-wmlm && bash wmk-glide/cloud/local/cpu_gate.sh wmk-glide/artifacts/out/de_lm_2m_slice10k /tmp/cpu-gate'
# fast CPython reference for directml_probe
wsl -d Ubuntu-26.04 -- bash -lc 'cd /mnt/g/C0ding/git/wmkeyboard-wmlm && /home/saenta/wmlm-de/.venv-distill/bin/python wmk-glide/cloud/local/directml_probe.py --device cpu --batch 4 --ctx 16'
# end-to-end bench_steps smoke (synthetic data, tiny model)
wsl -d Ubuntu-26.04 -- bash -lc 'cd /mnt/g/C0ding/git/wmkeyboard-wmlm && /home/saenta/wmlm-de/.venv-distill/bin/python wmk-glide/cloud/local/bench_steps.py --data <synth> --steps 5 --warmup 2 --batch 4 --ctx 12 --d 32 --layers 1 --heads 4 --ff 64'
```

### DirectML probe (CPU reference; Windows-direct path needs `dml_env.ps1`)

```powershell
# CPU reference (PowerShell or WSL)
python wmk-glide/cloud/local/directml_probe.py --device cpu --batch 4 --ctx 16
# Windows-native DML env (creates .venv-dml in %TEMP%, separate from the repo)
powershell -ExecutionPolicy Bypass -File wmk-glide\cloud\local\dml_env.ps1
```

## Numbers with their source (no re-research here)

- **GPU 1.32 steps/s at batch 256 with distill**: `research-notes.md` §0
  table (`30 000 steps, batch 256, d256/6/768/ctx40 with distill: 22 708 s →
  1.32 steps/s`). Same row gives `torch.cuda.is_available()==True`, GPU
  is `gfx1200`, stack is WSL Ubuntu 24.04 + ROCm 7.2.1 + torch 2.9.1.
- **CPU 0.52 s/step (1.92 steps/s) at batch 64**: `wmlm-training-plan.md:108`
  (`100 steps, batch 64: 52 s`). This session measured **0.66 steps/s**
  (1.52 s/step) at batch 64 on the same 16-vCPU WSL box while two other
  trainers shared it — see `teacher-free-results.md` §6.
- **CPU gate criterion**: `cpu_gate.sh` asserts the running *training* loss
  falls and no `nan`/`inf` appears. Heldout ppl rises on a small slice by
  design and is printed as a diagnostic only.
- **DirectML crash string**: `cloud/scaleway/NEXT-SESSION-TEACHER-FREE.md:74-78`
  (`DirectML scatter doesn't allow partially modified dimensions`, line 77).
- **DirectML operator gap**: `microsoft/DirectML#420` (closed not planned);
  PyTorch operator roadmap (gather/scatter_backward / take_along_dim /
  one_hot not listed).
- **ONNX Runtime DML EP was inference-only**: docs link above.

## Hard rules (binding)

- No commit / no push from this stage.
- `dml_env.ps1` is the ONLY thing allowed to install torch-directml, in a
  venv OUTSIDE the repo and OUTSIDE `/opt/wmlm-venv`.
- `bench_steps.py` MUST NOT save checkpoints; it allocates the model and
  runs `train.WordLm.eval()`-equivalent forward/backward without writing.
