#!/bin/bash

mongoversion=$( mongo --version | awk '{print $4;}' )

if [[ "$mongoversion" =~ "2.0" ]] || [[ "$mongoversion" =~ "1.8" ]]; then
	printf "you are running mongodb < 2.2 - mongo-hacker disabled"
	if [ -f ~/.mongorc.js ]; then
		mv ~/.mongorc.js ~/.mongorc.js.disabled
	fi
elif [ -f ~/.mongorc.js.disabled ]; then
	mv ~/.mongorc.js.disabled ~/.mongorc.js
	printf "you are running mongodb >= 2.2 - mongo-hacker enabled"
fi