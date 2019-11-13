#
#  Copyright (C) 2011, 2014, 2015, 2016, 2019
#            Smithsonian Astrophysical Observatory
#
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Access the CIAO version (both installed and latest available).

Query either the local installation for the installed version
of CIAO, or find out the latest released version by querying
the CXC website.
"""

import glob
import os
import socket

from urllib.request import urlopen
from urllib.error import URLError

from ciao_contrib import logger_wrapper as lw


__all__ = ('get_installed_versions', 'get_latest_versions',
           'read_latest_versions')


# Note: at the moment the check_ciao_version tool does not
#       set up a logger or its verbosity.
#
lgr = lw.initialize_module_logger('_tools.versioninfo')
v3 = lgr.verbose3
v4 = lgr.verbose4


def read_vfile(fname):
    "Reads the version string from a CIAO version file"
    fh = open(fname, "r")
    cts = fh.readlines()
    fh.close()

    # Just take the first line, in case there are any extra new lines
    # in the file, as has happened.
    return cts[0].strip()


def package_name(fname):
    """Return the package name for the given file name"""

    if fname == "VERSION":
        return "CIAO"

    elif fname == "contrib/VERSION.CIAO_scripts":
        return "contrib"

    elif fname.find("_") != -1:
        return fname.split("_")[-1]

    else:
        raise ValueError("Unrecognized file name: {0}".format(fname))


def get_installed_versions(ciao):
    """Return a dictionary of (name, version) pairs for the installed
    CIAO packages, where ciao is the base of the CIAO installation
    (i.e. the value of the $ASCDS_INSTALL environment variable).

    """

    vbase = glob.glob(ciao + "/VERSION")
    if vbase == []:
        raise IOError("Unable to find $ASCDS_INSTALL/VERSION")

    # assume there is at least one installed package
    #
    vfiles = glob.glob(ciao + "/VERSION_*")
    if vfiles == []:
        raise IOError("Unable to find $ASCDS_INSTALL/VERSION_*")

    # do not require the contrib package
    #
    cfile = glob.glob(ciao + "/contrib/VERSION*")

    l = len(ciao) + 1
    return dict([(package_name(vfile[l:]), read_vfile(vfile))
                 for vfile in vbase + vfiles + cfile])


def parse_version_file(lines):
    """Given a list of lines, return the parsed contents,
    assuming each line is either empty or

      '<file-head> <version text>'

    Returns a dictionary (key=file-head, value=version text).
    """

    out = {}
    for l in lines:
        l = l.strip()
        if l == "":
            continue
        idx = l.find(" ")
        if idx == -1:
            raise IOError("Unable to parse line: '{0}'".format(l))

        else:
            k = l[:idx]
            v = l[idx + 1:]
            if k in out:
                raise ValueError("Multiple copies of {0} found.".format(k))

            else:
                out[k] = v

    return out


# def find_ciao_system():
#     """Return the CIAO system value.
#
#     Returns
#     -------
#     system : str
#         The system type. This matches the SYS field from the
#         ciao-control file used by ciao-install.
#
#     Notes
#     -----
#     This is just a simple wrapper around the ciao-type tool.
#     """
#
#     ans = sbp.Popen(["ciao-type"], stdout=sbp.PIPE)
#     ans.wait()
#     if ans.returncode != 0:
#         # is this necessary?
#         raise IOError("Unable to run ciao-type")
#
#     text = ans.stdout.read()
#
#     # Ugly code; what is the better way to do this
#     if not isinstance(text, str):
#         text = text.decode('utf8')
#
#     return text.strip()


def find_ciao_system():
    """Return the CIAO system value.

    Returns
    -------
    system : str
        The system type. This matches the SYS field from the
        ciao-control file used by ciao-install.

    Notes
    -----
    The ciao-type tool does not seem to return the Python version,
    i.e. it does not distinguish the "P3*" variants. So the
    contents of $ASCDS_INSTALL/ciao-type are used.
    """

    # assume that ASCDS_INSTALL is defined
    filename = os.path.join(os.getenv("ASCDS_INSTALL"), "ciao-type")
    with open(filename, "r") as fh:
        cts = fh.read()

    return cts.strip()


def get_url_contents(url, timeout=None):
    """Return the contents of the URL or a "friendly" error message.

    Parameters
    ----------
    url : str
        The URL to access.
    timeout : optional
        The timeout parameter for the urlopen call; if not
        None then the value is in seconds.

    Returns
    -------
    res : dict
        If the call was successful then the result will be a dict
        with the key 'contents', and its value is the contents of
        the URL as a string. If there was an error then the keys
        will be 'errortext' and 'is404', where the former is a string
        (to use in an IOError exception) and 'is404' is True
        if this was a 404 error (i.e. the file did not exist).

    """

    v3("querying URL={} timeout={}".format(url, timeout))

    try:
        if timeout is None:
            contents = urlopen(url).read()
        else:
            contents = urlopen(url, timeout=timeout).read()

    except URLError as ue:
        # Probably excessive attempt to make a "nice" error message
        #
        out = {'is404': False}
        try:
            if ue.getcode() == 404:
                out['errortext'] = "The CIAO version file " + \
                    "appears to be unreachable."
                out['is404'] = True
            elif ue.reason.errno == socket.EAI_NONAME:
                out['errortext'] = "Unable to reach the CIAO " + \
                    "site - is the network down?"
            else:
                out['errortext'] = "Unable to reach the CIAO " + \
                    "site - {}".format(ue.reason)

        except Exception:
            pass

        if 'errortext' not in out:
            out['errortext'] = "Unable to access the CIAO " + \
                "version file - {}".format(ue)

        return out

    # Ugly code; what is the better way to do this
    if not isinstance(contents, str):
        contents = contents.decode('utf8')

    return {'contents': contents}


def get_latest_versions(timeout=None, system=None):
    """Return the latest-released version of CIAO packages.

    This call requires internet access and the ability to
    query pages at http://cxc.harvard.edu/ciao/download/.

    Parameters
    ----------
    timeout : optional
        The timeout parameter for the urlopen call; if not
        None then the value is in seconds.
    system : optional
        The system to check for (e.g. "Linux64", "LinuxU",
        "osxSierra", ...). It should match the SYS value from the
        ciao-control file used by ciao-install. If set to None then
        the system from the CIAO installation is used.

    Returns
    -------
    versioninfo : dict
        The keys are the package name and the values are the
        latest released version for that package.

    Raises
    ------
    IOError
        Various HTTP-related errors are caught and converted to
        IOError exceptions, with the aim of providing more
        user-friendly errors.

    Notes
    -----
    The package names are those returned by the ciaover tool when
    run with the -v option, but in lower case, and the version
    strings have the form:

        <package> <version> <day>, <month> <day of month>, <year>

    where <version> has the form "a.b" or "a.b.c".
    """

    if system is None:
        system = find_ciao_system()

    v3("get_latest_versions for system={}".format(system))

    # To allow for a system-agnostic version file, check for
    # the version-specific and then drop back to the
    # version-agnostic only if it does not exist. Is this OTT?
    #
    base_url = "http://cxc.harvard.edu/ciao/download/"
    system_url = base_url + "ciao_versions.{}.dat".format(system)
    simple_url = base_url + "ciao_versions.dat"

    res = get_url_contents(system_url, timeout)
    if 'is404' in res and res['is404']:
        res = get_url_contents(simple_url, timeout)

    if 'errortext' in res:
        raise IOError(res['errortext'])

    contents = res['contents']
    return parse_version_file(contents.splitlines())


def read_latest_versions(filename):
    """Read the versions of the latest CIAO packages from the input
    file. The return value is an array of (name, version) strings.

    """

    with open(filename, "r") as fh:
        return parse_version_file(fh.readlines())
