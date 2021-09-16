from collections import defaultdict
import copy
import glob
import os
import random
import string
import subprocess
import sys
import ABC
import liberty
from liberty.parser import parse_liberty
from pyosys import libyosys as ys


# So a hack. This assumes that we have abc executable in top dir of abc install
ABC_EXE =  os.path.split(ABC.__file__)[0] + "/../abc"
if not os.path.exists(ABC_EXE):
    ABC_EXE = None

    
lib_cache = {}

# Process a liberty library down to a dict of cell names and areas
def make_lib(fname):
    if fname in lib_cache:
        return lib_cache[fname]

    try:
        libr = parse_liberty(open(fname).read())
    except:
        print(f"Error parsing liberty library {fname}")
        return None
    
    nm2area = {}
    for cell in libr.get_groups("cell"):
        name = cell.args[0]
        if type(cell.args[0]) == liberty.types.EscapedString:
            name = cell.args[0].value
        nm2area[name] = cell.attributes["area"]
    del libr
    lib_cache[fname] = nm2area
    return nm2area


def randtag(n):
    return ''.join(random.choice(string.ascii_letters) for _ in range(n))    


# These can take options as a string argument.  Also can generally take a
# selection too, but then that is tacked on to the end of the options string
noarg_funcs = ["abc",
              "abc_reint",
              "add",
              "aigmap",         
              "alumacc",
              "assertpmux",
              "async2sync",
              "attrmap",
              "attrmvcp",
              "autoname",
              "blackbox",
              "cd",
              "check",
              "chformal",
              "chparam",
              "chtype",
              "clean",
              "clk2fflogic",
              "clkbufmap",
              "connect",
              "connwrappers",
              "cover",
              "cutpoint",
              "debug",
              "delete",
              "deminout",
              "design",
              "dffinit",
              "dfflegalize",
              "dfflibmap",
              "dffunmap",
              "dump",
              "edgetypes",
              "eval",
              "expose",
              "extract",
              "extract_fa",
              "extract_reduce",
              "extractinv",
              "flatten",
              "fmcombine",
              "fminit",
              "freduce",
              "help",
              "hierarchy",
              "hilomap",
              "history",
              "insbuf",
              "iopadmap",
              "json",
              "log",
              "logger",
              "ls",
              "ltp",
              "maccmap",
              "mutate",
              "muxcover",
              "muxpack",
              "onehot",
              "opt",
              "opt_clean",
              "opt_demorgan",
              "opt_dff",
              "opt_expr",
              "opt_mem",
              "opt_mem_feedback",
              "opt_mem_priority",
              "opt_mem_widen",
              "opt_merge",
              "opt_muxtree",
              "opt_reduce",
              "opt_share",
              "paramap",
              "peepopt",
              "pmux2shiftx",
              "pmuxtree",
              "portlist",
              "prep",
              "printattrs",
              "proc",
              "proc_arst",
              "proc_clean",
              "proc_dff",
              "proc_dlatch",
              "proc_init",
              "proc_memwr",
              "proc_mux",
              "proc_prune",
              "proc_rmdead",
              "rmports",
              "sat",
              "scatter",
              "scc",
              "scratchpad",
              "script",
              "select",
              "setattr",
              "setparam",
              "setundef",
              "share",
              "show",
              "shregmap",
              "sim",
              "simplemap",
              "splice",
              "splitnets",
              "stat",
              "submod",
              "supercover",
              "synth",
              "tcl",
              "techmap",
              "tee",
              "torder",
              "trace",
              "tribuf",
              "uniquify",
              "verilog_defaults",
              "verilog_defines",
              "wbflip",
              "wreduce",
              "write_aiger",
              "write_blif",
              "write_edif",
              "write_rtlil",
              "write_spice",
              "write_verilog",
              "write_xaiger",
              "zinit"]

# Functions that read in designs 
read_funcs = set(['read_verilog', 'read_blif', 'read_aiger', 'read_rtlil'])

#read_liberty

# Functions that must have one argument
onearg_funcs = ['debug', 'echo', 'read_verilog', 'read_blif', 'read_aiger',
                'read_rtlil', 'tcl']

# two
twoarg_funcs = ['copy', 'rename']

# This is only intended to run once at import time
# TODO: determine if we really want to distinguish between no-arg, one-arg,
#   etc, Yosys commands.  Pro is we can do more error checking and cache some 
#   things, cons is we have more complexity (and caches can become out of date)
def _make_cdesign_class():
    def __init__(self, design_file="", liberty_file=""):
        self.ys = ys
        self.ydesign = self.ys.Design()
        self.design_file = design_file
        if design_file != "":
            if not os.path.exists(design_file):
                print(f"ERROR: file {design_file} does not exist!")
                self.design_file = ""
                
            base, ext = os.path.splitext(design_file)
            self.name = base
            if ext == ".v":
                self.read_verilog(design_file)
            elif ext == ".rtlil":
                self.read_rtlil(design_file)
            elif ext == ".blif":
                self.read_blif(design_file)
            elif ext == ".aiger":
                self.read_aiger(design_file)
            else:
                print("Unknown design file type")

        self.liberty = liberty_file
        self.libinfo = None
        if self.liberty != "":
            if not os.path.exists(liberty_file):
                print(f"ERROR: file {liberty_file} does not exist!")
                self.liberty = ""
            else:
                self.libinfo = make_lib(self.liberty)

    def __repr__(self):
        r  = "Design file:  " + self.design_file
        r += "\nLiberty file: " + self.liberty
        return r

    # Get help
    def help(self, arg=""):
        self.ys.run_pass("help " + arg, self.ydesign)
        return self
    
    # Run a generic Yosys command/pass 
    def run(self, cmd):
        self.ys.run_pass(cmd, self.ydesign)
        return self

    cls_attrs = {}
        
    for fun in noarg_funcs:
        cmd  = 'def %s(self, opts=""):\n' % fun
        cmd += '    self.ys.run_pass("%s" + " " + opts, self.ydesign)\n' % fun
        cmd += '    return self'
        exec(cmd)
        cls_attrs[fun] = locals()[fun]

    for fun in onearg_funcs:
        cmd  = 'def %s(self, arg, opts=""):\n' % fun
        if fun in read_funcs:
            cmd += '    self.design_file = arg\n'
        cmd += '    self.ys.run_pass("%s" + " " + opts + " " + arg, self.ydesign)\n' % fun
        cmd += '    return self'
        exec(cmd)
        cls_attrs[fun] = locals()[fun]
        
    cls_attrs["__init__"] = __init__
    cls_attrs["__repr__"] = __repr__
    cls_attrs["help"] = help
    cls_attrs["run"] = run
    
    return type("CDesign", (object,), cls_attrs)


CDesign = _make_cdesign_class()
