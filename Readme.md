
## Motivation

There is an issue in `wavdetect` where it can sometimes report
nearly identical sources.  The cause of this behavior is understood
however, the fix could fundamentally change the output.

I wanted to obtain a large baseline sample of current outputs before
suggesting any kind of fundamental change. The entire Chandra archive 
is a pretty good starting place.

## Selection

Observations were selected from the information in the `obs0a.par` files.

- Gratings data were excluded
- CC mode data were excluded
- Interleaved mode data were excluded
- Multi-obi obsids were excluded
- Some 128 row subarray datasets were excluded (see below)


## Source Lists

Ref: `wavdetect_prep.py`

Broad band source lists were generated using CIAO 4.11, CALDB 4.8.3, in 
the typical way:

1. `download_chandra_obsid` 
2. `chandra_repro`
3. `fluximage` with `psfecf=0.9`.  For HRC: `binsize=4`, ACIS: `binsize=1`
4. `wavdetect` with `scales="1.4 2 4 8 12 16 32 48"`

No post processing has been performed on the `wavdetect` source lists.

Note: at `scale=48`, the observations with 128row subarrays typically
had images that were too small and wavdetect would error out (nicely). 
Those observations are also not included.

Ref:  `Wavdetect/${obsid}/wavdetect/${obsid}_baseline.src`

## Identify Overlapping Fields

Using the `_PNT` values in the `obs0a.par` files, I identified obsids
whose aimpoints are within 20" of each other.  This was done 
separately for ACIS and HRC.

Ref: `FindOverlaps86grt.ipynb` and `FindOverlaps86grt_hrc.ipynb`

This is a simple $O(N\log(N))$ search algorithm.  Slow, but 
gets the job done.


The outputs are in [graphviz](https://www.graphviz.org/) format 
files: `match_no_tg.dat` and 
`match_no_tg_hrc.dat` .  It is a fairly simple text file to parse later.

For anyone who has read this far and wants to see pretty pictures take
a look at `foo_no_tg.png` and `foo_no_tg_hrc.png`.


## Crossmatch and compute offsets

For all the overlapping pairs identified in the previous step I
then ran `wcs_match` to perform a crossmatch and to compute the
offsets.

Ref: `Crossmatch_ACIS.ipynb` and `Crossmatch_HRC.ipynb`

All pairs of overlapping obsids with 1 or more sources ID were computed.

I used a conservative match `radius=2.0` (arcsec) and only allowed
for a translation, ie `method=trans`, ie 0 rotation and unity scaling.

Ref: `XMatch/${obsid1}_${obsid2}.xmatch`

Note: All pairs of matches were computed, so you will find both

```bash
XMatch/4396_4395.xmatch
XMatch/4395_4396.xmatch
```

## Final results: `merged_xforms.fits`


Combines the data from the individual `.xmatch` files into a single file.

```bash
% dmlist merged_xforms.fits cols
 
--------------------------------------------------------------------------------
Columns for Table Block TABLE
--------------------------------------------------------------------------------
 
ColNo  Name                 Unit        Type             Range
   1   obi1                              String[5]                           
   2   obi2                              String[5]                           
   3   t1                                Real8          -Inf:+Inf            
   4   t2                                Real8          -Inf:+Inf            
   5   ra_ref                            Real8          -Inf:+Inf            
   6   dec_ref                           Real8          -Inf:+Inf            
   7   roll_ref                          Real8          -Inf:+Inf            
   8   xpix_ref                          Real8          -Inf:+Inf            
   9   ypix_ref                          Real8          -Inf:+Inf            
  10   x_scale                           Real8          -Inf:+Inf            
  11   y_scale                           Real8          -Inf:+Inf            
```

- `obi1` the input obsid (`wcsmatch.infile`)
- `obi2` the reference obsid (`wcsmatch.refsrcfile` ) `t1` and `t2` are the offsets in physical pixel, sky(x,y), to shift `obi1` to match `obi2`.
- `ra_ref`, `dec_ref` reference of tangent plane (akin to `RA_NOM`, `DEC_NOM`), (ie `CRVAL` values)
- `roll_ref` akin to `ROLL_NOM`
- `xpix_ref`, `ypix_ref` center of sky image (eg ACIS=4096.5,4096.5), (ie `CRPIX` values)
- `x_scale`, `y_scale` (ie `CDELT` values) 


As was noted before, the offsets was done for all pairs of overlapping
sources, so for example we see both 4395 matched to 4396, and 4396 matched to 
4395:

```bash
%  dmlist merged_xforms.fits"[(obi1=4396,obi2=4395)||(obi1=4395,obi2=4396)][cols obi1,obi2,t1,t2]" data,clean
#  obi1    obi2    t1                   t2
 4395    4396        0.25994328718183     0.03118283130192
 4396    4395       -0.25994328739595    -0.03118282948746
```

and as we might hope the offsets are the same except in the opposite direction.


