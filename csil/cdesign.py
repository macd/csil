from collections import defaultdict
import copy
import glob
import os
import random
import string
import subprocess
import sys
import abc
from pyosys import libyosys as ys


def randtag(n):
    return ''.join(random.choice(string.ascii_letters) for _ in range(n))    


# These can take options as a string argument.  Also can generally take a
# selection too, but then that is tacked on to the end of the options string
funcs = ["add",
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
         "copy",
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
         "orlo",           # Note: the orlo plugin must be already loaded
         "orlo_reint",
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
         "read_aiger",
         "read_blif",
         "read_liberty",
         "read_rtlil",
         "read_verilog",
         "rename",
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


# This is only intended to run once at import time to construct the class YDesign
def _make_YDesign_class():
    def __init__(self):
        self.ys = ys
        self.ydesign = self.ys.Design()
        self.ys.run_pass("plugin -i orlo", self.ydesign)

    # Run a generic Yosys command/pass that is not already wrapped
    def run(self, cmd):
        self.ys.run_pass(cmd, self.ydesign)
        return self

    cls_attrs = {}
        
    for fun in funcs:
        cmd  = 'def %s(self, opts=""):\n' % fun
        cmd += '    self.ys.run_pass("%s" + " " + opts, self.ydesign)\n' % fun
        cmd += '    return self'
        exec(cmd)
        cls_attrs[fun] = locals()[fun]

    cls_attrs["__init__"] = __init__
    cls_attrs["run"] = run
    
    return type("YDesign", (object,), cls_attrs)


YDesign = _make_YDesign_class()


# This is the user visible class.  We will save here the design files, the
# liberty file, sdc info, etc
class CDesign(YDesign):
    def __init__(self, design_files=[], liberty_file=""):
        super().__init__()
        self.design_files = design_files
        if design_files:
            for dfile in design_files:
                if not os.path.exists(design_file):
                    print(f"ERROR: file {dfile} does not exist!")
                else:
                    base, ext = os.path.splitext(dfile)
                    self.name = base
                    if ext == ".v":
                        self.read_verilog(dfile)
                    elif ext == ".rtlil":
                        self.read_rtlil(dfile)
                    elif ext == ".blif":
                       self.read_blif(dfile)
                    elif ext == ".aiger":
                       self.read_aiger(dfile)
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

        self.checkpoints = {}
        
        # Some default SDC values for the lazy 
        self.clock = "clk"
        self.period = 1.0
        self.input_delay = 0.0
        self.output_delay = 0.0
        # an elaborated but unmapped design
        self.elab = None

    def __repr__(self):
        r  = "Design file:  " + self.design_file
        r += f"\n    {str(self.ydesign)}"
        r += "\n    Liberty file  : " + self.liberty
        r += "\n    clock         : " + str(self.clock)
        r += "\n    period        : " + str(self.period)
        r += "\n    input delay   : " + str(self.input_delay)
        r += "\n    output delay  : " + str(self.output_delay)
        return r

    # Make an sdc file suitable for OpenSTA given a fully mapped gate level verilog file
    def make_sdc(self, vfile):
        topname = self.ydesign.top_module().name.str()[1:]
        sdc_file = topname + "_" + randtag(5) + ".sdc"
        nflag = "-name" if self.is_port(self.clock) else ""
        with open(sfile, "w") as fd:
            fd.write(f"read_liberty {self.liberty}\n")
            fd.write(f"read_verilog {vfile}\n")
            fd.write(f"link {topname}\n")
            fd.write(f"create_clock {nflag} {self.clock} -period {self.period}\n")
            fd.write(f"set_input_delay -clock [get_clocks {self.clock}] {self.input_delay} [all_inputs]\n")
            fd.write(f"set_output_delay -clock [get_clocks {self.clock}] {self.output_delay} [all_outputs]\n")
            fd.write(f"report_checks")
        return sdc_file

    # Possibly the ports have been bit blasted, so check for name "a[1]" etc, if needed
    def is_port(self, name):
        # remember all Yosys names begin with "\", and we add that here
        id_name = self.ys.IdString("\\" + name)
        tm = self.ydesign.top_module()
        if id_name in tm.wires_ and tm.wire(id_name).port_id != 0:
            return True
        return False
    
    #  Create a copy of the design including all metadata.  We need Yosys to 
    #  make a new copy as well.
    #  NOTE: To state the obvious, this returns the copy.
    def copy(self):
        other = copy.copy(self)
        other.ydesign = other.ys.Design()
        tmp_name = randtag(10)
        self.ys.run_pass(f"design -save {tmp_name}", self.ydesign)
        other.ys.run_pass(f"design -load {tmp_name}", other.ydesign)
        self.ys.run_pass(f"design -delete {tmp_name}", self.ydesign)
        return other

    def checkpoint(self, name):
        self.checkpoints[name] = self.copy()
        return self
    
    # Shell out to OpenSTA
    def report_checks(self, cleanup=True):
        tag = randtag(15)
        vfile = tag + ".v"
        self.write_verilog(f"-simple-lhs {vfile}")
        sdc_file = self.make_sdc(vfile)

        print("timing design with OpenSTA")
        results = subprocess.run(["sta", "-no_init", "-no_splash", "-exit", sdc_file],
                                 stdout=subprocess.PIPE, universal_newlines=True)
        delay = slack = None
        for line in results.stdout.split("\n"):
            print(line)
            if "data arrival time" in line:
                delay = -float(line.split()[0])  # - because this picks up the second def
            elif "slack" in line:
                slack = float(line.split()[0])
                
        # clean up temp files
        if cleanup:
            print("Cleaning up temp files\n")
            os.remove(vfile)
            os.remove(sdc_file)

        # Note this does not return self so you cannot "pipe" report_checks
        return (delay, slack)

    def elaborate(self, retime=False):
        self.hierarchy("-auto-top")
        if retime:
            self.scratchpad("-set abc.dff true")
        self.synth()
        self.opt("-purge")
        self.elab = self.copy()
        return self

    def unmap(self):
        if self.elab == None:
            print("Error: no design to unmap")
        else:
            # just to note that bad things happed when I "del self.ydesign"
            self.design("-reset")  
            self.ydesign = self.elab.ydesign 
            self.elab = self.copy()
        return self

    # use the default abc script just to set up the directories and input files
    # TODO: replace default script with an even smaller one
    def setup(self):
        cached = self.copy()
        
        # map full adders
        #self.extract_fa()
        #self.techmap("-map cells_adders.v")  # where should we have cells_adders.v?
        #self.techmap()
        #self.opt("-fast -purge")

        # map latches
        #self.techmap(f"-map -lib cells_latch.v")

        # Map flip flops
        self.dfflibmap(f"-liberty {self.liberty}")
        self.abc(f"-liberty {self.liberty} -nocleanup -abc_topdir={os.getcwd()}")
        abc_dir = self.scratchpad("-get abc.dir")
        
        self.design("-reset")
        self.ydesign = cached.ydesign
        self.scratchpad(f"-set abc.dir {abc_dir}")
        cached.ydesign = None
        del cached
        return self

    def splat(self):
        pass
        #abc_dir = self.scr
