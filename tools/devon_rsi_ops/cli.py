"""Operator-only offline evidence importer. No signer, model, network or promotion."""

import argparse
import sqlite3

from tools.devon_rsi.kernel import Refused, canonical, read_json

from .store import Store, safe_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["register", "assess", "review", "snapshot", "meta"])
    parser.add_argument("--state", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--keys", help="Operator-controlled registry, never supplied by candidate")
    parser.add_argument("--trust-sha256")
    parser.add_argument("--output")
    args = parser.parse_args()
    store = None
    try:
        if args.command == "meta":
            from .meta import compare
            if not args.output or not args.trust_sha256:
                raise Refused("META_ARGUMENTS")
            result = compare(safe_path(args.output), args.trust_sha256)
            print(canonical({k: v for k, v in result.items() if k != "strategies"}).decode())
            return
        store = Store(safe_path(args.state) / "operator.sqlite3")
        if args.command == "snapshot":
            result = store.snapshot()
        else:
            from . import registry
            if not args.evidence or not args.keys:
                raise Refused("EXTERNAL_EVIDENCE_REQUIRED")
            root = safe_path(args.evidence)
            keys_path = safe_path(args.keys)
            if keys_path == root or root in keys_path.parents:
                raise Refused("REGISTRY_MUST_BE_SEPARATE")
            keys = read_json(keys_path)
            protocol, freeze = [read_json(safe_path(root / name)) for name in ("protocol.json", "freeze.json")]
            if args.command == "register":
                result = registry.register(store, protocol, freeze, keys)
            else:
                paths = []
                for index, path in enumerate((root / "trials").iterdir()):
                    if index >= 256 or path.suffix != ".json":
                        raise Refused("TRIAL_FILES")
                    paths.append(safe_path(path))
                trials = [read_json(path) for path in sorted(paths)]
                if args.command == "assess":
                    result = registry.assess(store, protocol, freeze, trials, keys)
                else:
                    result = registry.review(store, protocol, freeze, trials,
                                             read_json(safe_path(root / "review.json")), keys)
        print(canonical(result).decode())
        if result.get("state") in {"HOLD", "REJECT"}:
            raise SystemExit(2)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print('{"state":"HOLD","reason":"FAIL_CLOSED","gain_claim":false,"promoted":false}')
        raise SystemExit(2) from None
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    main()
