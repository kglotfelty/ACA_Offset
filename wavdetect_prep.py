
import os
import sys

import stk
from pycrates import read_file
from ciao_contrib.runtool import make_tool
import subprocess
from ciao_contrib._tools.taskrunner import TaskRunner


OBI_LIS = "c.lis"
IN_ROOT = "/Volumes/Chandra/Archive"


if not os.path.exists(IN_ROOT):
    os.makedirs( IN_ROOT )
    

def download(obsid):
    from ciao_contrib.cda.data import download_chandra_obsids
    ftypes = [ "evt1", "asol", "bpix", "dtf", "msk", "mtl",
                "dtf", "stat", "bias", "flt", "fov", "pbk"]
    
    if os.path.exists( os.path.join(obsid, "repro")):
        """Skip it if already has repro dir"""
        return
    
    good = download_chandra_obsids([obsid], filetypes=ftypes)
    if good[0] is not True:
        raise RuntimeError("Can't download "+obsid)
     

def repro(obsid):
    from ciao_contrib.runtool import make_tool

    if os.path.exists( os.path.join( obsid, "images" )):
        """Skip repro, already done"""
        return

    chandra_repro = make_tool("chandra_repro")
    v = chandra_repro( obsid, outdir="", cleanup=True, clobber=True)
    if v:
        open( os.path.join(obsid, "LOG.repro"), "w").write(v+"\n")
        

def check_obsid( obsid):
    
    from ciao_contrib._tools.utils import is_multi_obi_obsid

    if is_multi_obi_obsid(obsid):
        raise RuntimeError("Skipping -- multi-obi obsid "+obsid)

    mskfile=os.path.join(IN_ROOT, obsid, "secondary", "*msk1.fits*")
        
    try:
        msk = stk.build(mskfile)
    except:
        raise RuntimeError("Skipping -- no mask file for obsid "+obsid)
    
    if len(msk) != 1:
        raise RuntimeError("Skipping -- too many mask files for "+obsid)

    try:
        tab = read_file(msk[0])
    except:
        raise RuntimeError("Skipping -- can't read mask file "+obsid)
    
    #~ ver = tab.get_key_value("ASCDSVER")
    #~ if ver.startswith('8.1') or ver.startswith('8.2') or ver.startswith('8.3'):
        #~ raise RuntimeError("Skipping -- old version "+obsid)
    
    if not tab.get_key_value("OBS_MODE") == "POINTING":
        raise RuntimeError("Skipping -- not pointing "+obsid)
    
    if not tab.get_key_value("GRATING") == "NONE":
        raise RuntimeError("Skipping -- gratings "+obsid)

    if tab.get_key_value("INSTRUME") == "ACIS":
        if not tab.get_key_value("READMODE") == "TIMED":
            raise RuntimeError("Skipping -- not timed mode "+obsid)

        if not tab.get_key_value("DTYCYCLE") == 0:
            raise RuntimeError("Skipping -- interleaved "+obsid)
    
    return (tab.get_key_value("INSTRUME") == "HRC")

    
def find_evt(obsid, is_hrc=False):
    
    det = "hrc" if is_hrc is True else "acis"
    
    evtstk = os.path.join(IN_ROOT, obsid, "repro", det+"*evt2.fits")
    evtfiles = stk.build(evtstk)
    if len(evtfiles) != 1:
        raise RuntimeError("Foo")
    return evtfiles[0]



    
def make_images(obsid, evt, is_hrc=False):

    if os.path.exists( os.path.join( obsid, "wavdetect")):
        """Skip if already past onto wavdetect"""
        return

    outdir = os.path.join( IN_ROOT, obsid, "images" )
    os.makedirs( outdir, exist_ok=True )

    fi = make_tool("fluximage")
    fi.infile = evt
    fi.outroot = os.path.join( outdir, obsid )
    if is_hrc is True:
        fi.bands = "wide"
        fi.binsize = 4
    else:
        fi.bands = "broad"
        fi.binsize = 1
    fi.psfecf = 0.9
    fi.background = "none"
    v = fi(clobber=True, parallel=False)
    if v:
        open( os.path.join( outdir, "LOG"), "w").write(v+"\n")


def run_wavdetect(obsid, edition, skip_exist=False, is_hrc=False):

    imgdir = os.path.join( IN_ROOT, obsid, "images" )
    detdir = os.path.join( IN_ROOT, obsid, "wavdetect" )
    os.makedirs( detdir, exist_ok=True )

    
    band="wide" if is_hrc is True else "broad"
     
    # inputs
    img = obsid+"_"+band+"_thresh.img"
    exp = obsid+"_"+band+"_thresh.expmap"
    psf = obsid+"_"+band+"_thresh.psfmap"

    # outputs
    src = "{}_{}.src".format(obsid, edition)
    cel = "{}_{}.cell".format(obsid, edition)
    nbk = "{}_{}.nbkg".format(obsid, edition)
    rec = "{}_{}.recon".format(obsid, edition)

    if os.path.exists(os.path.join(detdir, src)) and True == skip_exist:
        return

    wavdetect = make_tool("wavdetect")
    wavdetect.infile = os.path.join(imgdir, img)
    wavdetect.psffile = os.path.join(imgdir, psf)
    wavdetect.expfile = os.path.join(imgdir, exp)

    wavdetect.outfile = os.path.join( detdir, src )
    wavdetect.scellfile = os.path.join( detdir, cel )
    wavdetect.imagefile = os.path.join( detdir, nbk )
    wavdetect.defnbkgfile = os.path.join( detdir, rec )

    wavdetect.scales = "1.4 2 4 8 12 16 32 48" 

    v = wavdetect(clobber=True)
    if v:
        open(os.path.join( detdir, "LOG."+edition),"w").write(v+"\n")
    
    #~ subprocess.run("gzip -f {}".format(wavdetect.scellfile).split(" "))
    #~ subprocess.run("gzip -f {}".format(wavdetect.imagefile).split(" "))
    #~ subprocess.run("gzip -f {}".format(wavdetect.defnbkgfile).split(" "))    


def doit_obsid_main(obsid):

    # Setup
    os.chdir(IN_ROOT)
    outtmp = os.path.join( IN_ROOT, obsid, "tmp" )
    os.makedirs( outtmp, exist_ok=True )
    os.environ["ASCDS_WORK_PATH"] = outtmp

    os.environ["PFILES"] = "{};{}:{}".format( outtmp,
             os.environ["ASCDS_INSTALL"]+"/param",
             os.environ["ASCDS_INSTALL"]+"/contrib/param")


    # Repro
    download(obsid)
    is_hrc = check_obsid(obsid)
    repro(obsid)
    evt = find_evt(obsid, is_hrc=is_hrc)

    # Analysis
    make_images( obsid, evt, is_hrc=is_hrc)
    run_wavdetect( obsid, "baseline", skip_exist=True, is_hrc=is_hrc)
 

def doit_obsid(obsid):
    try:
        print("Started "+obsid)
        doit_obsid_main(obsid)
        print("Finished "+obsid)
    except Exception as ee:
        print(ee)


obsids = stk.build("@-"+OBI_LIS)


taskrunner = TaskRunner()
for obsid in obsids:
    taskrunner.add_task( "OBS_ID="+obsid, "", doit_obsid, obsid )

taskrunner.run_tasks(processes=9)

