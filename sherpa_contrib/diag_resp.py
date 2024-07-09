#
#  Copyright (C) 2024
#           Smithsonian Astrophysical Observatory
#
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301 USA.
#




""" Create diagonal RMF and flat ARF objects of value unity.

Helper routines for creating a diagonal RMF and flat ARF response
objects for various telescopes and instruments.
The default is to generate Chandra/ACIS responses for PI-type spectra
extracted from ACIS stowed background event files.

Examples
--------

>>> from sherpa_contrib.diag_resp import *
>>> diagrmf,flatarf = mkdiagresp()
>>>
>>> set_rmf(diagrmf, bkg_id=1)
>>> set_arf(flatarf, bkg_id=1)

or

>>> diagrmf,flatarf = mkdiagresp(refspec="bkg.pi")

or

>>> bkgspec = get_bkg()
>>> diagrmf,flatarf = mkdiagresp(refspec=bkgspec)

"""

__revision__ = "20 June 2024"

import os
import warnings
from logging import getLogger
from functools import wraps

import numpy.typing as npt
from numpy import arange
from ciao_contrib._tools.fileio import get_keys_from_file

from sherpa.astro.data import DataPHA, Data1DInt
from sherpa.astro.ui import create_rmf as shpmkrmf
from sherpa.astro.ui import create_arf as shpmkarf



def _reformat_wmsg(func):
    """
    Decorator:

    Trim extraneous user-warning information showing path and line number
    where Sherpa warning message is being thrown for replacing 0s with ethresh.
    """

    @wraps(func)
    def run_func(*args, **kwargs):
        warnings_reset = warnings.formatwarning
        warnings.formatwarning = lambda msg, *args_warn, **kwargs_warn: f'Warning: {msg}\n'

        func_out = func(*args,**kwargs)

        warnings.formatwarning = warnings_reset

        return func_out

    return run_func



def _quash_shpverb(func):
    """
    Decorator:

    Temporarily quash Sherpa verbosity.
    """

    def run_func(*args, **kwargs):
        sherpalog = getLogger("sherpa")
        loglevel = sherpalog.level
        sherpalog.setLevel(0)

        func_out = func(*args,**kwargs)

        sherpalog.setLevel(loglevel)

        return func_out

    return run_func



def _get_random_string(strlen: int = 16) -> str:
    from string import ascii_letters,digits
    from random import choices

    chars = ascii_letters + digits

    return ''.join(choices(chars, k=strlen))



@_quash_shpverb
def _get_file_header(fn) -> dict:
    from sherpa.astro.ui import load_pha,get_data,delete_data

    tmp_id = _get_random_string(strlen=32)

    load_pha(tmp_id,fn)
    hdr = get_data(tmp_id).header
    delete_data(tmp_id)

    return hdr



class EGrid:
    """
    gather together all information for non-Chandra setups and return the energy-grid.
    """

    def __init__(self, telescope, instrument, detector, instfilter, nchan, chantype):
        self.telescope = telescope
        self.instrument = instrument
        self.detnam = detector
        self.instfilter = instfilter

        self.subchan = nchan
        self.chantype = chantype

        if telescope.lower() == "chandra":
            self.elo,self.ehi,self.offset = self.get_acis_egrid(chantype=chantype)
        else:
            self.elo,self.ehi,self.offset = self.get_egrid(telescope = telescope,
                                                           instrument = instrument,
                                                           detnam = detector,
                                                           instfilter = instfilter,
                                                           subchan = nchan,
                                                           chantype = chantype)


    def _set_chantype_none(self, telescope: str = "",
                           instrument: str|None = None,
                           chantype: str|None=None):

        if telescope.lower() == "asca" and instrument.lower() != "gis":
            return chantype

        if telescope.lower() == "swift" and instrument.lower() == "xrt":
            return chantype

        if telescope.lower() == "xmm" and instrument.lower() == "epic":
            return chantype

        if telescope.lower() == "xrism" and instrument.lower() == "resolve":
            return chantype

        if telescope.lower() in ["chandra","calet"]:
            return chantype

        return None


    def _get_ebounds_blk(self, instrument: str|None = None,
                         detnam: str|None = None,
                         instfilter: str|None = None,
                         subchan: int|None = None,
                         chantype: str|None = None) -> str:

        detstr = f"{detnam:->{len(detnam)+1}}" if detnam is not None else ""
        filtstr = f"{instfilter:/>{len(instfilter)+1}}" if instfilter is not None else ""
        nchanstr = f"{subchan:_>{len(str(subchan))+1}}chan" if subchan is not None else ""
        chantypestr = f"_{chantype}" if chantype is not None else ""

        blkname = f"{instrument}{detstr}{filtstr}{nchanstr}{chantypestr}"

        return blkname


    def get_acis_egrid(self, chantype: str = "PI") -> tuple[npt.NDArray, npt.NDArray, int]:
        """
        return energy grid and channel offset for Chandra/ACIS detector
        """

        offset: int = 1

        chan = chantype.upper()

        if chan not in ["PI","PHA","PHA_no-CTIcorr"]:
            logger = getLogger(__name__)
            logger.warning("Warning: An invalid 'chantype' provided!  Assuming ACIS PI spectral channel type...")

        if chan.startswith("PHA"):
            detchans: int = 4096

            if chan == "PHA":
                ebin: float = 4.460 # eV CTI corrected
            else:
                ebin: float = 4.485 # eV non-CTI corrected
        else:
            detchans: int = 1024
            ebin: float = 14.6 # eV

        emin = arange(detchans) * (ebinkeV := ebin/1000) # in keV
        emax = emin + ebinkeV # in keV

        return emin, emax, offset


    def get_egrid(self, telescope: str = "",
                  instrument: str|None = None,
                  detnam: str|None = None,
                  instfilter: str|None = None,
                  subchan: int|None = None,
                  chantype: str|None = None) -> tuple[npt.NDArray, npt.NDArray, int]:
        """
        return energy grid and channel offset for a given telescope
        and instrument configuration
        """

        from sherpa.astro.io import backend as shp_backend

        fn = f"{os.environ['ASCDS_INSTALL']}/data/ebounds-lut/{telescope.lower()}-ebounds-lut.fits"

        chantype = self._set_chantype_none(telescope=telescope,
                                           instrument=instrument,
                                           chantype=chantype)

        blkname = self._get_ebounds_blk(instrument=instrument,
                                        detnam=detnam,
                                        instfilter=instfilter,
                                        subchan=subchan,
                                        chantype=chantype)

        try:
            if "pyfits" in shp_backend.__name__:
                from astropy.io import fits as aspy_fits

                with aspy_fits.open(fn) as hdul:
                    data = hdul[blkname].data

                    chan = data.CHANNEL
                    emin = data.E_MIN
                    emax = data.E_MAX

            else:
                from pycrates import read_file as pcr_readfile

                data = pcr_readfile(f"{fn}[{blkname}]")

                chan = data.CHANNEL.values.astype(int)
                emin = data.E_MIN.values.astype(float)
                emax = data.E_MAX.values.astype(float)

        except FileNotFoundError:
            raise ValueError("The specified 'telescope' parameter value is invalid; no corresponding lookup table is available.")


        offset = min(chan)

        del(shp_backend)
        del(data)

        egrid_unit = get_keys_from_file(f"{fn}[{blkname}]")["EUNIT"]

        if egrid_unit == "eV":
            ## convert eV to keV ##
            emin /=  1_000
            emax /=  1_000

        if egrid_unit == "MeV":
            ## convert MeV to keV ##
            emin *= 1_000
            emax *= 1_000

        if egrid_unit == "GeV":
            ## convert MeV to keV ##
            emin *= 1_000_000
            emax *= 1_000_000

        return emin, emax, offset



def _check_and_update_instrument_info(telescope: str = "",
                                      instrument: str|None = None,
                                      detnam: str|None = None,
                                      instfilter: str|None = None):
    """
    revise telescope/instrument configuration information to the
    minimal parameters required to obtain the necessary energy grid
    """

    if telescope == "" or telescope is None:
        raise ValueError("'telescope' parameter must be specified!")


    ### update telescopes with alternate names ###
    if telescope.upper() == "XTE":
        telescope = "RXTE"
    if telescope.upper() == "SAX":
        telescope = "BeppoSAX"
    if telescope.upper() == "EROSITA":
        telescope = "SRG"


    ### check for Chandra/HRC, which is barely suitable for crude hardness ratio estimates ###
    if telescope.lower() == "chandra" and instrument.upper() == "HRC":
        raise RuntimeWarning("non-grating HRC data has insufficient spectral resolution to be suitable for spectral fitting!")


    ### update telescopes with unique energy grid, even if there are multiple instruments ###
    if telescope.lower() == "cos-b":
        instrument = "COS-B"

    if telescope.lower() == "exosat":
        instrument = "CMA"

    if telescope.lower() == "halosat":
        instrument = "SDD"

    if telescope.lower() == "ixpe":
        instrument = "GPD"

    if telescope.lower() == "maxi":
        instrument = "GSC"

    if telescope.lower() == "nicer":
        instrument = "XTI"

    if telescope.lower() == "rosat":
        instrument = "PSPC"

    if telescope.lower() == "srg":
        instrument = "eROSITA"

    if telescope.lower() == "nustar": # and instrument.upper().startswith("FPM"):
        instrument = "FPM"

    if telescope.lower() == "einstein":
        if instrument is None or instrument.upper() not in ["HRI","IPC","SSS","MPC"]:
            raise ValueError("'telescope=Einstein' requires 'instrument' argument to be HRI|IPC|SSS|MPC")

        instrument = instrument.upper()

    ### set detector value to None for telescopes with only a single instrument ###
    if telescope.lower() in ["nustar","einstein","cos-b",
                             "exosat","halosat","ixpe",
                             "maxi","nicer","rosat","srg"]:
        detnam = None

    if telescope.lower() == "asca":
        if instrument is None or instrument.upper() not in ["GIS","SIS0","SIS1"]:
            raise ValueError("'telescope=ASCA' requires 'instrument' argument to be GIS|SIS0|SIS1")

        if instrument.upper().startswith("SIS"):
            if detnam is None or detnam.upper() not in ["CCD0","CCD1","CCD2","CCD3"]:
                raise ValueError("'telescope=ASCA' with 'instrument=SIS0|SIS1' requires the 'detector' argument to be CCD0|CCD1|CCD2|CCD3")

            detnam = detnam.upper()
        else:
            detnam = None


    if telescope.lower() == "bepposax":
        if instrument is None or instrument.upper() not in ["PDS","HPGSPC","LECS","MECS","WFC1","WFC2"]:
            raise ValueError("'telescope=BeppoSAX|SAX' requires 'instrument' argument to be PDS|HPGSPC|LECS|MECS|WFC1|WFC2")

        if instrument.upper() == "MECS":
            if detnam is None or detnam.upper() not in ["M1","M2","M3"]:
                raise ValueError("'telescope=BeppoSAX|SAX' with 'instrument=MECS' requires the 'detector' argument to be M1|M2|M3")

            detnam = detnam.upper()
        else:
            detnam = None


    if telescope.lower() == "calet":
        instrument = "GGBM"

        if detnam is not None and detnam.upper().startswith("HXM"):
            detnam = "HXM"

        if detnam is None or detnam.upper() not in ["HXM","SGM"]:
            raise ValueError("'telescope=CALET' requires 'detector' argument to be SGM|HXM")


    if telescope.lower() == "rxte":
        if instrument is None or instrument.upper() not in ["HEXTE","PCA"]:
            raise ValueError("'telescope=RXTE|XTE' requires 'instrument' argument to be PCA|HEXTE")

        if instrument.upper() == "HEXTE":
            if detnam is None or detnam.upper() not in ["PWA","PWB"]:
                raise ValueError("'telescope=RXTE|XTE' and 'instrument=HEXTE' requires 'detector' argument to be PWA|PWB")

            detnam = detnam.upper()
        else:
            detnam = None


    if telescope.lower() == "suzaku":
        if instrument is None or instrument.upper() not in ["HXD","XRS","XIS","XIS0","XIS1","XIS2","XIS3"]:
            raise ValueError("'telescope=Suzaku' requires 'instrument' argument to be XIS|XRS|HXD")

        if instrument.upper().startswith("XIS"):
            instrument = "XIS"

        if instrument.upper() == "HXD":
            if detnam is None or detnam.upper() not in ["WELL_GSO","WELL_PIN"]:
                raise ValueError("'telescope=Suzaku' with 'instrument=HXD' requires the 'detector' argument to be WELL_GSO|WELL_PIN")

            detnam = detnam.upper()
        else:
            detnam = None


    if telescope.lower() == "xmm":
        if instrument is None or instrument.upper() not in ["RGS","EPIC","EPN","EMOS1","EMOS2"]:
            raise ValueError("'telescope=XMM' requires 'instrument' argument to be EPIC|RGS")

        if instrument.upper() == "EPIC":
            if detnam is None or all([detnam.upper() != "PN", not detnam.upper().startswith("MOS")]):
                raise ValueError("'telescope=XMM' with 'instrument=EPIC' requires the 'detector' argument to be PN|MOS")

            if detnam.upper().startswith("MOS"):
                detnam = "MOS"

            detnam = detnam.upper()

        if instrument.upper() == "RGS":
            detnam = None

        if instrument.upper().startswith("EMOS"):
            instrument = "EPIC"
            detnam = "MOS"

        if instrument.upper().startswith("EPN"):
            instrument = "EPIC"
            detnam = "PN"


    if telescope.lower() == "swift":
        if instrument.upper() not in ["XRT","BAT","UVOTA","UVOT"]:
            raise ValueError("'telescope=Swift' requires 'instrument' argument to be XRT|BAT|UVOT")

        if instrument.upper().startswith("UVOT"):
            instrument = "UVOT"

        instrument = instrument.upper()
        detnam  = None


    ### setup 'instfilter' argument; only Swift/UVOT energy-grid is dependent on this quantity ###
    if telescope.lower() == "swift" and instrument.upper() == "UVOT":
        if instfilter.upper() not in ["B","V","U","UVM2","UVW1","UVW2","WHITE"]:
            raise ValueError("'telescope=Swift' with 'instrument=UVOT' requires the 'instfilter' argument to be B|V|U|UVM2|UVW1|UVW2|White")

        instfilter = instfilter.upper()

    else:
        instfilter = None


    return telescope, instrument, detnam, instfilter



@_reformat_wmsg
def build_resp(emin, emax, offset: int, ethresh: float|None=1e-12):
    """
    Return a diagonal RMF and flat ARF data objects with matching energy grid.
    Use set_rmf and set_arf on the respective instances.

    Parameters:
        emin - array of energy grid lower bin edge
        emax - array of energy grid upper bin edge
        offset - integer-value starting channel number, typically 0 or 1.
        ethresh - number or None, controls whether zero-energy bins are replaced.

    """

    logger = getLogger(__name__)

    try:
        flatarf = shpmkarf(emin, emax, ethresh=ethresh)
        diag_rmf = shpmkrmf(emin, emax, startchan=offset, ethresh=ethresh)

        #################################################################
        ### remove once 'startchan' is factored into channel enumeration
        ### in sherpa/astro/instrument.py

        if offset != 1:
            diag_rmf.f_chan += offset - 1

        #################################################################

    except Exception as exc:
        if repr(exc).find("value <= 0") != -1:

            raise RuntimeError(f"{exc.args[0]}.  Set 'ethresh' to a float value greater than zero and not None.") from None

        logger.warning(exc)
        raise RuntimeError(exc) from exc



    wmsg = "RMF and ARF data objects returned; use 'set_rmf' and 'set_arf' to set the respective instances to dataset ID."

    logger.warning("%s", f"\n{wmsg:>{len(wmsg)+4}}")


    return diag_rmf, flatarf



def mkdiagresp(telescope: str = "Chandra",
               instrument: str = "ACIS",
               detector: str|None = None,
               instfilter: str|None = None,
               refspec: str|DataPHA|None = None,
               chantype: str = "PI",
               nchan: int|None = None,
               ethresh: float|None = 1e-12):
    """
    Return a diagonal RMF and flat ARF data objects with matching energy grid for a specified instrument/detector.
    Use set_rmf and set_arf on the respective instances.  Use 'build_resp' for a non-instrument specific [or generalized] energy-grid configuration.

    "PI" channel-type is the default, assumed spectral type.


    Supported arguments:

        telescope="Chandra"
            instrument="ACIS"
            chantype="PI"|"PHA"|"PHA_no-CTIcorr"

        telescope="ASCA"
            instrument="GIS"
                nchan=[ 1024 | 256 | 128 ]

            instrument="SIS0"|"SIS1"
                detector="CCD0"|"CCD1"|"CCD2"|"CCD3"
                chantype="PI"|"PHA"
                nchan=[ 1024 | 512 ]

        telescope="BeppoSAX"|"SAX"
            instrument="WFC1"|"WFC2"|"HPGSPC"|"LECS"

            instrument="PDS"
                nchan=[ 256 | 128 | 60 ]

            instrument="MECS"
                detector="M1"|"M2"|"M3"

        telescope="CALET"
            instrument="GGBM"
                detector="SGM"|"HXM"
                chantype="GAIN_HI"|"GAIN_LO"

        telescope="COS-B"
            instrument="COS-B"

        telescope="Einstein"
            instrument="HRI"|"IPC"|"SSS"|"MPC"

        telescope="EXOSAT"
            instrument="CMA"

        telescope="HALOSAT"
            instrument="SDD"

        telescope="IXPE"
            instrument="GPD"

        telescope="MAXI"
            instrument="GSC"

        telescope="NICER"
            instrument="XTI"

        telescope="NuSTAR"
            instrument="FPM"

        telescope="ROSAT"
            instrument="PSPC"
            nchan=[ 256 | 34 ]

        telescope="RXTE"|"XTE"
            instrument="PCA"
                nchan=[ 256 | 6 ]

            instrument="HEXTE"
                detector="PWA"|"PWB"

        telescope="SRG"|"eROSITA"
            instrument="eROSITA"

        telescope="Suzaku"
            instrument="XIS"|"XRS"

            instrument="HXD"
                detector="WELL_GSO"|"WELL_PIN"

        telescope="Swift"
            instrument="BAT"

            instrument="XRT"
                chantype="PI"|"PHA"

            instrument="UVOT"
                instfilter="B"|"V"|"U"|"UVM2"|"UVW1"|"UVW2"|"WHITE"

        telescope="XMM"
            instrument="RGS"

            instrument="EPIC"
                detector="MOS"|"PN"
                chantype="PI"|"PHA"

        telescope="XRISM"
            instrument="XTEND"

            instrument="RESOLVE"
                chantype="lo-res"|"mid-res"|"hi-res"

    """

    if refspec is not None:
        if isinstance(refspec,str):
            # speckw = _get_file_header(refspec)
            speckw = get_keys_from_file(refspec)

        if isinstance(refspec,DataPHA):
            speckw = refspec.header

        for k,v in speckw.items():
            if isinstance(v,str) and v.lower() in ['none','']:
                speckw[k] = None

        telescope = speckw.get("TELESCOP")
        instrument = speckw.get("INSTRUME")
        detector = speckw.get("DETNAM")
        instfilter = speckw.get("FILTER")
        nchan = speckw.get("DETCHANS")
        chantype = speckw.get("CHANTYPE")


    if telescope.lower() == "chandra" and instrument.lower() == "acis" and chantype.lower() not in ["pi","pha","pha_no-cticorr"]:
        raise ValueError("Chandra/ACIS requires 'chantype' argument to be set to 'PI', 'PHA', or 'PHA_no-CTIcorr'.")

    if telescope.lower() == "calet" and chantype.lower() not in ["gain_lo","gain_hi"]:
        raise ValueError("CALET requires 'chantype' argument to be set to 'GAIN_HI' or 'GAIN_LO'.")

    if telescope.lower() == "xrism" and instrument.lower() == "resolve" and chantype.lower() not in ["lo-res","mid-res","hi-res"]:
        raise ValueError("XRISM RESOLVE requires 'chantype' argument to be set to 'lo-res', 'mid-res', or 'hi-res'.")


    ### run arguments check and update parameters to minimal information needed ###
    telescope, instrument, detector, instfilter = _check_and_update_instrument_info(telescope=telescope,
                                                                                    instrument=instrument,
                                                                                    detnam=detector,
                                                                                    instfilter=instfilter)


    ### instruments/detectors with more than one channel binning scheme ###
    multichan_resps_max = {"asca sis" : 1024,
                           "asca gis" : 1024,
                           "rosat pspc" : 256,
                           "rxte pca" : 256,
                           "bepposax pds" : 256
    }

    key = f"{telescope} {''.join(i for i in instrument if not i.isdigit())}".lower()

    if any([
            (chantest := multichan_resps_max.get(key)) is not None and chantest == nchan,
            key not in multichan_resps_max
    ]):
        nchan = None


    ### return energy grid and first enumerated spectral channel ###
    egrid = EGrid(telescope, instrument, detector,
                  instfilter, nchan, chantype)

    elo = egrid.elo
    ehi = egrid.ehi
    offset = egrid.offset


    return build_resp(emin=elo, emax=ehi, offset=offset, ethresh=ethresh)
