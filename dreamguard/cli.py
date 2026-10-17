"""Command line: `dreamguard serve` | `dreamguard benchmark [--auto]`."""
import argparse
import sys


def main(argv=None):
    p = argparse.ArgumentParser(prog="dreamguard", description="Reversible memory compilation for AI agents")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the dashboard + API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    b = sub.add_parser("benchmark", help="run the offline simulation")
    b.add_argument("--auto", action="store_true", help="auto-rollback instead of manual at turn 40")
    args = p.parse_args(argv)

    if args.cmd == "serve":
        try:
            import uvicorn
            from .api import app
        except ImportError:
            sys.exit('Server extras missing. Install with: pip install "dreamguard[server]"')
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        from .benchmark import run_benchmark
        res = run_benchmark(auto_rollback=args.auto, rollback_at=None if args.auto else 40)
        print(f"{'turn':>4} {'raw':>6} {'in_place':>9} {'dreamguard':>11}")
        for r in res["rows"]:
            if r["turn"] % 5 == 0:
                print(f"{r['turn']:>4} {r['raw_acc']:>5}% {r['in_place_acc']:>8}% {r['dreamguard_acc']:>10}%")
        print("events:", res["events"])


if __name__ == "__main__":
    main()
