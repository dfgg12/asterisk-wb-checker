"""Command-line interface: generate, analyze, call, run."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from wb_checker.analyze import HD_THRESHOLD_DB, analyze
from wb_checker.originate import AmiConfig, originate_test_call
from wb_checker.tonegen import ToneSpec, generate

LOG = logging.getLogger(__name__)
SOUNDS_DIR = Path("/var/lib/asterisk/sounds")
REC_DIR = Path("/var/spool/asterisk/hdtest")


def _recordings(rec_dir: Path) -> set[Path]:
    """Return recording formats supported by the analyzer."""
    if not rec_dir.is_dir():
        return set()
    return set(rec_dir.glob("*.wav")) | set(rec_dir.glob("*.wav16"))


def cmd_generate(args: argparse.Namespace) -> int:
    """Write probe tone files."""
    spec = ToneSpec(duration_s=args.duration)
    paths = generate(Path(args.out), spec=spec)
    for p in paths:
        print(f"ok {p}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze one recording, exit 0 if HD, 1 if narrowband."""
    verdict = analyze(Path(args.file), threshold_db=args.threshold)
    print(verdict.summary())
    return 0 if verdict.is_hd else 1


def cmd_call(args: argparse.Namespace) -> int:
    """Originate a test call via AMI."""
    cfg = AmiConfig(host=args.host, port=args.port,
                    username=args.username, secret=args.secret)
    originate_test_call(cfg, args.channel, context=args.context,
                        exten=args.exten)
    print("ok call originated")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Full cycle: call, wait, analyze newest recording."""
    rec_dir = Path(args.rec_dir)
    before = _recordings(rec_dir)
    rc = cmd_call(args)
    if rc != 0:
        return rc
    deadline = time.monotonic() + args.wait
    new: list[Path] = []
    while time.monotonic() < deadline:
        time.sleep(2)
        new = sorted(_recordings(rec_dir) - before)
        if new:
            break
    if not new:
        print(f"FAIL no recording appeared in {rec_dir}")
        return 2
    time.sleep(2)  # let Record() finish writing
    verdict = analyze(new[-1], threshold_db=args.threshold)
    print(verdict.summary())
    return 0 if verdict.is_hd else 1


def _add_ami_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5038)
    p.add_argument("--username", default="wbchecker")
    p.add_argument("--secret", required=True)
    p.add_argument("--channel", required=True,
                   help="e.g. PJSIP/48123456789@testtrunk")
    p.add_argument("--context", default="hd-test")
    p.add_argument("--exten", default="record")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="wb-checker",
        description="Test G.722 / AMR-WB HD voice paths on Asterisk")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write probe tone files")
    g.add_argument("--out", default=str(SOUNDS_DIR))
    g.add_argument("--duration", type=float, default=5.0)
    g.set_defaults(func=cmd_generate)

    a = sub.add_parser("analyze", help="analyze a recording")
    a.add_argument("file")
    a.add_argument("--threshold", type=float,
                   default=HD_THRESHOLD_DB)
    a.set_defaults(func=cmd_analyze)

    c = sub.add_parser("call", help="originate test call via AMI")
    _add_ami_args(c)
    c.set_defaults(func=cmd_call)

    r = sub.add_parser("run", help="call + wait + analyze")
    _add_ami_args(r)
    r.add_argument("--rec-dir", default=str(REC_DIR))
    r.add_argument("--wait", type=float, default=60.0,
                   help="seconds to wait for the recording")
    r.add_argument("--threshold", type=float,
                   default=HD_THRESHOLD_DB)
    r.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
