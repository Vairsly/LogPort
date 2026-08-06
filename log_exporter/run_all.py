import signal
import subprocess
import sys
import time


COMMANDS = {
    "worker": [sys.executable, "-m", "log_exporter.worker"],
    "web": [
        "gunicorn",
        "--bind",
        "0.0.0.0:9090",
        "--workers",
        "2",
        "--access-logfile",
        "-",
        "log_server:app",
    ],
}


def stop_processes(processes):
    for process in processes.values():
        if process.poll() is None:
            process.terminate()

    for process in processes.values():
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    processes = {
        name: subprocess.Popen(command)
        for name, command in COMMANDS.items()
    }

    try:
        while not stopping:
            for name, process in processes.items():
                return_code = process.poll()
                if return_code is not None:
                    print(f"{name} exited with status {return_code}", file=sys.stderr, flush=True)
                    return return_code or 1
            time.sleep(0.5)
        return 0
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
