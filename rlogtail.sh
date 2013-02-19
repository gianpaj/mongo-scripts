#!/bin/bash

logfile=$1

if [ $logfile ] && [[ -e $logfile ]] ; then
  # if logfile exists:
  XXX=$(grep -n 'RESTARTED' $logfile | tail -1 | awk -F: '{print $1}')

  tail -n +$XXX $logfile > $logfile-from_last_restart.log
else
  # if logfile does not exist:
  echo 'The logfile does not exist or is not defined.'
  echo 'USAGE: rlogtail.sh mongoX.log'
fi