import subprocess
import sys


def call_with_output(cmd, file=sys.stdout):
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
