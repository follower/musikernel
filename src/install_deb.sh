if [ -e ./core ]; then
	#Delete the core file if exists, sometimes the binary won't
	#delete it and then replace with a new core
	rm -f ./core
fi

sudo ./deb.py --default-version && sudo dpkg -i pydaw-build/pydaw*.deb
