import argparse
import json
from pathlib import Path
from .runner import run_task
from .targets import prepare_targets


def main():
    parser = argparse.ArgumentParser(description="Traceable binder-campaign tasks; no implicit model execution")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-targets")
    prep.add_argument("--config", default="config/targets.json")
    prep.add_argument("--output", default="data/targets")
    run = sub.add_parser("run")
    run.add_argument("spec")
    args = parser.parse_args()
    if args.command == "run":
        print(json.dumps(run_task(args.spec), indent=2))
    else:
        print(json.dumps([{k:v for k,v in r.items() if k != "sequence"} for r in prepare_targets(args.config, args.output)], indent=2))


if __name__ == "__main__":
    main()
