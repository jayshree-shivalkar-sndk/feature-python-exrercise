import json
import argparse
import paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed


class AsntHealth:

    def __init__(self, config_file):
        with open(config_file, "r") as f:
            self.testers = json.load(f)["testers"]

    def scan_tester(self, tester_name, timeout):

        cfg = self.testers[tester_name]

        result = {
            "tester": tester_name,
            "status": "OFFLINE"
        }

        try:

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(
                paramiko.AutoAddPolicy()
            )

            ssh.connect(
                hostname=cfg["ip_address"],
                port=int(cfg["port"]),
                username=cfg["username"],
                password=cfg["password"],
                timeout=timeout
            )

            commands = {
                "hostname": "hostname",
                "os": "lsb_release -ds",
                "uptime": "uptime -p",
                "memory": "free -h | awk '/Mem:/ {print $3\"/\"$2}'",
                "disk": "df -h / | awk 'NR==2 {print $5}'"
            }

            for key, cmd in commands.items():

                stdin, stdout, stderr = ssh.exec_command(cmd)

                result[key] = (
                    stdout.read()
                    .decode()
                    .strip()
                )

            result["status"] = "ONLINE"

            ssh.close()

        except Exception as e:

            result["error"] = str(e)

        return result

    def run(self, selected_testers, timeout):

        results = []

        with ThreadPoolExecutor(
            max_workers=len(selected_testers)
        ) as executor:

            futures = {

                executor.submit(
                    self.scan_tester,
                    tester,
                    timeout
                ): tester

                for tester in selected_testers
            }

            for future in as_completed(futures):
                results.append(
                    future.result()
                )

        return results


def main():

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(
        dest="command"
    )

    scan = subparsers.add_parser("scan")

    scan.add_argument(
        "--testers",
        help="Comma separated tester names"
    )

    scan.add_argument(
        "--all",
        action="store_true"
    )

    scan.add_argument(
        "--timeout",
        type=int,
        default=10
    )

    args = parser.parse_args()

    manager = AsntHealth(
        "testers_config.json"
    )

    if args.all:

        selected = list(
            manager.testers.keys()
        )

    elif args.testers:

        selected = [

            t.strip()

            for t in args.testers.split(",")

            if t.strip() in manager.testers

        ]

    else:

        parser.error(
            "Specify --all or --testers"
        )

    results = manager.run(
        selected,
        args.timeout
    )

    print("\nTester Health Summary")
    print("=" * 80)

    for r in results:

        print(f"\nTester : {r['tester']}")
        print(f"Status : {r['status']}")

        if r["status"] == "ONLINE":

            print(f"Host    : {r['hostname']}")
            print(f"OS      : {r['os']}")
            print(f"Uptime  : {r['uptime']}")
            print(f"Memory  : {r['memory']}")
            print(f"Disk    : {r['disk']}")

        else:

            print(
                f"Error   : "
                f"{r.get('error', '')}"
            )


if __name__ == "__main__":
    main()