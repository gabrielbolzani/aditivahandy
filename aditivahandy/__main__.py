import argparse
import os

from .engine import Engine
from .web import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="AditivaHandy, sem interface gráfica")
    parser.add_argument("--host", default=os.environ.get("HANDY_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HANDY_PORT", "8787")))
    args = parser.parse_args()
    engine = Engine()
    engine.start()
    serve(engine, args.host, args.port)


if __name__ == "__main__":
    main()
