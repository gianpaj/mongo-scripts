#!/bin/bash

logfile=$1

timematch=$2

# if logfile exists:
if [ $logfile ] && [[ -e $logfile ]] ; then
  # TODO: find if we should start from the bottom or the top of the file

  XXX=$(tail -r $logfile | grep -n ^$timematch -m 1 | awk -F: '{print $1}')
  if [ $XXX ]; then
    newlogfile="$(echo $logfile | sed 's/\.log//')-from_$timematch.log"
    # logfilelength=$(wc -l $logfile | awk '{print($1)}')
    tail -n-$XXX $logfile > $newlogfile
  else
    echo "$logfile does not contain $timematch"
  fi
else
  # if logfile does not exist:
  echo 'The logfile does not exist or is not defined.'
  echo 'USAGE: rlogtail.sh mongoX.log'
fi