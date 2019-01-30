import os
import subprocess
import sys
import time


def call_with_output(cmd, file=sys.stdout.buffer):
    # Run command printing output in real time
    # https://www.endpoint.com/blog/2015/01/28/getting-realtime-output-using-python
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    while True:
        output = p.stdout.readline()
        if not output and p.poll() is not None:
            break

        if output:
            file.write(output)

    return p.wait(timeout=1)


def wait_for_file(path, timeout=60):
    t = 0
    while t < timeout:
        if os.path.exists(path) and os.path.isfile(path):
            return True

        time.sleep(1)
        t += 1

    return False
