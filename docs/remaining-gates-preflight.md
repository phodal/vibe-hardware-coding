# Remaining Gates Preflight

`make remaining-gates-preflight` tracks the safe side of the four incomplete goal gates. By default it runs the three gates that do not require physical interaction and records the supervised Web AI tap gate as skipped/manual-required:

- `official-demos`: prints the official ES7210/ES8311 physical-audio plan.
- `xiaozhi-ai`: runs the non-destructive XiaoZhi firmware/source readiness preflight.
- `audio-front-end`: rebuilds and checks the ES7210/VAD preflight artifacts without uploading, playing stimulus, or opening audio devices.
- `web-ai-button`: documents the supervised physical tap gate and skips it unless `--include-manual` is passed.

This target is intentionally not a completion shortcut. It emits `destructive=0 audio=0` and records logs under `.logs/remaining-gates-preflight/`, but the strict goal audit still requires:

- official audio physical evidence during an allowed audio window
- explicit approval before flashing XiaoZhi, followed by runtime plus visual evidence
- supervised Web AI physical tap evidence on the AMOLED
- supervised audio-front-end physical smoke during an allowed audio window

## Commands

```bash
make remaining-gates-list
make remaining-gates-preflight
make remaining-gates-preflight REMAINING_GATES_ARGS=--include-manual
```

## Verified Locally

- `make remaining-gates-list`: lists all 4 remaining gates with `destructive=0 audio=0`, including `web-ai-button manual_required=1`.
- `make remaining-gates-preflight`: passed the 3 non-manual safe gates and recorded `web-ai-button` as `skipped` with `skip_reason=manual-required`.
- Latest safe preflight summary: `/Users/phodal/hardware/arduino/.logs/remaining-gates-preflight/20260615-082900/summary.json` reported `gates=4`, `passed=3`, `skipped=1`, `failed=0`, `destructive=0`, and `audio=0`.
- Latest summary records `official-demos` as plan-only, `xiaozhi-ai` as preflight-only with `release_source=live`, `audio-front-end` as compile/artifact preflight with `audio_devices_used=0 stimulus_played=0 uploaded=0`, and `web-ai-button` as supervised physical tap pending.
