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
Unpack module

Provides the object for managing and unpacking raw data from a working buffer.
"""
import struct
import nfstest_config as c

# Module constants
__author__    = 'Jorge Mora (%s)' % c.NFSTEST_AUTHOR_EMAIL
__version__   = '1.0.5'
__copyright__ = "Copyright (C) 2012 NetApp, Inc."
__license__   = "GPL v2"

class Unpack(object):
    """Unpack object

       Usage:
           from packet.unpack import Unpack

           x = Unpack(buffer)

           # Get the 32 bytes from the working buffer
           data = x.rawdata(32)

           # Unpack an 'unsigned short' (2 bytes)
           short_int = x.unpack(2, 'H')[0]

           # Unpack different basic types
           char_int  = x.unpack_char()
           short_int = x.unpack_short()
           uint      = x.unpack_uint()
           uint64    = x.unpack_uint64()
           data1     = x.unpack_opaque()
           data2     = x.unpack_opaque(64)  # Length of opaque must be <= 64
           data3     = x.unpack_fopaque(32)

           # Get string where length is given as an unsigned integer
           buffer = x.unpack_string()
           # Get string of fixed length
           buffer = x.unpack_string(32)
           # Get string where length is given as a short integer
           buffer = x.unpack_string(Unpack.unpack_short)
           buffer = x.unpack_string(ltype=Unpack.unpack_short)
           # Get string padded to a 4 byte boundary, discard padding bytes
           buffer = x.unpack_string(pad=4)

           # Get an array of integers
           alist = x.unpack_array()
           # Get a fixed length array of integers
           alist = x.unpack_array(ltype=10)
           # Get an array of short integers
           alist = x.unpack_array(Unpack.unpack_short)
           # Get an array of strings, the length of the array is given
           # by a short integer
           alist = x.unpack_array(Unpack.unpack_string, Unpack.unpack_short)
           # Get an array of strings, the length of each string is given by
           # a short integer and each string is padded to a 4 byte boundary
           alist = x.unpack_array(Unpack.unpack_string, args={'ltype':Unpack.unpack_short, 'pad':4})
           # Get an array of objects decoded by item_obj where the first
           # argument to item_obj is the unpack object, e.g., item = item_obj(x)
           alist = x.unpack_array(item_obj)

           # Get a list of integers
           alist = x.unpack_list()
           # Get a list of short integers
           alist = x.unpack_list(Unpack.unpack_short)
           # Get a list of strings, the next item flag is given
           # by a short integer
           alist = x.unpack_list(Unpack.unpack_string, Unpack.unpack_short)
           # Get a list of strings, the length of each string is given by
           # a short integer and each string is padded to a 4 byte boundary
           alist = x.unpack_list(Unpack.unpack_string, args={'ltype':Unpack.unpack_short, 'pad':4})
    """
    def __init__(self, data):
        """Constructor

           Initialize object's private data.

           data:
               Raw packet data
        """
        self.data = data

    def _get_ltype(self, ltype):
        """Get length of element"""
        if isinstance(ltype, int):
            # An integer is given, just return it
            return ltype
        else:
            # A function is given, return output of function
            return ltype(self)

    def rawdata(self, size, pad=0):
        """Get the number of bytes given from the working buffer.

           size:
               Length of data to get
           pad:
               Get and discard padding bytes [default: 0]
               If given, data is padded to this byte boundary
        """
        buf = self.data[0:size]
        if pad > 0:
            # Discard padding bytes
            size += (size+pad-1)/pad*pad - size
        self.data = self.data[size:]
        return buf

    def unpack(self, size, fmt):
        """Get the number of bytes given from the working buffer and process
           it according to the given format.
           Return a tuple of unpack items, see struct.unpack.

           size:
               Length of data to process
           fmt:
               Format string on how to process data
        """
        return struct.unpack('!'+fmt, self.rawdata(size))

    def unpack_char(self):
        """Get an unsigned char"""
        return self.unpack(1, 'B')[0]

    def unpack_short(self):
        """Get an unsigned short integer"""
        return self.unpack(2, 'H')[0]

    def unpack_uint(self):
        """Get an unsigned integer"""
        return self.unpack(4, 'I')[0]

    def unpack_uint64(self):
        """Get an unsigned 64 bit integer"""
        return self.unpack(8, 'Q')[0]

    def unpack_opaque(self, maxcount=0):
        """Get a variable length opaque upto a maximum length of maxcount"""
        size = self.unpack_uint()
        if maxcount > 0 and size > maxcount:
            raise Exception, "Opaque exceeds maximum length"
        return self.rawdata(size, pad=4)

    def unpack_fopaque(self, size):
        """Get a fixed length opaque"""
        return self.rawdata(size, pad=4)

    def unpack_string(self, *kwts, **kwds):
        """Get a variable length string

           ltype:
               Function to decode length of string [default: unpack_uint]
               Could also be given as an integer to have a fixed length string
               Given as the first positional argument or as a named argument
           pad:
               Get and discard padding bytes [default: 0]
               If given, string is padded to this byte boundary
           maxcount:
               Maximum length of string [default: any length]
        """
        # Process positional arguments
        ltype = Unpack.unpack_uint
        if len(kwts):
            ltype = kwts[0]
        # Process named arguments
        ltype    = kwds.pop('ltype', ltype)
        pad      = kwds.pop('pad', 0)
        maxcount = kwds.pop('maxcount', 0)

        slen = self._get_ltype(ltype)
        if maxcount > 0 and slen > maxcount:
            raise Exception, "String exceeds maximum length"
        return self.rawdata(slen, pad)

    def unpack_array(self, *kwts, **kwds):
        """Get a variable length array, the type of objects in the array
           is given by the unpacking function unpack_item and the type
           to decode the length of the array is given by ltype

           unpack_item:
               Unpack function for each item in the array [default: unpack_uint]
               Given as the first positional argument or as a named argument
           ltype:
               Function to decode length of array [default: unpack_uint]
               Could also be given as an integer to have a fixed length array
               Given as the second positional argument or as a named argument
           args:
               Named arguments to pass to unpack_item function [default: {}]
           maxcount:
               Maximum length of array [default: any length]
        """
        # Process positional arguments
        unpack_item = Unpack.unpack_uint
        ltype       = Unpack.unpack_uint
        if len(kwts):
            unpack_item = kwts[0]
        if len(kwts) > 1:
            ltype = kwts[1]
        # Process named arguments
        unpack_item = kwds.pop('unpack_item', unpack_item)
        ltype       = kwds.pop('ltype', ltype)
        uargs       = kwds.pop('args', {})
        islist      = kwds.pop('islist', False)
        maxcount    = kwds.pop('maxcount', 0)

        ret = []
        # Get length of array
        slen = self._get_ltype(ltype)
        if maxcount > 0 and slen > maxcount:
            raise Exception, "Array exceeds maximum length"
        while slen > 0:
            # Unpack each item in the array
            ret.append(unpack_item(self, **uargs))
            if islist:
                slen = self._get_ltype(ltype)
            else:
                slen -= 1
        return ret

    def unpack_list(self, *kwts, **kwds):
        """Get an indeterminate size list, the type of objects in the list
           is given by the unpacking function unpack_item and the type
           to decode the next item flag is given by ltype

           unpack_item:
               Unpack function for each item in the list [default: unpack_uint]
               Given as the first positional argument or as a named argument
           ltype:
               Function to decode the next item flag [default: unpack_uint]
               Given as the second positional argument or as a named argument
           args:
               Named arguments to pass to unpack_item function [default: {}]
        """
        kwds['islist'] = True
        return self.unpack_array(*kwts, **kwds)
