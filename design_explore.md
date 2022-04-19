# ASIC Design Space Exploration with ABC and Yosys

[Yosys](https://github.com/yosyshq/yosys) is an open source RTL
synthesis tool. Yosys uses the open source
[ABC](https://github.com/Berkeley-Abc/Abc) tool to do the final logic
optimization as well as the technology mapping to the technology that
is specified in an ASIC .lib file. 

## General concepts

Design exploration involves assessing various design implementations
for suitability.  Generally, we want a design that is 

  1. Just "fast enough" to meet the design constraints.
  2. Is minimum area for the desired speed.

Designs that are on this optimal frontier (ie smallest design for a given
speed) are said to be on a Pareto Optimal frontier. In some places, this
is also known as the "banana curve" (for obvious reasons). (We glossed
over the desire for low power designs for two reasons. First, there 
are not many ways to directly control those results from Yosys/ABC.
Second, many of those considerations are better done in placement and
routing).

Ideally, we would like to set our timing requirements (in an SDC file,
say) and then have the tools figure out which set of optimizations to
use and finally deliver a minimum area design that meets our
constraints. Unfortunately, neither of these tools can be driven in
this fashion. Yosys has no knowledge of either timing or constraints.
This means that any RTL optimization can only be done in a minimum
area fashion. While ABC does have a simple delay tracer to calculate
technology dependent path delays, it cannot be given a target delay
that it can reliably meet with a min area design.

Both of these tools are **recipe** based.  That is, you construct a
recipe out of smaller transformations (which stepwise may or may not
lead to a better design) and then at the end of the recipe you must
evaluate area (within ABC or Yosys) and the timing (which is usually
more reliable with the external tool OpenSTA) to decide on the design's
suitability.

## The current Yosys flow

A highly abstracted flow for Yosys looks something like

  1. Read Verilog
  2. Perform design elaboration and RTL optimization
  3. Perform gate level optimization and technology mapping (using ABC)
  4. Output a gate level Verilog file suitable for physical design

As we noted earlier, since Yosys has no timing info and no knowledge of
the constraints, there is not a lot we can do to affect speed/area tradeoffs
directly in Yosys (barring major surgery on the tool).

It does have some RTL optimization capabilities however. It can do
**resource sharing** for example. This is the sharing of adders,
subtractors, etc, based on **activation conditions** (logic that controls
when the output of an adder, say, is actually used). If it can prove,
by using a SAT algorithm, that the activation conditions for two adders
are never simultaneously active, then it will build a shared adder with
the appropriate muxing and mux conditions. 

Unfortunately, if one of those mux conditions is late arriving, this
step moves this late arriving signal from **after** the adder to
**before** the adder with a potentially huge negative impact on the
cycle time. The Yosys command `share` does this sharing. But this
command is on by default in the "meta" command `synth`, which runs a
default synthesis script. If you suspect that this is a problem, then
you must run `synth -noshare` through to having a fully technology
mapped design and then evaluate the timing with OpenSTA.

After RTL synthesis is complete, Yosys then uses ABC to do the gate
level logic optimization and finally the technology mapping.  It does
this by writing out the logic to a file and then shelling out to ABC
with one of its default scripts.  After ABC optimizes and maps the
logic, it writes out a blif file that Yosys reincorporates into the
design so that finally it can write out a gate level netlist.

The logic that Yosys writes out for ABC is written as blif (Berkeley
Logic Interchange Format) in a file that is always named "input.blif"
with a top level circuit name in the blif that is always named
"model". This is not a problem when the design is flattened and there
is only one design instance.

When the design is hierarchical, this becomes a problem because each
hierarchical instance is put into its own directory with a randomly
generated name. Thus, if you specify -nocleanup (and not -flatten) to
the Yosys `abc` command, you will get scores of randomly generated names
of directories, each with a file named "input.blif" with a top level
name of "model" with no way to tell one from another.

One final note is that since ABC is also recipe based, we must pass
a static script which ABC will use to optimize the logic. Yosys has
a handfull of default scripts that can be used, but most of them yield
sub-optimal results. You can however, specify a different ABC script,
either on the Yosys `abc` command line, or in a separate file. But this
leads to a single design and not a set of designs for evaluation.

## Python wrapper for ABC for Design Exploration

An issue with ABC is that there is no single script that is optimal
for all designs and indeed there is no deterministic way to generate a
Pareto optimal front for any particular design.  What seems to work
best is a set of ABC scripts, some area oriented and some timing oriented,
and then iterating each script multiple times.  This generates a
'point cloud' of 40 or more designs from which we can extract a Pareto
front of designs.

ABC has a very simple scripting language but it has no variables,
conditionals, or loops, so building design exporation in this language
is infeasible. To make this easier, we have forked a version of
[ABC](https://github.com/macd/abc) that provides a Python wrapper,
using SWIG.  The fork does not modify any of the native ABC files, it
only provides the Python wrapper and a way to install that locally
(using `pip install -e ...`) and we strive to keep this repo updated
with the current state of ABC.  The directions on how to build the
wrapper and install it are in the file **PY_README.md**.

Besides providing Python as the language with which to build some
exploration capabilities, we can also leverage the **multiprocessing**
module in the standard library to simultaneously spawn multiple jobs.

The api that ABC provides is just calling its internal shell with a
string of the command as a argument, so it is very straightforward and
the ABC command documentation can be used fairly directly. Here is a
very small example.

    import ABC
    opto_script = "&get -n;&st;&if -g -K 6;&dch;&nf;&put"
    initialize  = "&get -n;&st;&dch -x;&nf;&put"
    finalize    = "buffer -c;topo;stime -c;upsize -c;dnsize -c"
    
    abc_cmd = ABC.abc_start()
    abc_cmd("read_lib ~/libs/sky130_fd_sc_hs__tt_025C_1v80.lib")
    abc_cmd("read_blif mydesign.blif")
    abc_cmd(initialize)
    
    for i in range(5):
        abc_cmd(opto_script)
        abc_cmd(finalize)
        abc_cmd(f"write_blif mydesign_opt_{i}.blif")
        
and it will generate a set of five designs named `my_design_opt_0.blif` to 
`my_design_opt_4.blif`

In building a design exploration capability it is necessary to know
what the results of a particular optimization step gives.  But the ABC
commands only return a 0 or 1 according to whether a command has
passed or failed. The commands that give information about the current
design, such as `print_stats` or `stime` all write directly to the terminal.

To overcome this limitation, the `abc_cmd` as defined above returns a
tuple.  The first member of the tuple is the return status of the ABC
command. The second member of the tuple is the string that ABC would
have written to the terminal. This string is often empty, but on the
commands for information, its results are useful.

The results of the `stime -p` command can be parsed to find out the
current gate count, area, and maximum arrival time at the outputs with
the Python command **parse_timing** which is in the **csil** module
(more on this later).

    import ABC
    import csil
    abc_cmd = ABC.abc_start()
    abc_cmd("read_lib ~/libs/sky130_fd_sc_hs__tt_025C_1v80.lib")
    abc_cmd("read_blif mydesign.blif")
    abc_cmd(initialize)
    abc_cmd(opto_script)
    gate_count, area, timing = csil.parse_timing(abc_cmd("stime -p"))

## A new plugin for Yosys

When doing design exploration with Yosys, we would like to be able to
run a variety of logic synthesis scripts and perhaps even a variety of
different logic synthesis tools. So we would like to save the state of
the design (with the various `input.blif`s) just before actually
calling ABC. If we had a way to do that, then independently perform
many logic level experiments, pick the best one, and then reintegrate
those results into the design. We have created a Yosys plugin named
`orlo` do these steps. In Yosys, you would use the `plugin` command to
enable it (once the plugin is installed, which generally means that
the file `orlo.so` should be located in one of the directories that
Yosys will search for plugins). To load the plugin

    yosys> plugin -i orlo

The orlo plugin defines two new(ish) commands for Yosys. The first is
named simply `orlo` and it is (mostly) a copy of the `abc` command
with an additional argument named `-abc_topdir`.  This is the name of
an existing directory into which only **one** randomly named directory
is placed. Into this randomly named directory are created
subdirectories each of which is named after the module instance in the
Verilog design from which it was generated. This allows identification
of the subdesign so that it can be reintegrated into an ummapped top
design.  Also each directory name has a suffix "_n" where n is an
integer starting at 0. This is done because Yosys will partition a
module based on clock domains and send them individually to ABC and
this suffix keeps track of that. (But note, many modules have only one
clock domain).

Another command that is defined by this plugin is `orlo_reint`.  Given
the name of a top level directory that contains the optimized blif
(this is the one randomly generated by Yosys), it will reintegrate the
optimized and mapped blif back into an **unmapped design**. This
generally means that you need to save the **RTLIL** version of the
design before you call abc. There is one small wrinkle here inasmuch
as Yosys subtly changes the design on writing it out to RTLIL so that
we need to write out the RTLIL and then immediately read it back in
before issuing the `orlo` command.  This insures that all the naming
is correct so that the `orlo_reint` command doesn't fail. That would
look something like

    yosys> plugin -i orlo
    yosys> read_verilog mydesign.v
    yosys> synth
    yosys> rename -wire
    yosys> dfflibmap -liberty ~/libs/sky130_fd_sc_hs__tt_025C_1v80.lib
    yosys> write_rtlil mydesign.rtlil
    yosys> read_rtlil mydesign.rtlil
    yosys> orlo -liberty ~/libs/sky130_fd_sc_hs__tt_025C_1v80.lib -nocleanup -abc_topdir .
    
    ... use ABC to do various logic optimizations on input.blif here
    ... put desired results in the output.blif files
    
    yosys> read_rtlil mydesign.rtlil
    yosys> orlo_reint -abc_dir ./yosys-abc-hA2PPY
    

## A Python package for exploring with different ABC scripts

The python package [csil](https://github.com/macd/csil) provides some capability
for executing multiple ABC scripts and then choosing the best one to re-integrate
into the design.

