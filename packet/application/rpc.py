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
RPC module

Decode RPC layer.
"""
import struct
import traceback
from gss import GSS
from rpc_const import *
import nfstest_config as c
from baseobj import BaseObj
from packet.nfs.nfs4lib import FancyNFS4Unpacker

# Module constants
__author__    = 'Jorge Mora (%s)' % c.NFSTEST_AUTHOR_EMAIL
__version__   = '1.0.3'
__copyright__ = "Copyright (C) 2012 NetApp, Inc."
__license__   = "GPL v2"

class Header(BaseObj): pass
class Credential(BaseObj): pass
class Prog(BaseObj): pass

class RPC(GSS):
    """RPC object

       Usage:
           from packet.application.rpc import RPC

           # Decode the RPC header
           x = RPC(pktt_obj, buffer, proto=6)

           # Decode NFS layer
           nfs = x.decode_nfs()

       Object definition:

       RPC(
           [
               # If TCP
               fragment_hdr = Header(
                   last_fragment = int,
                   size          = int,
               ),
           ]
           xid  = int,
           type = int,

           [
               # If type == 0 (RPC call)
               rpc_version = int,
               program     = int,
               version     = int,
               procedure   = int,
               credential  = Credential(
                   data   = string,
                   flavor = int,
                   size   = int,
               ),
               verifier = Credential(
                   data   =string,
                   flavor = int,
                   size   = int,
               ),
           ] | [
               # If type == 1 (RPC reply)
               reply_status = int,
               [
                   # If reply_status == 0
                   verifier = Credential(
                       data   = string,
                       flavor = int,
                       size   = int,
                   ),
                   accepted_status = int,
                   [
                       # If accepted_status == 2
                       prog_mismatch = Prog(
                           low  = int,
                           high = int,
                       )
                   ]
               ] | [
                   # If reply_status != 0
                   rejected_status = int,
                   [
                       # If rejected_status == 0
                       prog_mismatch = Prog(
                           low  = int,
                           high = int,
                       )
                   ] | [
                       # If rejected_status != 0
                       auth_status = int,
                   ]
               ]
           ]
           [data = string] # raw data of payload if unable to decode
       )
    """
    def __init__(self, pktt, data, proto):
        """Constructor

           Initialize object's private data.

           pktt:
               Packet trace object (packet.pktt.Pktt) so this layer has
               access to the parent layers.
           data:
               Raw packet data for this layer.
           proto:
               Transport layer protocol.
        """
        self.data = data
        self._rpc = False
        self._pktt = pktt
        self._proto = proto

        try:
            self._rpc_header()
        except:
            pass

    def _rpc_header(self):
        """Internal method to decode RPC header"""
        if self._proto == 6:
            # TCP packet
            save_data = ''
            while True:
                # Decode fragment header
                psize = self.unpack_uint()
                self.fragment_hdr = Header(
                    size          = (psize & 0x7FFFFFFF) + len(save_data),
                    last_fragment = psize >> 31,
                )
                if self.fragment_hdr.size == 0:
                    return
                if self.fragment_hdr.last_fragment == 0 and self.fragment_hdr.size < len(self.data):
                    # Save RPC fragment
                    save_data += self.data[:self.fragment_hdr.size]
                    self.data = self.data[self.fragment_hdr.size:]
                else:
                    # Concatenate RPC fragments
                    self.data = save_data + self.data
                    break
        elif self._proto == 17:
            # UDP packet
            pass
        else:
            return

        # Decode XID and RPC type
        self.xid  = self.unpack_uint()
        self.type = self.unpack_uint()

        if self.type == CALL:
            # RPC call
            self.rpc_version = self.unpack_uint()
            self.program     = self.unpack_uint()
            self.version     = self.unpack_uint()
            self.procedure   = self.unpack_uint()
            self.credential  = self._rpc_credential()
            if self.credential is None:
                return
            self.verifier = self._rpc_credential(True)
            if self.rpc_version != 2 or (self.credential.flavor in [0,1] and self.verifier is None):
                return
        elif self.type == REPLY:
            # RPC reply
            self.reply_status = self.unpack_uint()
            if self.reply_status == MSG_ACCEPTED:
                self.verifier = self._rpc_credential(True)
                if self.verifier is None:
                    return
                self.accepted_status = self.unpack_uint()
                if self.accepted_status == PROG_MISMATCH:
                    self.prog_mismatch = Prog(
                        low  = self.unpack_uint(),
                        high = self.unpack_uint(),
                    )
                elif accept_stat.get(self.accepted_status) is None:
                    # Invalid accept_stat
                    return
            elif self.reply_status == MSG_DENIED:
                self.rejected_status = self.unpack_uint()
                if self.rejected_status == RPC_MISMATCH:
                    self.rpc_mismatch = Prog(
                        low  = self.unpack_uint(),
                        high = self.unpack_uint(),
                    )
                elif self.rejected_status == AUTH_ERROR:
                    self.auth_status = self.unpack_uint()
                    if auth_stat.get(self.auth_status) is None:
                        # Invalid auth_status
                        return
                elif reject_stat.get(self.rejected_status) is None:
                    # Invalid rejected status
                    return
            elif reply_stat.get(self.reply_status) is None:
                # Invalid reply status
                return
        else:
            return

        self._rpc = True
        xid = self.xid
        pktt = self._pktt
        if not getattr(pktt, '_rpc_xid_map', None):
            # NFS XID map: to keep track of call information
            # (program, version, procedure, ...) and insert
            # this information into the proper NFS reply
            pktt._rpc_xid_map = {}
        if xid not in pktt._rpc_xid_map:
            # Initialize new xid
            pktt._rpc_xid_map[xid] = {}
        if self.type == CALL:
            # Save call info in the xid map
            pktt._rpc_xid_map[xid]['program']    = self.program
            pktt._rpc_xid_map[xid]['version']    = self.version
            pktt._rpc_xid_map[xid]['procedure']  = self.procedure
            pktt._rpc_xid_map[xid]['call_index'] = pktt.index
            pktt._rpc_xid_map[xid]['flavor']     = self.credential.flavor
            if self.credential.flavor == RPCSEC_GSS:
                pktt._rpc_xid_map[xid]['gss_proc'] = self.credential.gss_proc
                pktt._rpc_xid_map[xid]['gss_service'] = self.credential.gss_service
                pktt._rpc_xid_map[xid]['gss_version'] = self.credential.gss_version
        elif self.type == REPLY:
            try:
                # Save reply info and retrieve call info
                self.program    = pktt._rpc_xid_map[xid]['program']
                self.version    = pktt._rpc_xid_map[xid]['version']
                self.procedure  = pktt._rpc_xid_map[xid]['procedure']
                self.call_index = pktt._rpc_xid_map[xid]['call_index']
                if pktt._rpc_xid_map[xid]['flavor'] == RPCSEC_GSS:
                    self.verifier.gss_proc = pktt._rpc_xid_map[xid]['gss_proc']
                    self.verifier.gss_service = pktt._rpc_xid_map[xid]['gss_service']
                    self.verifier.gss_version = pktt._rpc_xid_map[xid]['gss_version']
                pktt._rpc_xid_map[xid]['reply_index'] = pktt.index
            except Exception:
                pass

    def __nonzero__(self):
        """Truth value testing for the built-in operation bool()"""
        return self._rpc

    def __str__(self):
        """String representation of object

           The representation depends on the verbose level set by debug_repr().
           If set to 0 the generic object representation is returned.
           If set to 1 the representation of the object is:
               'RPC call   program: 100003, version: 4, procedure: 0, xid: 0xe37d3d5 '

           If set to 2 the representation of the object is as follows:
               'CALL(0), program: 100003, version: 4, procedure: 0, xid: 0xe37d3d5'
        """
        rdebug = self.debug_repr()
        if rdebug > 0:
            prog = ''
            for item in ['program', 'version', 'procedure']:
                value = getattr(self, item, None)
                if value != None:
                    prog += " %s: %d," % (item, value)
        if rdebug == 1:
            rtype = "%-5s" % msg_type.get(self.type, 'Unknown').lower()
            out = "RPC %s %s xid: 0x%08x" % (rtype, prog, self.xid)
        elif rdebug == 2:
            rtype = "%-5s(%d)" % (msg_type.get(self.type, 'Unknown'), self.type)
            out = "%s,%s xid: 0x%08x" % (rtype, prog, self.xid)
        else:
            out = BaseObj.__str__(self)
        return out

    def decode_nfs(self):
        """Decode NFS

           For RPC calls it is easy to decide if the RPC payload is an NFS packet
           since the RPC program is in the RPC header, which for NFS the
           program number is 100003. On the other hand, for RPC replies the RPC
           header does not have any information on what the payload is, so the
           transaction ID (xid) is used to map the replies to their calls and
           thus deciding if RPC payload is an NFS packet or not.
           This is further complicated when trying to decode callbacks, since
           the program number for callbacks could be any number in the transient
           program range [0x40000000, 0x5FFFFFFF]. Therefore, any program number
           in the transient range is considered a callback and if the decoding
           succeeds then this is an NFS callback, otherwise it is not.

           Since the RPC replies do not contain any information about what type
           of payload, when they are decoded correctly as NFS replies this
           information is inserted in the RPC (pkt.rpc) object.
           This information includes program number, RPC version, procedure
           number as well as the call_index which is the packet index of its
           corresponding call for each reply.

           x.pkt.nfs = <NFSobject>

           where <NFSobject> is an object of type COMPOUND4args or COMPOUND4res

           class COMPOUND4args(
               tag          = string,
               minorversion = int,
               argarray     = [],
           )

           The argarray is a list of nfs_argop4 objects:

           class nfs_argop4(
               argop = int,
               [<opobject> = <opargobject>,]
           )

           where opobject could be opsequence, opgetattr, etc., and opargobject
           is the object which has the arguments for the given opobject, e.g.,
           SEQUENCE4args, GETATTR4args, etc.

           class COMPOUND4res(
               tag      = string,
               status   = int,
               resarray = [],
           )

           The resarray is a list of nfs_resop4 objects:

           class nfs_resop4(
               resop = int,
               [<opobject> = <opresobject>,]
           )

           where opobject could be opsequence, opgetattr, etc., and opresobject
           is the object which has the results for the given opobject, e.g.,
           SEQUENCE4res, GETATTR4res, etc.
        """
        ret = None
        self.decode_gss_data()

        try:
            # Set variables for ease of use
            program   = self.program
            version   = self.version
            procedure = self.procedure
        except:
            return

        if len(self.data) == 0 or not procedure or not version:
            # Nothing to process
            return

        if program == 100003:
            cb_flag = False
        elif program >= 0x40000000 and program < 0x60000000:
            # This is a crude way to figure out if call/reply is a callback
            # based on the fact that NFS is always program 100003 and anything
            # in the transient program range is considered a callback
            cb_flag = True
        else:
            # Not an NFS packet
            return

        # Make sure to catch any errors
        try:
            if procedure == 1 and ((not cb_flag and version == 4) or
                                   (cb_flag and version == 1)):
                # Create object to unpack the NFS layer
                unpacker = FancyNFS4Unpacker(self.data)
                unpacker.check_enum = False
                if self.type == CALL:
                    # RPC call
                    if cb_flag:
                        # This packet is definitely not program 100003
                        # so treat it like a NFS callback
                        ret = unpacker.unpack_CB_COMPOUND4args()
                    else:
                        # This packet NFS
                        ret = unpacker.unpack_COMPOUND4args()
                else:
                    # RPC reply
                    if cb_flag:
                        # This packet is definitely not program 100003
                        # so treat it like a NFS callback
                        ret = unpacker.unpack_CB_COMPOUND4res()
                    else:
                        # This packet NFS
                        ret = unpacker.unpack_COMPOUND4res()

                # Position data pointer to include bytes processed by NFS
                self.data = self.data[unpacker.get_position():]
                self.decode_gss_checksum()
        except Exception:
            # Could not decode NFS packet
            self.dprint('PKT3', traceback.format_exc())
            return
        return ret

    def _rpc_credential(self, verifier=False):
        """Get the RPC credentials from the working buffer."""
        if len(self.data) < 8:
            return
        ret = Credential(flavor = self.unpack_uint())
        # Get size of data without removing bytes from buffer
        size = struct.unpack('!I', self.data[:4])[0]
        if len(self.data) < size:
            return None
        if ret.flavor == AUTH_SYS:
            ret.size    = self.unpack_uint()
            ret.stamp   = self.unpack_uint()
            ret.machine = self.unpack_opaque(maxcount=255)
            ret.uid     = self.unpack_uint()
            ret.gid     = self.unpack_uint()
            ret.gids    = self.unpack_array(maxcount=16)
        elif ret.flavor == RPCSEC_GSS:
            if not verifier:
                ret.size        = self.unpack_uint()
                ret.gss_version = self.unpack_uint()
                ret.gss_proc    = self.unpack_uint()
                ret.gss_seq_num = self.unpack_uint()
                ret.gss_service = self.unpack_uint()
                ret.gss_context = self.unpack_opaque()
            else:
                ret.size      = size
                ret.gss_token = self.unpack_opaque()
        else:
            ret.size = self.unpack_uint()
            ret.data = self.rawdata(size)
        return ret
