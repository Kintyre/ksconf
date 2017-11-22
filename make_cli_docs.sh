#!/bin/bash

(
echo "# Kintyre Splunk Admin Script with CLI interfaces"
echo "Kintyre's Splunk scripts for various admin tasks."

for script in *.py
do
	echo "## $script"
	python $script --help | awk '$0="    "$0'
        if [ "$script" == "restore_from_frozen.py" ]
	then
		echo
		echo "### $script chunk"
		python $script chunk --help | awk '$0="    "$0'
		echo
		echo "### $script restore"
		python $script restore --help | awk '$0="    "$0'

	fi
	echo
	echo
done) > README.md


