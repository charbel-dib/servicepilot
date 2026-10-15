import argparse
import socket
import threading

import uvicorn

from servicepilot.config import Settings


def main():
    parser = argparse.ArgumentParser(description="ServicePilot support assistant")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Start the UI, API and local fixture status service")
    demo.add_argument("--port", type=int, default=8000)
    serve = commands.add_parser("serve", help="Start only the support API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    status = commands.add_parser("status", help="Start the local fixture status API")
    status.add_argument("--port", type=int, default=8001)
    evaluate = commands.add_parser("evaluate", help="Run the offline behavior suite")
    evaluate.add_argument("--output", default="reports/evaluation.json")
    evaluate.add_argument("--judge", action="store_true", help="Opt-in paid LLM-as-a-judge")
    args = parser.parse_args()
    if args.command == "evaluate":
        from servicepilot.evaluation import run_evaluation

        raise SystemExit(run_evaluation(args.output, judge=args.judge))
    if args.command == "status":
        uvicorn.run("servicepilot.status_api:app", host="127.0.0.1", port=args.port)
        return
    if args.command == "serve":
        uvicorn.run(
            "servicepilot.api:create_app", factory=True, host=args.host, port=args.port, workers=1
        )
        return
    settings = Settings()
    if settings.environment != "demo":
        parser.error("demo command requires SERVICEPILOT_ENVIRONMENT=demo")
    # Reserve an ephemeral local port instead of accidentally querying another service.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    settings.status_url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    status_server = uvicorn.Server(
        uvicorn.Config("servicepilot.status_api:app", log_level="warning")
    )
    thread = threading.Thread(target=status_server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    from servicepilot.api import create_app

    try:
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, workers=1)
    finally:
        status_server.should_exit = True
        thread.join(timeout=5)
        sock.close()


if __name__ == "__main__":
    main()
