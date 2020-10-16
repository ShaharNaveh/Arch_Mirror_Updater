#!/usr/bin/env python
"""
Because there are sometimes issues with the arch mirrors, and if you don't want
to install a package like reflector. this is a small script to handle this.

NOTES
-----
You should really use reflector ;)
"""
import contextlib
import datetime
import json
import os
import sys
import urllib.request
import warnings
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Union

# Options
MAX_LAST_SYNC_HOURS = 6  # Lower is better
MAX_SCORE = 1  # Lower is better
MINIMUM_COMPLETION_PERCENTAGE = 1  # 1 = 100%
URL_BLACKLIST = {"mirrors.lug.mtu.edu", "mirror.rackspace.com"}

# Constants
MIRROR_LIST_PATH = "/etc/pacman.d/mirrorlist"
NOW = datetime.datetime.now()
URL = "https://www.archlinux.org/mirrors/status/json/"


def main():
    """
    The function that gets called, to assemble the pieces.

    Raises
    ------
    RuntimeError
        If the running platform is not linux.

        If the running user is not root.

    Warns
    -----
    RuntimeWarning
        * If the fetched data was not updated recently.

        * If there was no urls that stood up to the predefined standarts.
    """
    if not is_platform_linux():
        raise RuntimeError("The running platform is not linux")
    elif os.geteuid() != 0:
        raise RuntimeError("The user who is running the script needs to be root")

    DATA = load_data_from_url(url=URL)

    if is_outdated(timestamp=DATA["last_check"], time_format="%Y-%m-%dT%H:%M:%S.%fZ"):
        warnings.warn(
            "The number of hours since the last sync of the data,"
            f" is larger than {MAX_LAST_SYNC_HOURS}",
            RuntimeWarning,
        )

    have_failed = True
    mode = "w"

    for mirror_path in updated_urls(urls_data=DATA["urls"]):
        have_failed = False

        with open(MIRROR_LIST_PATH, mode=mode) as file_obj:
            file_obj.write(mirror_path)

        mode = "a"

    if have_failed:
        warnings.warn("The mirror list was not updated")


def is_platform_linux() -> bool:
    """
    Check if the running platform is linux.

    Returns
    -------
    bool
        Whether or not running on a linux platform.
    """
    return "linux" in sys.platform


def load_data_from_url(
    *, url: str
) -> Dict[
    str, Union[List[Dict[str, Optional[Union[bool, float, int, str]]]], int, str]
]:
    """
    Get the data from the received URL.

    Parameters
    ----------
    url : str
        URL to fetch the data from.

    Returns
    -------
    Dict
        Mapping of:
            cutoff : int
            last_check : str
            num_checks : int
            check_frequency : int
            urls : List[Dict]
                url : str
                protocol : str
                last_sync : str
                completion_pct : float
                delay : int
                duration_avg : float
                duration_stddev : float
                score : float
                active : bool
                country : str
                country_code : str
                isos : bool
                ipv4 : bool
                ipv6 : bool
                details : str
            version : int
    """
    with contextlib.closing(urllib.request.urlopen(url)) as response:
        fetched_data = response.read()

    decoded_data = fetched_data.decode()
    return json.loads(decoded_data)


def updated_urls(
    *,
    urls_data: List[Dict[str, List[Dict[str, Optional[Union[bool, float, int, str]]]]]],
) -> Iterable[str]:
    """
    Yields all the URLs that are up to the predefined standart

    Parameters
    ----------
    urls_data : List
        List of dictionaries with all the fetched information about the URL.

    Yields
    ------
    str
        Mirror path of the URL that is up to the predefined standarts.
    """
    for url_information in urls_data:
        if TYPE_CHECKING:
            assert isinstance(url_information["last_sync"], str)  # mypy needs this

        if any(slow_url in url_information["url"] for slow_url in URL_BLACKLIST):
            continue
        elif not url_information["active"]:
            continue
        elif url_information["protocol"] != "https":
            continue
        elif not url_information["completion_pct"] >= MINIMUM_COMPLETION_PERCENTAGE:
            continue
        elif url_information["score"] >= MAX_SCORE:
            continue
        elif is_outdated(
            timestamp=url_information["last_sync"], time_format="%Y-%m-%dT%H:%M:%SZ"
        ):
            continue

        yield f"Server = {url_information['url']}$repo/os/$arch\n"


def is_outdated(*, timestamp: str, time_format: str) -> bool:
    """
    Warn the user if the data is outdated

    Parameters
    ----------
    timestamp : str
        Datetime representation.
    time_format : str
        Time format to parse the received timestamp.

    Returns
    -------
    bool
        Whether or not the received time is outdated.
    """
    parsed = datetime.datetime.strptime(timestamp, time_format)
    result = NOW - parsed
    hours_since_last_sync = result.total_seconds() / 3600
    return hours_since_last_sync > MAX_LAST_SYNC_HOURS


if __name__ == "__main__":
    main()
