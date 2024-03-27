#!/usr/bin/env bash

venv_dir="$(dirname $1)/venv"
if [ -d "${venv_dir}" ] ; then
	. "${venv_dir}/bin/activate"
else
	echo "${venv_dir} not found" > /dev/stderr
fi

"$@"
