import ABC
from glob import glob
import pandas as pd
import os.path
import numpy as np
import re
import shutil
import time

# These assumes we live in the old ABC space so we explicitly
# move into ABC9 at the start and back to old ABC at the end of
# the script.
scripts = {
    "area1"   : "&get;&st;&dch;&nf;&put",
    "area2"   : "&get;&st;&synch2;&nf;&put",
    "area3"   : "&get;&st;&syn2;&synch2;&nf;&put",
    "delay1"  : "&get;&st;&if -g -K 6;&dch;&nf;&put",
    "delay2"  : "&get;&st;&if -g -K 6; &synch2; &nf; &put",
    "delay3"  : "&get;&st;&syn2;&if -g -K 6;&synch2;&nf;&put",
    "simple"  : "strash;dch;map -B 0.9",
    "oldarea" : "strash;dch;amap",
}

# if initialize or finalize is == "", then it will be skipped
util_scripts = {
    "initialize" : "&get;&st;&dch -x;&nf;&put",
    "finalize"   : "buffer -c;topo;stime -c;upsize -c;dnsize -c"
}

# Run the scatter shot of scripts on the design hierarchy
#  Nangate45_typ.lib
#  sky130_fd_sc_hs__tt_025C_1v80.lib
class Abc_scatter:
    def __init__(self,
                 libr = "/home/macd/libs/sky130_fd_sc_hs__tt_025C_1v80.lib",
                 iterations=5,  # generally use 5
                 scripts=scripts,
                 util_scripts=util_scripts
                 ):
        self.cmd = ABC.abc_start()
        if self.cmd(f"read_lib {libr}")[0] == 0:
            print(f"Read library {libr}")
        else:
            print(f"Problem reading library {libr}")

        self.iterations = iterations
        self.scripts = scripts
        self.util_scripts = util_scripts

        
    # Note: stime only works on the older network datastructure
    # Don't use globals for scripts etc here so we can filter
    # some if necessary.
    def shotgun(self, design):
        """Run all of the scipts on the design for a specified number of 
           iterations"""
        df = pd.DataFrame(columns=["design", "file", "script", "iteration",
                                   "cpu time", "gates", "area", "delay", "Pareto"])

        for script in self.scripts.items():
            etime = 0.0
            start = time.process_time()
            res = self.cmd(f"read_blif {design}")
            etime += time.process_time() - start
            if res[0] == 0:
                print(f"Read design {design}")
            else:
                print(f"Problem reading design {design}")

            if self.util_scripts["initialize"] != "":
                start = time.process_time()
                res = self.cmd(self.util_scripts["initialize"])
                etime += time.process_time() - start
                # Our starting design
                res = self.cmd("write_blif design.blif")
            
            for i in range(1, self.iterations+1):
                ###
                res = self.cmd("read_blif design.blif")
                start = time.process_time()
                res = self.cmd(script[1])
                etime += time.process_time() - start
                ### These are the intermediate design points
                res = self.cmd("write_blif design.blif")
            
                if self.util_scripts["finalize"] != "":
                    start = time.process_time()
                    res = self.cmd(self.util_scripts["finalize"])
                    etime += time.process_time() - start
                
                ta = self.parse_timing(self.cmd("stime -p"))
                fname = f"{script[0]}_{i}.blif"
                df.loc[len(df.index)] = [design, fname, script[0], i, etime, *ta, 0]
                print(f"{design} {script[0]} Iteration {i}:  {ta}")
                res = self.cmd(f"write_blif {fname}")

        return df

    # So yeah, kinda brittle parsing of the abc stime command. Let's hope Alan
    # doesn't change it often.
    def parse_timing(self, timing):
        st, res = timing
        if st != 0:
            print("Error parsing timing: bad ABC result")
            return

        # first find the correct line to parse
        line = ""
        for line in res.splitlines():
            if "Gates" in line and "Area" in line and "Delay" in line:
                break
            
        toks = list(filter(lambda x: x != "", re.split("[ m=\x1b]", line)))
        g = toks.index("Gates")
        a = toks.index("Area")
        d = toks.index("Delay")
    
        gates = 0
        area = delay = 0.0
    
        try:
            gates = int(toks[g+1].split('\e')[0])
            area  = float(toks[a+1].split('\e')[0])
            delay = float(toks[d+1].split('\e')[0])
        except:
            print("Parsing area and delay failed on the following line:")
            print(res[1])
            print(toks)

        return (gates, area, delay)

    # Only need to run one design here, but with multiple scripts
    def get_scatter_df(self, fn="input.blif", rn="results.csv"):
        results_df = pd.DataFrame(columns=["design", "file", "script", "iteration",
                                           "cpu time", "gates", "area",
                                           "delay", "Pareto"])

        df = self.shotgun(fn)
        results_df = results_df.append(df)
        results_df.to_csv(rn)
        return results_df


# Given a single file and a library, run all the scripts * iterations on it and
# generate the results.csv file as well as keep all the generated blifs'
def splat_one(infile, libr="/home/macd/libs/sky130_fd_sc_hs__tt_025C_1v80.lib"):
    sctx = Abc_scatter(libr=libr)
    sc_df = sctx.get_scatter_df(fn=infile)


# Given a abc_topdir, run all the scripts for a set number of iterations on
# each "input.blif" file in each subdirectory in abc_topdir.  The leaves all
# the produced blif's (# of scripts) * (# of iterations) in the directories
# and also leaves a file named "results.csv" which has all the optimization
# results (area, delay) for each blif
def splat(abc_topdir=None):
    mdirs = [os.path.abspath(dr) if os.path.isdir(dr) else None for dr in glob(f"./{abc_topdir}/*")]
    olddir = os.getcwd()

    sctx = Abc_scatter() # only start ABC once
    for dr in mdirs:
        # no output.blif means input.blif was empty. Delete it here so
        # we don't mess with it later
        if not os.path.exists(dr + "/output.blif"):
            shutil.rmtree(dr)
        else:        
            os.chdir(dr)
            sc_df = sctx.get_scatter_df()

    os.chdir(olddir)    


def dump_script(script, iters):
    scr = util_scripts["initialize"]
    for i in range(iters):
        scr = scr + ";" + scripts[script]
    scr = scr + ";" + util_scripts["finalize"]
    p = re.sub(";", "\n", scr)
    print(p)
    return p
        
