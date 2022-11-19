import math
import random
import subprocess
import sys
import time

from gator.logger import Logger

# Read argument
tgt = int(sys.argv[1]) if len(sys.argv) > 1 else 10

# Log at each level
Logger.debug("This is a debug message")
Logger.info("This is an info message")
Logger.warning("This is a warning message")
Logger.error("This is an error message")

# Use STDOUT and STDERR
print("This is STDOUT")
print("This is STDERR", file=sys.stderr)

# Wait a little
time.sleep(2)

# Launch a bunch of subprocesses
procs = []
for idx in range(tgt):
    print(f"Launching {idx+1}")
    procs.append(subprocess.Popen(["sleep", f"{idx+1}"]))

# Wait for subprocesses to complete
for idx, proc in enumerate(procs):
    proc.wait()
    print(f"Finished {idx+1}")

# Calculation
print("Running high intensity calculation")
result = 0
for idx in range(1000000):
    a = math.sqrt(random.randint(1, 1000000))
    b = math.pow(a, (idx % 10))
    c = a / b
    d = math.log2(c)
    result += d
print(f"Result: {result}")

# Wait a little
time.sleep(2)
