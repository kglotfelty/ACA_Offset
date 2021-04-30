#!/usr/bin/env python

'Run wavdetect on obsid'


import os
import sys

import stk
from ciao_contrib.runtool import make_tool


def download(obsid):
    'Download data from chandra public archive'

    from ciao_contrib.cda.data import download_chandra_obsids
    ftypes = ["evt1", "asol", "bpix", "dtf", "msk", "mtl",
              "dtf", "stat", "bias", "flt", "fov", "pbk"]

    if os.path.exists(os.path.join(obsid, "repro")):
        # Skip it if already has repro dir
        return

    good = download_chandra_obsids([obsid], filetypes=ftypes)
    if good[0] is not True:
        raise RuntimeError("Can't download "+obsid)


def repro(obsid):
    'Reprocess data'

    if os.path.exists(os.path.join(obsid, "images")):
        # Skip repro, already done
        return

    chandra_repro = make_tool("chandra_repro")
    verb = chandra_repro(obsid, outdir="", cleanup=True, clobber=True)
    if verb:
        open(os.path.join(obsid, "LOG.repro"), "w").write(verb+"\n")


def check_obsid(obsid):
    'Check that this is a good obsid'

    from ciao_contrib._tools.utils import is_multi_obi_obsid
    from pycrates import read_file

    if is_multi_obi_obsid(obsid):
        raise RuntimeError("Skipping -- multi-obi obsid "+obsid)

    mskfile = os.path.join(obsid, "secondary", "*msk1.fits*")

    try:
        msk = stk.build(mskfile)
    except Exception as bad:
        raise RuntimeError("Skipping -- no mask file for obsid "+obsid)

    if len(msk) != 1:
        raise RuntimeError("Skipping -- too many mask files for "+obsid)

    try:
        tab = read_file(msk[0])
    except Exception as bad:
        raise RuntimeError("Skipping -- can't read mask file "+obsid)

    # ~ ver = tab.get_key_value("ASCDSVER")
    # ~ if ver.startswith('8.1') or ver.startswith('8.2') or ver.startswith('8.3'):
        # ~ raise RuntimeError("Skipping -- old version "+obsid)

    if not tab.get_key_value("OBS_MODE") == "POINTING":
        raise RuntimeError("Skipping -- not pointing "+obsid)

    if not tab.get_key_value("GRATING") == "NONE":
        raise RuntimeError("Skipping -- gratings "+obsid)

    if tab.get_key_value("INSTRUME") == "ACIS":
        if not tab.get_key_value("READMODE") == "TIMED":
            raise RuntimeError("Skipping -- not timed mode "+obsid)

        if not tab.get_key_value("DTYCYCLE") == 0:
            raise RuntimeError("Skipping -- interleaved "+obsid)

    return tab.get_key_value("INSTRUME") == "HRC"


def find_evt(obsid):
    'Locate the evt2 file name'

    evtstk = os.path.join(obsid, "repro", "*_evt2.fits")
    evtfiles = stk.build(evtstk)
    if len(evtfiles) != 1:
        raise RuntimeError("Foo")
    return evtfiles[0]


def make_images(obsid, evt, is_hrc=False):
    'Create image. Also creates the exposure map and psfmap'

    if os.path.exists(os.path.join(obsid, "wavdetect")):
        # Skip if already past onto wavdetect
        return

    outdir = os.path.join(obsid, "images")
    os.makedirs(outdir, exist_ok=True)

    fimg = make_tool("fluximage")
    fimg.infile = evt
    fimg.outroot = os.path.join(outdir, obsid)
    if is_hrc is True:
        fimg.bands = "wide"
        fimg.binsize = 4
    else:
        fimg.bands = "broad"
        fimg.binsize = 1
    fimg.psfecf = 0.9
    fimg.background = "none"
    verb = fimg(clobber=True, parallel=False)
    if verb:
        open(os.path.join(outdir, "LOG"), "w").write(verb+"\n")


def run_wavdetect(obsid, edition, skip_exist=False, is_hrc=False):
    'Run wavdetect'

    imgdir = os.path.join(obsid, "images")
    detdir = os.path.join(obsid, "wavdetect")
    os.makedirs(detdir, exist_ok=True)

    band = "wide" if is_hrc is True else "broad"

    # inputs
    img = obsid+"_"+band+"_thresh.img"
    exp = obsid+"_"+band+"_thresh.expmap"
    psf = obsid+"_"+band+"_thresh.psfmap"

    # outputs
    root = f"{obsid}_{edition}"
    src = root + ".src"
    cel = root + ".cell"
    nbk = root + ".nbkg"
    rec = root + ".recon"

    if os.path.exists(os.path.join(detdir, src)) and skip_exist:
        return

    wavdetect = make_tool("wavdetect")
    wavdetect.infile = os.path.join(imgdir, img)
    wavdetect.psffile = os.path.join(imgdir, psf)
    wavdetect.expfile = os.path.join(imgdir, exp)

    wavdetect.outfile = os.path.join(detdir, src)
    wavdetect.scellfile = os.path.join(detdir, cel)
    wavdetect.imagefile = os.path.join(detdir, nbk)
    wavdetect.defnbkgfile = os.path.join(detdir, rec)

    wavdetect.scales = "1.4 2 4 8 12 16 32 48"

    verb = wavdetect(clobber=True)
    if verb:
        open(os.path.join(detdir, "LOG."+edition), "w").write(verb+"\n")

    # ~ import subprocess as subprocess
    # ~ subprocess.run("gzip -f {}".format(wavdetect.scellfile).split(" "))
    # ~ subprocess.run("gzip -f {}".format(wavdetect.imagefile).split(" "))
    # ~ subprocess.run("gzip -f {}".format(wavdetect.defnbkgfile).split(" "))


def doit_obsid_main(obsid):
    'Main routine to process a single obsid'

    # Setup
    outtmp = os.path.join(obsid, "tmp")
    os.makedirs(outtmp, exist_ok=True)
    os.environ["ASCDS_WORK_PATH"] = outtmp

    pf = "{};{}:{}".format(outtmp,
                           os.environ["ASCDS_INSTALL"]+"/param",
                           os.environ["ASCDS_INSTALL"]+"/contrib/param")
    os.environ["PFILES"] = pf

    # Repro
    download(obsid)
    is_hrc = check_obsid(obsid)
    repro(obsid)
    evt = find_evt(obsid)

    # Analysis
    make_images(obsid, evt, is_hrc=is_hrc)
    run_wavdetect(obsid, "baseline", skip_exist=True, is_hrc=is_hrc)


def doit_obsid(obsid):
    'Wrapper around main to catch exceptions'

    try:
        print("Started "+obsid)
        doit_obsid_main(obsid)
        print("Finished "+obsid)
    except Exception as bad:
        print(bad)


def main():
    'Main routine'
    from ciao_contrib._tools.taskrunner import TaskRunner

    if len(sys.argv) == 1 or len(sys.argv) > 3:
        raise RuntimeError("Usage: {} obi.lis [outdir]".format(sys.argv[0]))

    obi_lis = sys.argv[1]
    
    if os.path.exists(obi_lis):
        # '@-' builds stack but does not include path name
        obsids = stk.build("@-" + obi_lis)
    else:
        obsids = stk.build(obi_lis)

    if len(sys.argv) == 3:
        outdir = sys.argv[2]
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        os.chdir(outdir)

    taskrunner = TaskRunner()
    for obsid in obsids:
        taskrunner.add_task("OBS_ID="+obsid, "", doit_obsid, obsid)

    # '9' because the archive limits number of concurrent connections
    # from same IP address (well, it did when it was 'ftp').
    taskrunner.run_tasks(processes=9)


if __name__ == '__main__':
    main()
