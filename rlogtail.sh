#!/bin/bash

logfile=$1

if [ $logfile ] && [[ -e $logfile ]] ; then
  # if logfile exists:
  XXX=$(tail -r $logfile | grep -n 'RESTARTED' -m 1 | awk -F: '{print $1}')
  if [ $XXX ]; then
    newlogfile="$(echo $logfile | sed 's/\.log//')-from_last_restart.log"
    logfilelength=$(wc -l $logfile | awk '{print($1)}')
    tail -n +$(expr $logfilelength - $XXX) $logfile > $newlogfile
  else
    echo "$logfile does not contain 'RESTARTED'"
  fi
else
  # if logfile does not exist:
  echo 'The logfile does not exist or is not defined.'
  echo 'USAGE: rlogtail.sh mongoX.log'
fi