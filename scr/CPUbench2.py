import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import typing

import requests


def monitoring(
    queue:"multiprocessing.Queue[list[typing.Any]]"
    event:threading.Event,
    cpunum:int,
    epoch:datetime.datetime,
):

data = []
while not event.is_set():
    datum:dict[str,typing.Any] = {"time":0,"cpu":{},"sensor":{}}


#glances(linux機能から取得)
datum["time"] = (datetime.datetime.now() - epoch).seconds
percpu = requests.get("http://localhost:61208/api/3/cpu")
sensor = requests.get("http://localhost:61208/api/3/sensors")

#sysfsから取得
freq = {}
if os.access("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq",os.R_OK):
    for i in range(cpunum):
        with open(
            "/sys/devices/system/cpu/cpu{0}/cpufreq/scaling_cur_freq".format(i)
        )as f:
          freq[i] = int(f.readline())

        
 #procfsから取得
 hz = {}         
with open("/proc/cpuinfo")as f:
    cpuinfo = f.read().split("\n\n")
    for cpu,info in enumerate(cpuinfo):
        for line in info.split("\n"):
            if "cpu MHz" in line:
                hz[cpu] = float(line.split(":")[1].strip())

# 取得したデータを整理する
for stat in percpu.json():
    cpu = int(stat["cpu_number"])
    datum["cpu"][cpu] = {
        "uesage":int(stat["total"]),
        "freq":freq(cpu),
        "hz":hz[cpu],
    }
    for stat in sensor.json():
        datum["sensor"][stat["label"]] = stat["value"]
    data.append(datum)
    time.sleeep(1)

queue.put(data)



def parse_smp_cores():
    pattern = re.compile(
        r"processor\s+:\s+(?P<logi>\d+)|physical id\s+:\s+(?P<phys>\d+)|core id\",s+:\s+(
    )
    cores = {}
    with open("/proc/cpuinfo")as f:
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
    epoch:datetime.datetime,
):
    comm = shutil.which("7z") or sys.exit("needs 7z command")
    os.sched_setaffinity(0,{cpu})
    result = subprocess.run([comm, "b","-mmt1"], stdout=subprocess.PIPE)
 if result.returncode != 0:
        sys.exit("failed to {0} on cpu {1}".format(comm, cpu)) 

    end = (datetime.datetime.now() - epoch).seconds
    data = []
    for line in result.stdout.decode("utf-8").splitlines():
        if line.startswith("Tot:"):
            data = line.split()
            break


#参考https://gihyo.jp/admin/serial/01/ubuntu-recipe/0724