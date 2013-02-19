#!/bin/bash

logfile=$1

if [ $logfile ] && [[ -e $logfile ]] ; then
  # if logfile exists:
  XXX=$(grep -n 'RESTARTED' $logfile | tail -1 | awk -F: '{print $1}')
  if [ $XXX ]; then
    tail -n +$XXX $logfile > $logfile-from_last_restart.log
  else
    echo "$logfile does not contain 'RESTARTED'"
  fi
else
  # if logfile does not exist:
  echo 'The logfile does not exist or is not defined.'
  echo 'USAGE: rlogtail.sh mongoX.log'
fi