import sys

from .app import main

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "say":
        # quick test without the UI:  python -m sema say "text to read"
        import threading

        from .config import Config
        from .engine import Engine

        done = threading.Event()
        eng = Engine(Config(), on_event=lambda e: (print(e), done.set() if e["type"] in ("finished", "error") else None))
        eng.speak(" ".join(sys.argv[2:]) or sys.stdin.read())
        done.wait()
    else:
        main()
