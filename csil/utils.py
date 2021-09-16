import time
import os.path
import re
import sys
import numpy as np
import pandas as pd
import matplotlib.pylab as plt
from glob import glob
import shutil


def plot_it(d, df, x, y):
    fig, ax1 = plt.subplots(1, 1)
    fig.set_figheight(7)
    fig.set_figwidth(9)

    for sc in set(df['script']):
        rows = df.loc[df['script'] == sc]
        print(rows)
        plt.plot(rows[x], rows[y], ".-", label=sc)

    # Mark the Pareto optimal points for the area vs delay plot
    if x == "area":
        p = get_pareto(df[["area", "delay"]].to_numpy(), [0, 1], [])
        plt.scatter(p[:, 0], p[:, 1], s=80, facecolors="none", edgecolors="r")
        
    ax1.set_xlabel(x)
    ax1.set_ylabel(y)
    ax1.legend()
    ax1.set_title(f"{x} vs {y} for {d}")
    #nm = "all_scatter_plots/" + os.path.splitext(os.path.basename(d))[0] + f"_{x}_vs_{y}" + ".png"
    nm = os.path.splitext(os.path.basename(d))[0] + f"_{x}_vs_{y}" + ".png"
    fig.savefig(nm)
    plt.close(fig)


# We have two n-vectors x and y.  min_idxs is a vector of indices at which
# x[i] < y[i], if x is to dominate y. Likewise, max_idxs is a vector of
# indices at which x[i] > y[i], if x is to dominate y
def domvals(x, y, min_idxs, max_idxs):
    n_better = 0
    n_worse  = 0

    for i in min_idxs:
        n_better += x[i] < y[i]
        n_worse  += x[i] > y[i]
    
    for i in max_idxs:
        n_better += x[i] > y[i]
        n_worse  += x[i] < y[i]
    
    return n_better, n_worse


# Conditionally update the pareto set (a set of n-vectors) with a new candidate
# vector x. The vector min_idxs contains the indices of the vector x whose
# values we want to find the minimum and analogously for the vector max_idxs.
# Note that if an index does not appear in either min_idxs or max_idxs, it will
# not be used in calculating the Pareto front
def update_pareto(pareto, x, min_idxs, max_idxs):
    remove_pts = set()
    for p in pareto:
        n_better, n_worse = domvals(x, list(p), min_idxs, max_idxs)

        # Current candidate is dominated by point j in pareto so ignore it
        # To avoid including duplicate points, change "n_worse > 0" to "n_worse >= 0"
        if n_worse > 0 and n_better == 0:
            return pareto

        # Current candidate dominates point p in pareto, so remove p from pareto
        # Need to convert to tuple, since you cannot hash a list
        if n_better > 0 and n_worse == 0:
            remove_pts.add(p)
        
    pareto = pareto - remove_pts
    pareto.add(tuple(x))
    return pareto


# Use get_pareto when you already have a numpy matrix (whose rows are points)
# out of which you want to extract the Pareto front
# min_idxs is a list of indices on which we want the minimum value
# max_idxs is a list of indices on which we want the maximum value
# an index cannot be both in min_idxs and max_idxs
def get_pareto(V, min_idxs, max_idxs):
    pareto = set()
    for x in V:
        pareto = update_pareto(pareto, x, min_idxs, max_idxs)

    return np.concatenate([np.array(o, ndmin=2) for o in pareto])


# Plot the results contained in the CSV file "fn".  Circle the design points
# that are on the Pareto Front.
def plt_csv(fn, do_cpu=False):
    sc_df = pd.read_csv(fn)
    for d in set(sc_df['design']):
        drows = sc_df.loc[sc_df['design'] == d]
        plot_it(d, drows, "area", "delay")
        if do_cpu:
            plot_it(d, drows, "iteration", "cpu time")


# Just a quick and dirty hack to see if we get useful results, _but_ it is 
# problematic for how do we weigh area vs delay?  Here, we scale such that
# (max_delay - min_delay) = 1 and (max_area  - min_area)  = 1  and then
# take the min distance to llh corner. A real solution will involve using 
# only designs on the pareto front to meet the timing constraints with a 
# minimum area.  Probably using a backtracking algorithm.
def get_best(sc_df):
    area  = sc_df["area"].to_numpy()
    delay = sc_df["delay"].to_numpy()
    min_area  = np.min(area)
    min_delay = np.min(delay)
    max_area  = np.max(area)
    max_delay = np.max(delay)
    s_area  = (max_area  - min_area)**2
    s_delay = (max_delay - min_delay)**2
    min_dist = 1e20
    min_idx = -1
    for i in range(0, sc_df.shape[0]):
        dist = (min_area - area[i])**2 / s_area +  (min_delay - delay[i])**2 / s_delay
        if dist < min_dist:
            min_dist = dist
            min_idx = i
            
    return min_idx

# by copying the best implementation to output.blif, it will be used by
# reintegrate
def choose_impl(fn):
    sc_df = pd.read_csv(fn)
    idx = get_best(sc_df)
    print("Best impl: ", sc_df["design"][idx])
    shutil.copy(sc_df["design"][idx], "output.blif")
        

def iselect(abc_dir=None):
    mdirs = [os.path.abspath(dr) if os.path.isdir(dr) else None for dr in glob(f"./{abc_dir}/*")]
    olddir = os.getcwd()
    for dr in mdirs:
        os.chdir(dr)
        choose_impl("results.csv")        

    os.chdir(olddir)
        
