#!/bin/bash

tgt=${1:-10}

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

a=0
b=1234
for i in $(seq 1000000); do
    a=$(($a + $b))
done
echo "Result: $a"
