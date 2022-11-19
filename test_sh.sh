#!/bin/bash

# Arguments
tgt=${1:-10}

# Use directive logging interactive
python -m gator.logger --severity DEBUG "This is a debug message"
python -m gator.logger --severity INFO "This is an info message"
python -m gator.logger --severity WARNING "This is a warning message"
python -m gator.logger --severity ERROR "This is an error message"

# Use STDOUT and STDERR
echo "This is STDOUT"
>&2 echo "This is STDERR"

# Launch a bunch of subprocesses
do_something () {
    echo "Launching $1"
    sleep 5
    echo "Finished $1"
}

for i in $(seq $tgt); do
    do_something $i &
    sleep 1
done

wait

# Run a high intensity process
# echo "Running high intensity calculation"
# a=0
# b=1234
# for i in $(seq 1000000); do
#     a=$(($a + $b))
# done
# echo "Result: $a"
