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
    
        
    

#参考https://gihyo.jp/admin/serial/01/ubuntu-recipe/0724