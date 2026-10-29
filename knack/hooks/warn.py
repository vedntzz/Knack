import json
import sys


def main() -> None:
    # Heavy imports sit inside the try, so even an import failure exits 0.
    try:
        from knack.hooks.warn_guard import run_hook

        _print_result(run_hook(sys.stdin.read()))
    except Exception as error:
        print(f"knack guard-error: {type(error).__name__}: {error}", file=sys.stderr)


def _print_result(result: dict[str, object] | None) -> None:
    # Silence injects nothing; print appends the required trailing newline.
    if result is not None:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
