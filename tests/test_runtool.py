"""Basic tests of the runtool interface"""

import os
import pathlib

import pytest

import ciao_contrib.runtool as rt


ALL_TOOLS = rt.list_tools()
SPECIAL_TOOLS = ['axbary', 'dmgti', 'evalpos', 'fullgarf',
                 'mean_energy_map', 'pileup_map', 'tgdetect',
                 'wavdetect']
PAR_TOOLS = ['ardlib', 'colors', 'dax', 'geom', 'imagej_lut', 'lut', 'ximage_lut']

STANDARD_TOOLS = list(set(ALL_TOOLS) - set(SPECIAL_TOOLS) - set(PAR_TOOLS))


# The current tests assume a conda-installed CIAO environment
#
ASCDS_INSTALL = pathlib.Path(os.getenv('ASCDS_INSTALL'))


def test_have_ascds_install():
    """Needed for other tests"""

    assert ASCDS_INSTALL.is_dir()


def test_expected_tools():
    assert len(ALL_TOOLS) == 179
    assert len(STANDARD_TOOLS) == 164


@pytest.mark.parametrize("expected", STANDARD_TOOLS)
def test_expected_standard(expected):
    tool1 = getattr(rt, expected)
    assert isinstance(tool1, rt.CIAOToolParFile)

    tool2 = rt.make_tool(expected)
    assert isinstance(tool2, rt.CIAOToolParFile)

    assert tool1 != tool2
    assert str(tool1) == str(tool2)

    out = f'<CIAO tool: {expected}>'
    assert repr(tool1) == out
    assert repr(tool2) == repr(tool1)


@pytest.mark.parametrize("expected", SPECIAL_TOOLS)
def test_expected_special(expected):
    tool1 = getattr(rt, expected)
    assert isinstance(tool1, rt.CIAOToolDirect)

    tool2 = rt.make_tool(expected)
    assert isinstance(tool2, rt.CIAOToolDirect)

    assert tool1 != tool2
    assert str(tool1) == str(tool2)

    out = f'<CIAO tool: {expected}>'
    assert repr(tool1) == out
    assert repr(tool2) == repr(tool1)


@pytest.mark.parametrize("expected", PAR_TOOLS)
def test_expected_par(expected):
    tool1 = getattr(rt, expected)
    assert isinstance(tool1, rt.CIAOParameter)

    tool2 = rt.make_tool(expected)
    assert isinstance(tool2, rt.CIAOParameter)

    assert tool1 != tool2
    assert str(tool1) == str(tool2)

    out = f'<CIAO parameter file: {expected}>'
    assert repr(tool1) == out
    assert repr(tool2) == repr(tool1)


def test_error_on_invalid_attribute():
    with pytest.raises(AttributeError) as ae1:
        rt.dmstat.foo = 1

    emsg = "There is no parameter for dmstat that matches 'foo'"
    assert str(ae1.value) == emsg

    tool = rt.make_tool('dmstat')
    with pytest.raises(AttributeError) as ae2:
        tool.foo = 1

    assert str(ae2.value) == emsg


def test_error_on_int_parameter_too_low():
    with pytest.raises(ValueError) as ve1:
        rt.dmstat.maxiter = 0

    emsg = "dmstat.maxiter must be >= 1 but set to 0"
    assert str(ve1.value) == emsg

    tool = rt.make_tool('dmstat')
    with pytest.raises(ValueError) as ve2:
        tool.maxiter = 0

    assert str(ve2.value) == emsg


def test_error_on_int_parameter_too_high():
    with pytest.raises(ValueError) as ve1:
        rt.dmstat.verbose = 6

    emsg = "dmstat.verbose must be <= 5 but set to 6"
    assert str(ve1.value) == emsg

    tool = rt.make_tool('dmstat')
    with pytest.raises(ValueError) as ve2:
        tool.verbose = 6

    assert str(ve2.value) == emsg


def test_error_on_real_parameter_too_low():
    with pytest.raises(ValueError) as ve1:
        rt.vtpdetect.mincutoff = -1

    emsg = "vtpdetect.mincutoff must be >= 0 but set to -1"
    assert str(ve1.value) == emsg

    tool = rt.make_tool('vtpdetect')
    with pytest.raises(ValueError) as ve2:
        tool.mincutoff = -1

    assert str(ve2.value) == emsg


def test_error_on_real_parameter_too_high():
    with pytest.raises(ValueError) as ve1:
        rt.vtpdetect.mincutoff = 30

    emsg = "vtpdetect.mincutoff must be <= 10 but set to 30"
    assert str(ve1.value) == emsg

    tool = rt.make_tool('vtpdetect')
    with pytest.raises(ValueError) as ve2:
        tool.mincutoff = 30

    assert str(ve2.value) == emsg


def test_parameter_check_is_case_sensitive():

    with pytest.raises(AttributeError) as ae1:
        rt.dmstat.CENTROID

    emsg = "There is no parameter for dmstat that matches 'CENTROID'"

    assert str(ae1.value) == emsg

    with pytest.raises(AttributeError) as ae2:
        rt.make_tool('dmstat').CENTROID

    assert str(ae2.value) == emsg


@pytest.mark.parametrize("requested,expected",
                         [("centroi", "centroid"),
                          ("cent", "centroid"),
                          ("cen", "centroid"),
                          ("ce", "centroid"),
                          ("med", "median"),
                          ("inf", "infile")])
def test_dmstat_parameter_match(requested, expected):
    """Check we can use unique name subsets"""

    a1 = getattr(rt.dmstat, requested)
    a2 = getattr(rt.make_tool('dmstat'), requested)

    b = getattr(rt.dmstat, expected)
    if b is None:
        assert a1 is None
        assert a2 is None
    else:
        assert a1 == b
        assert a2 == b


def test_dmstat_parameter_match_not_unique():

    with pytest.raises(AttributeError) as ae1:
        rt.dmstat.c

    emsg = "Multiple matches for dmstat parameter 'c', choose from:\n" + \
        "  centroid clip"

    assert str(ae1.value) == emsg

    with pytest.raises(AttributeError) as ae2:
        rt.make_tool('dmstat').c

    assert str(ae2.value) == emsg


@pytest.mark.parametrize('val', [True, 1, "yes", "YES", "true", "NO", "false", "on", "off"])
def test_set_boolean_true(val):
    """We include a number of settings that user might expect would be false!"""
    tool = rt.make_tool('dmstat')
    assert not tool.median

    tool.median = val
    assert tool.median


@pytest.mark.parametrize('val', [False, 0, "no"])
def test_set_boolean_false(val):
    tool = rt.make_tool('dmstat')
    assert tool.sigma

    tool.sigma = val
    assert not tool.sigma


def test_reset_params():
    """We can set and reset values"""

    tool = rt.make_tool('dmstat')
    orig = str(tool)

    def check():
        assert tool.infile is None
        assert tool.centroid
        assert tool.nsigma == pytest.approx(3)
        assert tool.maxiter == 20
        assert tool.out_mean is None

    check()

    infile = 'foo/bar/bax[energy=2:3, sky=region(bob.reg)][bin sky=::4]'
    tool.infile = infile
    tool.centroid = False
    tool.nsigma = 2.5
    tool.maxiter = 2

    assert tool.infile == infile
    assert not tool.centroid
    assert tool.nsigma == pytest.approx(2.5)
    assert tool.maxiter == 2
    assert tool.out_mean is None

    text = str(tool)
    assert text != orig

    lines = text.split('\n')
    assert len(lines) == 28
    assert lines[0] == 'Parameters for dmstat:'
    assert lines[1] == ''
    assert lines[2] == 'Required parameters:'
    assert lines[3] == f'              infile = {infile}  Input file specification'
    assert lines[4] == ''
    assert lines[5] == 'Optional parameters:'
    assert lines[6] == '            centroid = False            Calculate centroid if image?'

    assert lines[10] == '              nsigma = 2.5              Number of sigma to clip'
    assert lines[11] == '             maxiter = 2                Maximum number of iterations'

    assert lines[18] == '            out_mean =                  Output Mean Value'

    tool.punlearn()
    assert str(tool) == orig
    check()


@pytest.mark.parametrize("toolname", STANDARD_TOOLS)
def test_write_parfile_standard(toolname, tmp_path):

    if toolname in ['arfcorr', 'dmimg2jpg', 'mkgarf', 'mkgrmf', 'simulate_psf']:
        pytest.skip(f'tool {toolname} has problems')

    parfile = tmp_path / f'standard.{toolname}.par'

    tool = rt.make_tool(toolname)
    assert not parfile.exists()
    tool.write_params(str(parfile))
    assert parfile.exists()

    cts = parfile.read_text()

    # why are these three special? Probably MIT heritege/
    #
    if toolname in ['mkarf', 'mkexpmap', 'mkinstmap']:
        assert 'mode,s,h,"hl",ql|hl|q|h,,' in cts
    else:
        assert 'mode,s,h,"hl",,,' in cts

    # It would be nice to compare to the "default" values
    # but the conversion isn't perfect, so the following has
    # many failures I don't want to address right now.
    #
    orig = ASCDS_INSTALL / 'param' / f'{toolname}.par'
    assert orig.is_file()

    cts2 = open(orig, 'rt').read()

    assert ('mode,s,h,"ql",,,' in cts2) or \
        ('mode,s,h,ql,,,' in cts2) or \
        ('mode,s,h,ql' in cts2) or \
        ('mode,s,h,"h",,,' in cts2) or \
        ('mode,s,h,"ql",ql|hl|q|h,,' in cts2)

    cts = [l for l in cts.split('\n') if not l.startswith('mode,')]
    cts2 = [l for l in cts2.split('\n') if not l.startswith('mode,')]

    wrong = []
    for a, b in zip(cts, cts2):
        if a.strip() == b.strip():
            continue

        print(a.strip())
        print(b.strip())
        wrong.append((a, b))

    # This is ugly - it would be nice to check the actual differences
    # but that's a lot of work
    #
    nwrong = len(wrong)
    if toolname == 'acis_find_afterglow':
        assert nwrong == 2
    elif toolname == 'acis_process_events':
        assert nwrong == 1
    elif toolname == 'acis_streak_map':
        assert nwrong == 2
    elif toolname == 'acisreadcorr':
        assert nwrong == 4
    elif toolname == 'aprates':
        assert nwrong == 15
    elif toolname == 'asphist':
        assert nwrong == 2
    elif toolname == 'arestore':
        assert nwrong == 2
    elif toolname == 'celldetect':
        assert nwrong == 1
    elif toolname == 'combine_grating_spectra':
        assert nwrong == 2
    elif toolname == 'combine_spectra':
        assert nwrong == 1
    elif toolname == 'correct_periscope_drift':
        assert nwrong == 3
    elif toolname == 'destreak':
        assert nwrong == 2
    elif toolname == 'dmcoords':
        assert nwrong == 14
    elif toolname == 'dmellipse':
        assert nwrong == 2
    elif toolname == 'dmextract':
        assert nwrong == 1
    elif toolname == 'dmmakepar':
        assert nwrong == 3
    elif toolname == 'dmhistory':
        assert nwrong == 1
    elif toolname == 'dmimgadapt':
        assert nwrong == 2
    elif toolname == 'dmimgblob':
        assert nwrong == 1
    elif toolname == 'dmimglasso':
        assert nwrong == 6
    elif toolname == 'dmimgpick':
        assert nwrong == 1
    elif toolname == 'dmimgthresh':
        assert nwrong == 1
    elif toolname == 'dmkeypar':
        assert nwrong == 2
    elif toolname == 'dmreadpar':
        assert nwrong == 3
    elif toolname == 'dmregrid':
        assert nwrong == 1
    elif toolname == 'dmregrid2':
        assert nwrong == 5
    elif toolname == 'dmtcalc':
        assert nwrong == 1
    elif toolname == 'download_obsid_caldb':
        assert nwrong == 3
    elif toolname == 'ecf_calc':
        assert nwrong == 1
    elif toolname == 'eff2evt':
        assert nwrong == 1
    elif toolname == 'find_chandra_obsid':
        assert nwrong == 5
    elif toolname == 'get_src_region':
        assert nwrong == 3
    elif toolname == 'glvary':
        assert nwrong == 1
    elif toolname == 'hrc_build_badpix':
        assert nwrong == 4
    elif toolname == 'hrc_process_events':
        assert nwrong == 8
    elif toolname == 'imgmoment':
        assert nwrong == 15
    elif toolname == 'make_psf_asymmetry_region':
        assert nwrong == 3
    elif toolname == 'mkacisrmf':
        assert nwrong == 4
    elif toolname == 'mkarf':
        assert nwrong == 2
    elif toolname == 'mkpsfmap':
        assert nwrong == 3
    elif toolname == 'mkrmf':
        assert nwrong == 1
    elif toolname == 'modelflux':
        assert nwrong == 1
    elif toolname == 'monitor_photom':
        assert nwrong == 1
    elif toolname == 'mtl_build_gti':
        assert nwrong == 1
    elif toolname == 'obsid_search_csc':
        assert nwrong == 3
    elif toolname == 'pfold':
        assert nwrong == 1
    elif toolname == 'psf_project_ray':
        assert nwrong == 2
    elif toolname == 'psfsize_srcs':
        assert nwrong == 1
    elif toolname == 'rank_roi':
        assert nwrong == 1
    elif toolname == 'reproject_image':
        assert nwrong == 2
    elif toolname == 'reproject_image_grid':
        assert nwrong == 6
    elif toolname == 'roi':
        assert nwrong == 1
    elif toolname == 'search_csc':
        assert nwrong == 3
    elif toolname == 'srcflux':
        assert nwrong == 1
    elif toolname == 'tg_create_mask':
        assert nwrong == 40
    elif toolname == 'tg_resolve_events':
        assert nwrong == 5
    elif toolname == 'tgidselectsrc':
        assert nwrong == 1
    elif toolname == 'wrecon':
        assert nwrong == 1
    elif toolname == 'wtransform':
        assert nwrong == 1
    else:
        assert nwrong == 0


@pytest.mark.parametrize("toolname", SPECIAL_TOOLS)
def test_write_parfile_special(toolname, tmp_path):

    parfile = tmp_path / f'special.{toolname}.par'

    tool = rt.make_tool(toolname)
    assert not parfile.exists()
    tool.write_params(str(parfile))
    assert parfile.exists()

    cts = parfile.read_text()

    assert 'mode,s,h,"hl",,,' in cts

    # It would be nice to compare to the "default" values
    # but the conversion isn't perfect, so the following has
    # many failures I don't want to address right now.
    #
    orig = ASCDS_INSTALL / 'param' / f'{toolname}.par'
    assert orig.is_file()

    cts2 = open(orig, 'rt').read()

    assert ('mode,s,h,"ql",,,' in cts2) or \
        ('mode,s,h,ql' in cts2)

    cts = [l for l in cts.split('\n') if not l.startswith('mode,')]
    cts2 = [l for l in cts2.split('\n') if not l.startswith('mode,')]

    wrong = []
    for a, b in zip(cts, cts2):
        if a.strip() == b.strip():
            continue

        print(a.strip())
        print(b.strip())
        wrong.append((a, b))

    # This is ugly - it would be nice to check the actual differences
    # but that's a lot of work
    #
    nwrong = len(wrong)
    if toolname == 'dmgti':
        assert nwrong == 1
    elif toolname == 'evalpos':
        assert nwrong == 1
    elif toolname == 'mean_energy_map':
        assert nwrong == 1
    elif toolname == 'tgdetect':
        assert nwrong == 4
    elif toolname == 'wavdetect':
        assert nwrong == 2
    else:
        assert nwrong == 0


@pytest.mark.parametrize("toolname", PAR_TOOLS)
def test_write_parfile_par(toolname, tmp_path):

    parfile = tmp_path / f'par.{toolname}.par'

    tool = rt.make_tool(toolname)
    assert not parfile.exists()
    tool.write_params(str(parfile))
    assert parfile.exists()

    cts = parfile.read_text()

    assert ('mode,s,h,"hl",,,' in cts) or \
        ('mode,s,h,"hl",ql|hl|q|h,,' in cts)

    # It would be nice to compare to the "default" values
    # but the conversion isn't perfect, so the following has
    # many failures I don't want to address right now.
    #
    orig = ASCDS_INSTALL / 'param' / f'{toolname}.par'
    assert orig.is_file()

    cts2 = open(orig, 'rt').read()

    print([l for l in cts2.split('\n') if l.startswith('mode')])

    if toolname in ['ardlib', 'dax', 'geom']:
        assert ('mode,s,h,"ql",,,' in cts2) or \
            ('mode,s,h,"h",,,' in cts2) or \
            ('mode,s,h,h,,,' in cts2) or \
            ('mode,s,h,"hl","ql|hl|q|h",,' in cts2)
    else:
        assert '\nmode,' not in cts2

    cts = [l for l in cts.split('\n') if not l.startswith('mode,')]
    cts2 = [l for l in cts2.split('\n') if not l.startswith('mode,')]

    wrong = []
    for a, b in zip(cts, cts2):
        if a.strip() == b.strip():
            continue

        print(a.strip())
        print(b.strip())
        wrong.append((a, b))

    # This is ugly - it would be nice to check the actual differences
    # but that's a lot of work
    #
    nwrong = len(wrong)
    if toolname == 'dmgti':
        assert nwrong == 1
    elif toolname == 'evalpos':
        assert nwrong == 1
    elif toolname == 'mean_energy_map':
        assert nwrong == 1
    elif toolname == 'tgdetect':
        assert nwrong == 4
    elif toolname == 'wavdetect':
        assert nwrong == 2
    else:
        assert nwrong == 0
