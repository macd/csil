# csil

This is definitely WIP.

A Python platform for experiments with [Yosys](https://github.com/YosysHQ/yosys),
[ABC](https://github.com/berkeley-abc/abc) and [OpenSTA](https://github.com/The-OpenROAD-Project/OpenSTA)

We also use the very nice Python package for parsing Liberty files 
[liberty-parser](https://codeberg.org/tok/liberty-parser)

Note that we currently use forked version of both [ABC](https://github.com/macd/abc) and 
[Yosys](https://github.com/macd/yosys) and the main version of OpenSTA


### Setup Notes

The Yosys Python wrapper module, must be installed and visible to
Python. You will have to build Yosys with `ENABLE_PYOSYS := 1` (In
order to do this you will need to have libboost-python-dev installed.)
This will make the libyosys.so library. You can use the Yosys Makefile
to install it, but I prefer to do that manually in my local anaconda3
tree. If you want to do that, then in the directory
~/anaconda3/lib/python3.8/site-packages make a directory named
pyosys. Copy libyosys.so (should be in the top level Yosys directory
after a successful build) to that directory. Also copy the file
`__init__.py` from the yosys/misc directory to that location as
well. The Yosys vendored abc, now named yosys-abc, needs to be copied
to the ~/anaconda3/bin directory, if you intend to use that. Finally,
you need to have the contents of yosys/share copied to a system
directory /usr/local/share/yosys. See the Yosys docs for more info.

The above mentioned forked version of ABC has a build script called wrapper.sh
which will also install the Python wrapper for ABC.

OpenSTA just needs to be on your path and we only shell out to it.
