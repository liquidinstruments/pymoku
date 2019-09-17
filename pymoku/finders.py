
import select
import socket
import time
from . import pybonjour
from . import version


class BonjourFinder(object):
    def __init__(self):
        self.moku_list = []
        self.resolved = []
        self.queried = []
        self.finished = False
        self.filter_callback = None
        self.filter_type = None  # 'serial', 'name', 'ip'
        self.max_results = 0
        self.pversion = ''
        self.timeout = 5

    def query_record_callback(self, sdRef, flags, interfaceIndex,
                              errorCode, fullname, rrtype, rrclass,
                              rdata, ttl):

        if errorCode == pybonjour.kDNSServiceErr_NoError:
            ip = socket.inet_ntoa(rdata)

            # If the service got this far through then it hasn't already been
            # filtered out by serial or name,
            # so we add it to the list, unless it's filtered by IP first.
            if (not self.filter_type == 'ip') \
                    or (self.filter_type == 'ip' and (
                    self.filter_callback(ip))):
                self.moku_list.append(ip)

            if self.max_results and len(self.moku_list) >= self.max_results:
                self.finished = True

        self.queried.append(True)

    def resolve_callback(self, sdRef, flags, interfaceIndex, errorCode,
                         fullname, hosttarget, port, txtRecord):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        try:
            hw, pver, dummy = hosttarget.split('_')
            if not hw.startswith('moku') or pver != self.pversion:
                return
        except Exception:
            return

        # Parse the txtRecord string for the service
        txtRecord_dict = pybonjour.TXTRecord.parse(txtRecord)

        # If specified, filter service by serial number (extracted from
        # service metadata)
        if not (self.filter_type == 'serial' and not self.filter_callback(
                txtRecord_dict)):
            query_sdRef = pybonjour.DNSServiceQueryRecord(
                interfaceIndex=interfaceIndex,
                fullname=hosttarget,
                rrtype=pybonjour.kDNSServiceType_A,
                callBack=self.query_record_callback)
            try:
                while not self.queried:
                    ready = select.select([query_sdRef], [], [], self.timeout)
                    if query_sdRef not in ready[0]:
                        break
                    pybonjour.DNSServiceProcessResult(query_sdRef)
                else:
                    self.queried.pop()
            finally:
                query_sdRef.close()

        self.resolved.append(True)

    def browse_callback(self, sdRef, flags, interfaceIndex,
                        errorCode, serviceName, regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            return

        # If specified, filter service by device name
        if self.filter_type == 'name' and \
           not self.filter_callback(serviceName):
            return

        resolve_sdRef = pybonjour.DNSServiceResolve(0,
                                                    interfaceIndex,
                                                    serviceName,
                                                    regtype,
                                                    replyDomain,
                                                    self.resolve_callback)

        try:
            while not self.resolved:
                ready = select.select([resolve_sdRef], [], [], self.timeout)
                if resolve_sdRef not in ready[0]:
                    break
                pybonjour.DNSServiceProcessResult(resolve_sdRef)
            else:
                self.resolved.pop()
        finally:
            resolve_sdRef.close()

    def find_all(self, protocol_version=None, timeout=5, max_results=0,
                 filter_type=None, filter_callback=None):
        # Use pymoku network protocol version by default
        if protocol_version is None:
            self.pversion = version.protocol_version
        else:
            self.pversion = protocol_version

        self.timeout = timeout
        self.max_results = max_results
        self.filter_callback = filter_callback
        self.filter_type = filter_type
        self.moku_list = []

        browse_sdRef = pybonjour.DNSServiceBrowse(
            regtype='_moku._tcp',
            callBack=self.browse_callback)

        start = time.time()
        try:
            try:
                while time.time() - start < timeout and not self.finished:
                    # Basically have to reduce this to polling so we can check
                    # the finished flag with good responsiveness
                    ready = select.select([browse_sdRef], [], [], 0.1)
                    if browse_sdRef in ready[0]:
                        pybonjour.DNSServiceProcessResult(browse_sdRef)
            except KeyboardInterrupt:
                pass
        finally:
            browse_sdRef.close()

        return self.moku_list
