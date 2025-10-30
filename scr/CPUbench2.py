#!/usr/bin/env python3

import datetime
import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import typing

import requests


def monitoring(
    queue: "multiprocessing.Queue[list[typing.Any]]",
    event: threading.Event,
    cpunum: int,
    epoch: datetime.datetime,
):
    data = []
    while not event.is_set():
        datum: dict[str, typing.Any] = {"time": 0, "cpu": {}, "sensor": {}}

        #glances(linux機能から取得)
        datum["time"] = (datetime.datetime.now() - epoch).seconds
        percpu = requests.get("http://localhost:61208/api/3/percpu")
        sensors = requests.get("http://localhost:61208/api/3/sensors")

        #sysfsから取得
        freq = {}
        if os.access("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", os.R_OK):
            for i in range(cpunum):
                with open(
                    "/sys/devices/system/cpu/cpu{0}/cpufreq/scaling_cur_freq".format(i)
                ) as f:
                    freq[i] = int(f.readline())

         #procfsから取得
        hz = {}
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read().split("\n\n")
            for cpu, info in enumerate(cpuinfo):
                for line in info.split("\n"):
                    if "cpu MHz" in line:
                        hz[cpu] = float(line.split(":")[1].strip())

        # 取得したデータを整理する
        for stat in percpu.json():
            cpu = int(stat["cpu_number"])
            datum["cpu"][cpu] = {
                "usage": int(stat["total"]),
                "freq": freq[cpu],
                "hz": hz[cpu],
            }
        for stat in sensors.json():
            datum["sensor"][stat["label"]] = stat["value"]
        data.append(datum)
        time.sleep(1)

    queue.put(data)


def parse_smp_cores():
    pattern = re.compile(
        r"processor\s+:\s+(?P<logi>\d+)|physical id\s+:\s+(?P<phys>\d+)|core id\s+:\s+(?P<core>\d+)"
    )
    cores = {}
    with open("/proc/cpuinfo") as f:
        cpuinfo = f.read().split("\n\n")
        for block in cpuinfo:
            if len(block) == 0:
                continue
            coreinfo = {}
            for m in re.finditer(pattern, block):
                coreinfo.update({k: int(v) for k, v in m.groupdict().items() if v})
           # CPUパッケージあたりの最大コアIDが2^16以下であるという前提で。
            key = str(coreinfo["phys"] << 16 | coreinfo["core"])
            if key not in cores:
                cores[key] = []
            cores[key].append(coreinfo["logi"])

    return cores


def bench_7z(
    queue: "multiprocessing.Queue[dict[str, typing.Any]]",
    cpu: int,
    epoch: datetime.datetime,
):
    comm = shutil.which("7z") or sys.exit("needs 7z command")
    os.sched_setaffinity(0, {cpu})
    result = subprocess.run([comm, "b", "-mmt1"], stdout=subprocess.PIPE)
    if result.returncode != 0:
        sys.exit("failed to {0} on cpu {1}".format(comm, cpu))
    end = (datetime.datetime.now() - epoch).seconds
    data = []
    for line in result.stdout.decode("utf-8").splitlines():
        if line.startswith("Tot:"):
            data = line.split()
            break
    queue.put(
        {
            "end": end,
            "result": (int(data[2]) + int(data[3])) / 2,
        }
    )


if __name__ == "__main__":
    #glancesをdaemonで起動
    glances = shutil.which("glances") or sys.exit("needs glances command")
    daemon = subprocess.Popen(
        [glances, "-w", "--disable-webui"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        pipesize=0,
    )
    os.sched_setaffinity(daemon.pid, {1})

    # サーバーの起動待機中
    time.sleep(3)

    # CPU情報取得する。
    result = requests.get("http://localhost:61208/api/3/quicklook")
    cpuname = result.json()["cpu_name"]
    cpunum = len(os.sched_getaffinity(0))
    data = {"cpunum": cpunum, "name": cpuname, "system": " ".join(os.uname())}

    # 準備時間エポック
    os.sched_setaffinity(0, {1})
    epoch = datetime.datetime.now()

    #　モニター開始
    queue = multiprocessing.Queue()
    event = multiprocessing.Event()
    monitor = multiprocessing.Process(
        target=monitoring,
        args=(
            queue,
            event,
            cpunum,
            epoch,
        ),
        daemon=True,
    )
    monitor.start()
    if not monitor.pid:
        sys.exit("failed to start monitor process")
    os.sched_setaffinity(monitor.pid, {1})

    #ベンチマーク処理開始
    do_bench = bench_7z
    data["benchmark"] = []
    start = (datetime.datetime.now() - epoch).seconds
    reset = {
        "time": (datetime.datetime.now() - epoch).seconds,
        "cpu": dict.fromkeys(range(cpunum), {"end": 0, "result": 0}),
    }
    data["benchmark"].append(reset)
    time.sleep(3)
    patterns = [(x,) for x in range(cpunum)]  # single core
    patterns = [(x,) for x in range(cpunum)]  # single core
    patterns.extend([tuple(v) for _, v in parse_smp_cores().items()])  # 同時マルチスレッティング
    patterns.append(tuple([x for x in range(0, cpunum, 2)]))  # マルチスレッド無しの偶数コア、マルチスレッドなしならコアにかかわらず
    patterns.append(tuple([x for x in range(1, cpunum, 2)]))  #　マルチスレッドなしの奇数コア、マルチスレッド無しならコアにかかわらず
    patterns.append(tuple([x for x in range(cpunum)]))  # 全コア
    for pattern in patterns:
        print("Start benchmark on CPU", end=" ", file=sys.stderr)
        start = (datetime.datetime.now() - epoch).seconds
        benchmark_result: list[dict[str, typing.Any]] = [{"time": start, "cpu": {}}]
        bench = {}
        for i in pattern:
            print("{}".format(i), end=" ", file=sys.stderr)
            bench[i] = {}
            bench[i]["queue"] = multiprocessing.Queue()
            bench[i]["proc"] = multiprocessing.Process(
                target=do_bench,
                args=(
                    bench[i]["queue"],
                    i,
                    epoch,
                ),
            )
            bench[i]["proc"].start()
            if not bench[i]["proc"].pid:
                sys.exit("failed to start benchmark process")
        print(file=sys.stderr)
        for i in pattern:
            bench[i]["proc"].join()
            if bench[i]["proc"].exitcode != 0:
                sys.exit("failed benchmark process")
            result = bench[i]["queue"].get()
            benchmark_result[0]["cpu"][i] = result
            end = {"time": result["end"], "cpu": {}}
            end["cpu"][i] = result
            benchmark_result.append(end)
        data["benchmark"].extend(benchmark_result)
        reset = {
            "time": (datetime.datetime.now() - epoch).seconds,
            "cpu": dict.fromkeys(range(cpunum), {"end": 0, "result": 0}),
        }
        data["benchmark"].append(reset.copy())
        time.sleep(30)
        reset["time"] = (datetime.datetime.now() - epoch).seconds
        data["benchmark"].append(reset)

    # 取得したデータを出力する
    event.set()
    data["monitoring"] = queue.get()
    print(json.dumps(data))

    # モニタースレッドとグラスデーモンを纏める
    event.set()
    monitor.join()
    daemon.terminate()

#参考https://gihyo.jp/admin/serial/01/ubuntu-recipe/0724