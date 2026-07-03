# asterisk-wb-checker

Programmatic HD voice (G.722 / AMR-WB 16 kHz) path tester for
Asterisk PBX. Modern equivalent of the PSTN 1004 Hz milliwatt test,
adapted for wideband: a 1 kHz tone proves nothing about HD, so the
probe is a dual tone at 1 kHz + 6 kHz. G.711/AMR-NB paths cut off
around 3.4 kHz; if the 6 kHz component survives the round trip, the
path is genuinely wideband end-to-end. If any hop silently
transcoded to ulaw, the 6 kHz band dies and the check fails.

Verdict is the energy ratio between the 6 kHz and 1 kHz bands in the
recording (self-calibrating against level loss and AGC): ratio above
-20 dB = HD, below = narrowband.

## Install

```
uv sync
uv run wb-checker --help
```

Python 3.11+, numpy only.

## Setup

1. Generate probe files into Asterisk sounds dir:

```
uv run wb-checker generate --out /var/lib/asterisk/sounds
```

2. Include the dialplan and AMI user:

- `asterisk/extensions_hdtest.conf` -> extensions.conf
  (contexts: `play` sends the probe, `record` captures the far
  audio as 16 kHz .wav16, `loopback` self-tests without a trunk)
- `asterisk/manager_hdtest.conf` -> manager.conf (set secret)
- `asterisk/pjsip_hdtest.conf` -> pjsip.conf endpoint templates
  forcing `!all,g722` or `!all,amr-wb` (AMR-WB needs the
  third-party codec_amr module, not in core Asterisk)

```
install -d -o asterisk /var/spool/asterisk/hdtest
asterisk -rx "dialplan reload"
asterisk -rx "manager reload"
```

## Usage

Full cycle (originate, wait for recording, analyze, exit code):

```
uv run wb-checker run \
  --secret AMISECRET \
  --channel "PJSIP/48123456789@testtrunk"
```

The dialed number must answer into something playing the probe
(your own `8000` extension via a peer PBX or a looped trunk).
Exit code: 0 = HD, 1 = narrowband, 2 = error. Cron-friendly.

Pieces individually:

```
uv run wb-checker call --secret S --channel "PJSIP/..."
uv run wb-checker analyze /var/spool/asterisk/hdtest/hdtest-XXX.wav16
```

Quick manual test from Asterisk CLI:

```
asterisk -rx "channel originate Local/loopback@hd-test extension record@hd-test"
```

## Caveats

- Do not trust `${CHANNEL(audionativeformat)}` alone; SDP can say
  G722 while an intermediate hop transcodes. The tone is ground
  truth.
- Record with `.wav16` / `.sln16` only; an 8 kHz recording cannot
  carry the 6 kHz probe (the analyzer rejects it).
- Asterisk built-in TONE_DETECT is telephony-band oriented; offline
  FFT here is more trustworthy at 6 kHz.
- For MOS-like scoring instead of pass/fail, feed the reference and
  the recording to ViSQOL (open source, 16 kHz full-reference).

## Development

```
uv run pytest
uv run ruff check src tests
uv run pylint src/wb_checker
```
