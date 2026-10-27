from flask import Flask, render_template, jsonify
from concurrent.futures import ThreadPoolExecutor
import paramiko
import json

app = Flask(__name__)

with open("testers_config.json") as f:
    TESTERS = json.load(f)


def get_tester_info(name, cfg):

    info = {
        "name": name,
        "ip": cfg["hostname"],
        "status": "Offline"
    }

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        ssh.connect(
            hostname=cfg["hostname"],
            username=cfg["username"],
            password=cfg["password"]
        )

        cmds = {
            "ubuntu":
                "lsb_release -rs",

            "memory":
                "free -m | awk '/Mem:/ {print $3\"/\"$2\" MB\"}'",

            "cpu":
                "top -bn1 | grep Cpu",

            "disk":
                "df -h / | tail -1 | awk '{print $5}'",

            "release":
                "ls -dt /home/ubuntu/release/AstraNT_Firmware_* 2>/dev/null | head -1",

            "linux_Kernel_version":
                "uname -r | uname -v"
        }

        for key, cmd in cmds.items():
            stdin, stdout, stderr = ssh.exec_command(cmd)
            info[key] = stdout.read().decode().strip()

        info["status"] = "Online"

        ssh.close()

    except:
        pass

    return info


@app.route("/api/testers")
def testers():

    result = []

    with ThreadPoolExecutor(max_workers=20) as ex:

        futures = [
            ex.submit(
                get_tester_info,
                name,
                cfg
            )
            for name, cfg in TESTERS.items()
        ]

        for f in futures:
            result.append(f.result())

    return jsonify(result)


@app.route("/")
def home():
    return render_template("dashboard.html")

app.run(host="0.0.0.0", port=5000)