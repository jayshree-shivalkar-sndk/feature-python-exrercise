from flask import Flask, render_template, jsonify, request
import json
import paramiko
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__)

CONFIG_FILE = "testers_config.json"

with open(CONFIG_FILE, "r") as f:
    TESTERS = json.load(f)["testers"]

def execute_command(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    return stdout.read().decode().strip()

def get_tester_info(name):

    cfg = TESTERS[name]

    result = {
        "name": name,
        "ip": cfg["ip_address"],
        "status": "Offline"
    }

    try:

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        ssh.connect(
            cfg["ip_address"],
            username=cfg["username"],
            password=cfg["password"],
            port=int(cfg["port"]),
            timeout=5
        )

        result["hostname"] = execute_command(
            ssh, "hostname"
        )

        result["os"] = execute_command(
            ssh,
            "lsb_release -ds"
        )

        result["uptime"] = execute_command(
            ssh,
            "uptime -p"
        )

        result["memory"] = execute_command(
            ssh,
            "free -h | awk '/Mem:/ {print $3\" / \"$2}'"
        )

        result["disk"] = execute_command(
            ssh,
            "df -h / | awk 'NR==2 {print $5}'"
        )

        result["cpu"] = execute_command(
            ssh,
            "top -bn1 | grep Cpu | awk '{print $2}'"
        )

        result["last_login"] = execute_command(
            ssh,
            "last -n 1"
        )

        result["status"] = "Online"

        ssh.close()

    except Exception as e:
        result["error"] = str(e)

    return result


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/testers")
def get_testers():

    results = []

    with ThreadPoolExecutor(max_workers=20) as ex:

        futures = []

        for name in TESTERS:
            futures.append(
                ex.submit(
                    get_tester_info,
                    name
                )
            )

        for f in futures:
            results.append(f.result())

    return jsonify(results)


@app.route("/api/tester/<tester_name>")
def tester_details(tester_name):
    return jsonify(
        get_tester_info(tester_name)
    )


@app.route("/connect", methods=["POST"])
def connect_testers():

    selected = request.json["testers"]

    results = []

    with ThreadPoolExecutor(max_workers=20) as ex:

        futures = []

        for tester in selected:
            futures.append(
                ex.submit(
                    get_tester_info,
                    tester
                )
            )

        for f in futures:
            results.append(f.result())

    return jsonify(results)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )