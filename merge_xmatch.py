

import os
import sys
import glob


from pycrates import read_file
from crates_contrib.utils import *


files = glob.glob("XMatch/*.xmatch")
files.sort()

cols =  ['obi1','obi2', 't1', 't2','ra_ref','dec_ref','roll_ref',
    'xpix_ref','ypix_ref','x_scale','y_scale']


retvals = { x : [] for x in cols }


for f in files:    
    aa = f.split("/")[-1].split('.')[0]
    retvals['obi1'].append(aa.split("_")[0])
    retvals['obi2'].append(aa.split("_")[1])

    print(f)
    tab = read_file(f)
    if tab.get_nrows() == 0:
        for c in cols[2:]:
            retvals[c].append(-999.0)
    else:
        for c in cols[2:]:
            retvals[c].append( tab.get_column(c).values[0])
        

write_columns("merged_xforms.fits",retvals,colnames=cols,format="fits")

