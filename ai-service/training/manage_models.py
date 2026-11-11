import argparse
import json
from corecare import registry, storage


def main():
    parser = argparse.ArgumentParser(description="Explicit model review, promotion and rollback.")
    parser.add_argument("action", choices=["list", "approve", "rollback"])
    parser.add_argument("--component", choices=["delay", "workload"])
    parser.add_argument("--version")
    parser.add_argument("--reviewer")
    parser.add_argument("--reason")
    parser.add_argument("--allow-experimental", action="store_true")
    parser.add_argument("--confirm", help="Must be APPROVE or ROLLBACK for a mutation.")
    args = parser.parse_args()
    storage.initialize()
    if args.action == "list":
        print(json.dumps(registry.catalog(), indent=2))
        return
    if not args.component or not args.reviewer or not args.reason:
        parser.error("component, reviewer and reason are required")
    if args.action == "approve":
        if not args.version or args.confirm != "APPROVE":
            parser.error("--version and --confirm APPROVE are required")
        registry.promote(args.component, args.version, args.reviewer, args.reason, allow_experimental=args.allow_experimental)
    else:
        if args.confirm != "ROLLBACK":
            parser.error("--confirm ROLLBACK is required")
        registry.rollback(args.component, args.reviewer, args.reason)
    print(json.dumps({"component": args.component, "active": registry.active_version(args.component)}))


if __name__ == "__main__":
    main()
