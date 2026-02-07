"""Single entry point for wsj-triage commands."""
import argparse
import sys


def cmd_triage(args):
    from src.triage import main
    main()


def cmd_serve(args):
    from src.server import app
    app.run(host="127.0.0.1", port=args.port, debug=True)


def cmd_synthesis(args):
    from src.synthesis import main
    main(days=args.days)


parser = argparse.ArgumentParser(prog="wsj-triage", description="WSJ Signal Triage System")
sub = parser.add_subparsers(dest="command", required=True)

sub.add_parser("triage", help="Fetch RSS, score articles, generate dashboard")

serve_p = sub.add_parser("serve", help="Start local Flask server for analysis workflow")
serve_p.add_argument("--port", type=int, default=5050, help="Port (default: 5050)")

synth_p = sub.add_parser("synthesis", help="Generate weekly memo from analysis log")
synth_p.add_argument("--days", type=int, default=7, help="Analysis window in days (default: 7)")

COMMANDS = {"triage": cmd_triage, "serve": cmd_serve, "synthesis": cmd_synthesis}

if __name__ == "__main__":
    args = parser.parse_args()
    COMMANDS[args.command](args)
