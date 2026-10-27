import json
import paramiko
from concurrent.futures import ThreadPoolExecutor, as_completed


class MultiTesterManager:

    def __init__(self, config_file):

        with open(config_file, "r") as f:
            self.testers = json.load(f)["testers"]

    def connect_and_execute(self, tester_name, command):

        cfg = self.testers[tester_name]

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
                timeout=10
            )

            stdin, stdout, stderr = ssh.exec_command(command)

            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            ssh.close()

            return {
                "tester": tester_name,
                "status": "SUCCESS",
                "output": output,
                "error": error
            }

        except Exception as e:

            return {
                "tester": tester_name,
                "status": "FAILED",
                "output": "",
                "error": str(e)
            }

    def execute_on_multiple_testers(self, selected_testers, command):

        results = []

        with ThreadPoolExecutor(
            max_workers=len(selected_testers)
        ) as executor:

            futures = {

                executor.submit(
                    self.connect_and_execute,
                    tester,
                    command
                ): tester

                for tester in selected_testers
            }

            for future in as_completed(futures):
                results.append(
                    future.result()
                )

        return results


if __name__ == "__main__":

    manager = MultiTesterManager(
        "testers_config.json"
    )

    print("\nAvailable Testers:")

    for tester in manager.testers:
        print("-", tester)

    user_input = input(
        "\nEnter testers (comma separated): "
    )

    selected_testers = [
        x.strip()
        for x in user_input.split(",")
        if x.strip() in manager.testers
    ]

    command = input(
        "\nEnter command to execute: "
    )

    results = manager.execute_on_multiple_testers(
        selected_testers,
        command
    )

    print("\n" + "=" * 80)
    print("EXECUTION SUMMARY")
    print("=" * 80)

    for result in results:

        print(f"\nTester : {result['tester']}")
        print(f"Status : {result['status']}")

        if result["output"]:
            print("\nOUTPUT:")
            print(result["output"])

        if result["error"]:
            print("\nERROR:")
            print(result["error"])