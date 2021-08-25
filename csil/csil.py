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
    

class NoLibrarySpecified(Exception):
    pass

class NoScriptFileSpecified(Exception):
    pass

lib_cache = {}


# Stolen from stack overflow 7396849, get the string that is stored as 
# a bitstring constant in the attributes dict
def text_from_bits(bits, encoding='utf-8', errors='surrogatepass'):
    n = int(bits, 2)
    return n.to_bytes((n.bit_length() + 7) // 8, 'big').decode(encoding, errors) or '\0'


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


class ADesign:
    def __init__(self, fname=None, liberty=None, default_script=None):
        self.ys = ys
        self._fname = fname
        self._liberty = liberty
        self._default_script = default_script
        self._abc_exe = f"-exe {ABC_EXE}" if ABC_EXE != None else None
        
        if self._liberty != None:
            self._libinfo = make_lib(self._liberty)
        else:
            self._libinfo = None

        self._design = self.ys.Design()
        self._name = ""
        if fname != None:
            if not os.path.exists(fname):
                print(f"ERROR: file {fname} does not exist!")
                sys.exit(1)
            base, ext = os.path.splitext(fname)
            self._name = base
            if ext == ".v":
                self.read_verilog(fname)
            elif ext == ".rtlil":
                self.read_rtlil(fname)
            elif ext == ".blif":
                self.read_blif(fname)
            elif ext == ".aiger":
                self.read_aiger(fname)
            else:
                # add more file types??
                print("Unknown design file type")
            
        self._input_delay = None
        self._output_delay = None
        self._clk_name = None
        self._period = None
        self._delay = 0.0

    def read_verilog(self, vfile, opts=""):
        if os.path.exists(vfile):
            self.ys.run_pass(f"read_verilog {opts} {vfile}", self._design)
        else:
            print(f"Error: File {vfile} not found)")

    def read_liberty(self, libfile, opts=""):
        if os.path.exists(libfile):
            self._liberty = libfile
            self._libinfo = make_lib(self._liberty)
            self.ys.run_pass(f"read_liberty {opts} {libfile}", self._design)
        else:
            print(f"Error: File {libfile} not found)")

    # It used to be that sta did not like concats on the lhs, but that changed.
    # Also, Yosys added the -simple_lhs to the write_verilog command
    # to avoid these, but that's also not needed now.
    def bit_blast(self):
        self.ys.run_pass("splitnets -ports", self._design)

    def write_verilog(self, vfile, opts=""):
        self.ys.run_pass(f"write_verilog {opts} {vfile}", self._design)
    
    def read_blif(self, bfile, opts=""):
        if os.path.exists(bfile):
            self.ys.run_pass(f"read_blif {opts} {bfile}", self._design)
    
    def write_blif(self, bfile, opts=""):
        self.ys.run_pass(f"write_blif {opts} {bfile}", self._design)

    def read_aiger(self, bfile, opts=""):
        if os.path.exists(bfile):
            self.ys.run_pass(f"read_aiger {opts} {bfile}", self._design)

    # We use the ABC commands to write aiger so we don't need to run
    # the Yosys command aigmap
    def write_aiger(self, bfile):
        script = f"+strash; ifraig; write_aiger -s -u {bfile}"
        abc_cmd = f'abc {self._abc_exe} -script "{script}"'
        self.ys.run_pass(abc_cmd, self._design)

    def read_rtlil(self, vfile, opts=""):
        if os.path.exists(vfile):
            self.ys.run_pass(f"read_rtlil {opts} {vfile}", self._design)

    def write_rtlil(self, vfile, opts=""):
        self.ys.run_pass(f"write_rtlil {opts} {vfile}", self._design)
        
    def set_liberty(self, liberty):
        self._liberty = liberty
        if os.path.exists(liberty):
            self._libinfo = make_lib(self._liberty)
        else:
            print(f"Cannot find liberty file {liberty}")

    def clean(self, opts=""):
        self.ys.run_pass(f"clean {opts}", self._design)

    def synth(self, opts=""):
        self.ys.run_pass(f"synth {opts}", self._design)    


    def compile(self, abc_script=None, lib=None, opts=""):
        if lib == None:
            if self._liberty == None:
                raise NoLibrarySpecified
            else:
                lib = self._liberty
            
        if abc_script == None:
            if self._default_script == None:
                raise NoScriptFileSpecified
            else:
                abc_script = self._default_script

        # we need the " if we are passing the abc commands directly
        elif abc_script[0] == '+':
            abc_script = f'"{abc_script}"'
            
        if opts != "":
            OPTS = opts
        else:
            OPTS = YABC_OPTS
        
        if abc_script[0] != '"' and not os.path.exists(abc_script):
            print(f"Error: cannot find ABC script file {abc_script}\n")
            sys.exit(1)
            
        print(f"Using ABC script {abc_script} using library {lib}")

        base, ext = os.path.splitext(self._liberty)
        tflag = f"-constr {base}.constr"
        abc_cmd = f'abc {OPTS} {tflag} {self._abc_exe} -script {abc_script} -liberty {lib}'
        print("Calling ABC: ", abc_cmd)
        self.ys.run_pass(abc_cmd, self._design)
    
    def flatten(self, opts=""):
        self.ys.run_pass(f"flatten {opts}", self._design)    

    def uniquify(self):
        self.ys.run_pass("uniquify", self._design)    

    def help(self, s=""):
        self.ys.run_pass(f"help {s}")

    def topm(self):
        return self._design.top_module()

    def check(self):
        self.ys.run_pass("check", self._design)

    # Print the longest topological path in the design
    def ltp(self, opts=""):
        self.ys.run_pass(f"ltp {opts}", self._design)

    def ls(self):
        self.ys.run_pass("ls", self._design)

    def hierarchy(self, opts="-check"):
        self.ys.run_pass(f"hierarchy {opts}", self._design)

    # for those commands not yet wrapped
    def run(self, cmd):
        self.ys.run_pass(cmd, self._design)

    def traverse(self):
        self.hierarchy("-auto-top")
        module = self._design.top_module()
        print("Top module:", module.name.str()[1:])
        for cell in module.cells_:
            gate_name = module.cell(cell).type.str()[1:]
            name = cell.str()[1:]
            print(name, "  ", gate_name)

    # report area  NOTE: this currently only works on a flat design
    # TODO: Separate the combinational and the sequential cells into
    # separate subsections
    def sumry_area(self):
        if self._libinfo == None:
            print("Skipping area summary. No library")
            return
        
        all_cells = defaultdict(int)
        self.hierarchy("-auto-top")
        
        # This currently only works for flat designs.  Need to traverse the yosys hierarchy
        missing_cells = defaultdict(int) # warn only once per cell
        # to get all the cells
        module = self._design.top_module()
        for cell in module.cells_:
            name = module.cell(cell).type.str()[1:]
            # Only count cells in the library
            if name in self._libinfo:
                all_cells[name] += 1
            else:
                missing_cells[name] += 1

        if len(missing_cells) > 0:
            print("The following cells are not in the cell library:")
            for k, v in missing_cells.items():
                print(f"   |{name}| {v}")

        total_area = 0.0
        print("Area summary:")
        total_cells = 0
        unmapped_cells = defaultdict(int)
        for k, v in all_cells.items():
            if k not in self._libinfo:
                unmapped_cells[k] += 1
                continue
            cell_area = self._libinfo[k][0]
            used_area = v * cell_area
            total_cells += v
            total_area += used_area
            print("%34s  %6.3f  %5d  %9.3f" % (k, cell_area, v, used_area))

        print("Total area: %6.3f   Total number of cells %d" % (total_area, total_cells))
        
        if len(unmapped_cells) > 0:
            print("Warning: Design contains the following unmapped cells:")
            for k, v in unmapped_cells.items():
                print("%15s %5d" % (k, v))
                
        return total_area

    def create_clock(self, clk_name, period):
        self._clk_name = clk_name
        self._period = period
        
    def set_input_delay(self, input_delay):
        self._input_delay = input_delay

    def set_output_delay(self, output_delay):
        self._output_delay = output_delay

    def check_constraints(self):
        if self._input_delay == None:
            return False
        if self._output_delay == None:
            return False            
        if self._clk_name == None:
            return False            
        if self._period == None:
            return False
        return True
        
    # write tcl cmds and shell out to OpenSTA
    def report_checks(self, cleanup=True):
        if not self.check_constraints():
            print("Not all constraints are set")
            return
        tag = randtag(15)
        tmname = self._design.top_module().name.str()[1:]
        vfile = tag + ".v"
        sfile = tag + ".tcl"
        self.write_verilog(vfile, "-simple-lhs")
        nmclock = "-name"
        if self.has_port(self._clk_name):
            nmclock = ""
            
        with open(sfile, "w") as fd:
            fd.write(f"read_liberty {self._liberty}\n")
            fd.write(f"read_verilog {vfile}\n")
            fd.write(f"link {tmname}\n")
            fd.write(f"create_clock {nmclock} {self._clk_name} -period {self._period}\n")
            fd.write(f"set_input_delay -clock [get_clocks {self._clk_name}] {self._input_delay} [all_inputs]\n")
            fd.write(f"set_output_delay -clock [get_clocks {self._clk_name}] {self._output_delay} [all_outputs]\n")
            fd.write(f"report_checks")

        print("timing design with OpenSTA")
        results = subprocess.run(["sta", "-no_init", "-no_splash", "-exit", sfile],
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
            for f in glob.glob(f"{tag}*"):
                os.remove(f)
            
        return (delay, slack)

    # Return a copy of the current design
    # TODO: copy the persistant abc_dir as well?
    def copy(self):
        tmp_name = "_tmp_design_" + randtag(3)
        self.ys.run_pass(f"design -save {tmp_name}", self._design)
        nd = ADesign()
        nd._liberty = self._liberty
        nd._libinfo = self._libinfo
        nd._default_script = self._default_script
        self.ys.run_pass(f"design -load {tmp_name}", nd._design)
        self.ys.run_pass(f"design -delete {tmp_name}", self._design)
        nd._name = self._name + "_cp_" + randtag(4)
        
        # Copy any constraints
        nd._input_delay = self._input_delay
        nd._output_delay = self._output_delay
        nd._clk_name = self._clk_name
        nd._period = self._period
        nd._delay = self._delay
        
        return nd

    # Most likely the ports have been bit blasted, so check for name "a[1]" etc, if needed
    def has_port(self, pname):
        # remember all Yosys names begin with "\", and we add that here
        id_pname = self.ys.IdString("\\" + pname)
        tm = self._design.top_module()
        if id_pname in tm.wires_ and tm.wire(id_pname).port_id != 0:
            return True

        return False

    def map_flops(self):
        self.ys.run_pass(f"dfflibmap -liberty {self._liberty}")

    def unmap(self):
        # TODO: need to read in a mapped design into abc.  Can that only be done
        # with mapped Verilog? Or are there better ways?
        # FIXME: This completes the abc command OK but does not reintegrate the new
        # unmapped netlist into Yosys RTLIL. Maybe have abc write out a file and then
        # read that back into yosys
        vfile = randtag(15) + ".v"
        self.write_verilog(vfile, "-noattr")
        script = f"+read_lib {self._liberty}; read_verilog -m {vfile}; unmap"
        self.ys.run_pass(f'abc {YABC_OPTS} {self._abc_exe} -script "{script}"')
        os.remove(vfile)

    # Is there a good way to set default constraints on the design for STA?
    def tdefault(self, period=10.0):
        self.set_input_delay(0)
        self.set_output_delay(0)
        self.create_clock("clk", period)
