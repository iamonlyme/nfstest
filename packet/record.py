#===============================================================================
# Copyright 2012 NetApp, Inc. All Rights Reserved,
# contribution by Jorge Mora <mora@netapp.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#===============================================================================
"""
Record module

Provides the object for a record and the string representation of the record
in a tcpdump trace file.

Record object attributes:
    Record(
        index       = Frame number
        length_inc  = Number of bytes included in trace
        length_orig = 1
        msecs       = 905320,
        seconds     = 1349747491,
        secs        = 4.165262937545776,
    )
"""
import nfstest_config as c
from baseobj import BaseObj

# Module constants
__author__    = 'Jorge Mora (%s)' % c.NFSTEST_AUTHOR_EMAIL
__version__   = '1.0.1'
__copyright__ = "Copyright (C) 2012 NetApp, Inc."
__license__   = "GPL v2"

class Record(BaseObj):
    """Record object

       Usage:
           from packet.record import Record

           x = Record()
    """
    def __str__(self):
        """String representation of object

           The representation depends on the verbose level set by debug_repr().
           If set to 0 the generic object representation is returned.
           If set to 1 the representation of the object is condensed to display
           the frame number and the timestamp:
               '57 0.530957 '

           If set to 2 the representation of the object also includes the number
           of bytes on the wire, number of bytes captured and a little bit more
           verbose:
               'frame 57 @ 0.530957 secs, 42 bytes on wire, 42 packet bytes'
        """
        rdebug = self.debug_repr()
        if rdebug == 1:
            out = "%d %f " % (self.index, self.secs)
        elif rdebug == 2:
            out = "frame %d @ %f secs, %d bytes on wire, %d packet bytes" % (self.index, self.secs, self.length_inc, self.length_orig)
        else:
            out = BaseObj.__str__(self)
        return out

