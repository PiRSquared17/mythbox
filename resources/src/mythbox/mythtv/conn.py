#
#  MythBox for XBMC - http://mythbox.googlecode.com
#  Copyright (C) 2010 analogue@yahoo.com
# 
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import datetime
import logging
import socket
import sre
import thread
import threading
import time

from decorator import decorator
from mythbox import pool
from mythbox.bus import Event
from mythbox.mythtv import protocol
from mythbox.mythtv.db import inject_db
from mythbox.mythtv.enums import TVState, Upcoming
from mythbox.mythtv.protocol import ProtocolException
from mythbox.util import timed, threadlocals

log     = logging.getLogger('mythbox.core')     # mythtv core logger
wirelog = logging.getLogger('mythbox.wire')     # wire level protocol logger
ilog    = logging.getLogger('mythbox.inject')   # dependency injection via decorators

# =============================================================================
def createChainId():
    """
    @return: chainId as a string suitable for spawning livetv

    Based on livetvchain.cpp:InitializeNewChain(...)
    Match format: live-zeus-2008-12-04T11:41:52
    """
    return "live-%s-%s" % (socket.gethostname(), time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()))

def decodeLongLong(low32Bits, high32Bits):
    """
    @type low32Bits: int or str
    @type high32Bits: int or str
    @return: Decodes two 32bit ints to a 64bit long
    @rtype: long
    """
    if isinstance(low32Bits, str): 
        low32Bits = long(low32Bits)
    if isinstance(high32Bits, str): 
        high32Bits = long(high32Bits)
    return low32Bits & 0xffffffffL | (high32Bits << 32)

def encodeLongLong(long64Bits):
    """
    @rtype: (low32Bits, high32Bits)
    @return: Encodes 64bit long into pair of 32 bit ints
    """
    return long64Bits & 0xffffffffL, long64Bits >> 32

@decorator
def inject_conn(func, *args, **kwargs):
    """
    Decorator to inject a thread-safe Connection object into the context 
    of a method invocation.
    
    To use:
      1. Decorate method with @inject_conn
      2. Within method, use self.conn() to obtain a reference to the Connection.
    """
    self = args[0]
    
    # if dependency already injected via constructor, do nothing 
    if hasattr(self, '_conn') and self._conn: 
        return func(*args, **kwargs)
    
    connPool = pool.pools['connPool']
    
    # Create thread local storage if not already allocated
    tlsKey = thread.get_ident()
    try:
        threadlocals[tlsKey]
        ilog.debug('threading.local() already allocated')
    except KeyError:
        threadlocals[tlsKey] = threading.local()
        ilog.debug('Allocating threading.local() to thread %d'  % tlsKey)

    # Bolt-on getter method so client can access connection.
    def conn_accessor():
        return threadlocals[thread.get_ident()].conn
    self.conn = conn_accessor  

    # Only acquire resource once per thread
    try:
        if threadlocals[tlsKey].conn == None:
            raise AttributeError # force allocation
        alreadyAcquired = True; 
        ilog.debug('Skipping acquire resource')
    except AttributeError:
        alreadyAcquired = False
        ilog.debug('Going to acquire resource')

    try:
        if not alreadyAcquired:
            # store conn in thread local storage
            threadlocals[tlsKey].conn = connPool.checkout()
            ilog.debug('--> injected conn %s into %s' % (threadlocals[tlsKey].conn, threadlocals[tlsKey]))
            
        result = func(*args, **kwargs) 
    finally:
        if not alreadyAcquired:
            ilog.debug('--> removed conn %s from %s' % (threadlocals[tlsKey].conn, threadlocals[tlsKey]))
            connPool.checkin(threadlocals[tlsKey].conn)
            threadlocals[tlsKey].conn = None
    return result

# =============================================================================
class ClientException(Exception): 
    """Thrown when the mythtv client behaves inappropriately"""
    pass

# =============================================================================
class ServerException(Exception): 
    """Thrown in response to error conditions from the mythtv backend"""
    pass

# =============================================================================
class Connection(object):
    """
    Connection to MythTV Backend.
    
    TODO: Update to support multiple storage groups - getDiskUsage()
    """
    
    def __init__(self, settings, translator, platform, bus, db=None):
        """
        @param db: None means use @inject_db
        """
        self.settings = settings
        self.translator = translator
        self.platform = platform
        self.bus = bus
        self._db = db
        
        self.host = self.settings.getMythTvHost()
        self.port = self.settings.getMythTvPort()
        self.cmdSock = self.connect()
        
    def db(self):
        return self._db

    def connect(self, announce='Playback', slaveBackend=None):
        """
        Monitor connections allow backend to shutdown.
        Playback connections prevent backend from shutting down. 

        @param announce: Playback, Monitor, or None (to not announce anything)  
        @return: socket to backend
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if slaveBackend == None:
            slaveBackend = self.host
        s.connect((slaveBackend, self.port))
        
        if not protocol.serverVersion:
            protocol.serverVersion = self.getServerVersion()
        
        # Protocol version has to be sent on each new connection
        serverVersion = self.negotiateProtocol(s, protocol.serverVersion)
        try:
            self.protocol = protocol.protocols[serverVersion]
        except KeyError:
            raise ProtocolException('Unsupported protocol: %s' % serverVersion)
            
        if announce:
            if announce == 'Playback':
                self.annPlayback(s)
            elif announce == 'Monitor':
                self.annMonitor(s)
            else:
                raise ClientException('Unsupported announce command: %s' % announce)
        return s
    
    def getServerVersion(self):
        # TODO: Optimize to static method proteced by a class level lock so only done once
        #       and not multiple times on a flurry of new connection instances on startup
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.settings.getMythTvHost() , self.settings.getMythTvPort()))
        try:
            # induce reject
            reply = self._sendRequest(sock, ['MYTH_PROTO_VERSION %d' % protocol.initVersion])
            serverResponse = reply[0]
            serverVersion  = int(reply[1])
            log.debug('getServerVersion: %s %s' % (serverResponse, serverVersion))
        finally:
            sock.close()
        return serverVersion
        
    def close(self):
        if self.cmdSock:
            self._sendMsg(self.cmdSock, ['DONE'])
            self.cmdSock.shutdown(socket.SHUT_RDWR)
            self.cmdSock.close()
            
        if self._db:
            self._db.close()
                
    @timed            
    def negotiateProtocol(self, s, clientVersion):
        """ 
        @return: version of the MythTV protocol the server supports
        @rtype: int 
        @raise ProtocolException: when clientVersion is less than serverVersion
        """
        reply = self._sendRequest(s, ['MYTH_PROTO_VERSION %s' % clientVersion])
        
        serverResponse = reply[0]
        serverVersion  = int(reply[1])
        wirelog.debug('negotiateProtocol: %s -> %s %s' % (clientVersion, serverResponse, serverVersion))
        
        if (serverVersion < clientVersion):
            pe = ProtocolException('Protocol mismatch - Server protocol version: %s  Client protocol version: %s'%(serverVersion, clientVersion))
            pe.protocolVersion = serverVersion
            raise pe   
        return serverVersion

    @timed
    def annPlayback(self, cmdSock):
        reply = self._sendRequest(cmdSock, ['ANN Playback %s 0' % self.platform.getHostname()])
        if not self._isOk(reply):
            raise ServerException, 'Backend playback refused: %s' % reply
    
    @timed
    def annMonitor(self, cmdSock):
        reply = self._sendRequest(cmdSock, ['ANN Monitor %s 0' % self.platform.getHostname()])
        if not self._isOk(reply):
            raise ServerException, 'Backend monitor refused: %s' % reply

    @timed
    def annFileTransfer(self, backendHost, filePath):
        """
        Announce file transfer to backend.
        
        @param backendHost : Hostname of backend that recorded the file to transfer
        @param filePath    : Myth style URL of file to tranfer. Ex: myth://somehost:port/blah.mpg
        @return            : list[reply[], socket] 
        """
        s = self.connect(announce=None, slaveBackend=backendHost)
        self._sendMsg(s, self.protocol.buildAnnounceFileTransferCommand(self.platform.getHostname(),  filePath))
        reply = self._readMsg(s)
        if not self._isOk(reply):
            raise ServerException('Backend filetransfer refused: %s' % reply)
        del reply[0]    # remove OK
        return [reply, s]
        
    def checkFile(self, rec):
        # TODO: Whats this for? Not used currently
        msg = rec.data()[:]
        msg.insert(0, 'QUERY_CHECKFILE')
        reply = self._sendRequest(msg)
        return reply[0]

    def getSetting(self, key, hostname):
        """
        @return: MythSetting for the given key and hostname
        """
        command = 'QUERY_SETTING %s %s' %(key, hostname)
        reply = self._sendRequest(self.cmdSock, [command])
        return reply
        # TODO: Unfinished!
    
    @inject_db
    def getChannels(self):
        """
        @return: Viewable channels across all tuners.
        @rtype: Channel[]
        """
        return self.db().getChannels()
    
    @inject_db
    def getTuners(self):
        """
        @return: Tuner[]
        """
        tuners = self.db().getTuners()
        # inject each tuner w/ this session before returning
        for t in tuners:
            t.conn = self
        return tuners
    
    @timed
    def getFramesWritten(self, tuner):
        """
        For a tuner that is recording, return the number of frames written as an int
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %d' % tuner.tunerId, 'GET_FRAMES_WRITTEN'])
        return decodeLongLong(int(reply[1]), int(reply[0]))

    @timed
    def getTunerFilePosition(self, tuner):
        """
        For a tuner that is recording, return the current position in the file as an int
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %d' % tuner.tunerId, 'GET_FILE_POSITION'])
        return decodeLongLong(int(reply[1]), int(reply[0]))

    @timed
    def getTunerFrameRate(self, tuner):
        """
        For a tuner that is recording, return the framerate as a float
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %d' % tuner.tunerId, 'GET_FRAMERATE'])
        return float(reply[0])

    @timed 
    def getCurrentRecording(self, tuner):
        """
        @return: For a tuner that is recording, return the current Program
        @rtype: RecordedProgram
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %d' % tuner.tunerId, 'GET_CURRENT_RECORDING'])
        from mythbox.mythtv.domain import RecordedProgram
        program = RecordedProgram(reply, self.settings, self.translator, self.platform, [self, None][self._db is None])
        return program
        
    @inject_db
    def getTunerShowing(self, showName):
        """ 
        @type showName: str
        @return: tunerId of the first tuner either recording or watching the given showname, otherwise returns -1
        @rtype: int
        @todo: Change return type to Tuner or None
        @todo: Rename to getTunerWatchingOrRecording(...)
        """ 
        tuners = self.db().getTuners()
        for tuner in tuners:
            tvState = int(self._sendRequest(self.cmdSock, ['QUERY_REMOTEENCODER %d'%tuner.tunerId, 'GET_STATE'])[0])
            
            if tvState == TVState.OK:  # not busy
                break
            elif tvState == TVState.Error:
                log.warning('QUERY_REMOTEENCODER::GET_STATE = Error')
                break
            elif tvState in [TVState.WatchingLiveTV, TVState.RecordingOnly, TVState.WatchingPreRecorded, TVState.WatchingRecording]:
                recording = self.getCurrentRecording(tuner)
                if showName == recording.title():
                    return tuner.tunerId
            else:
                break
        return -1

    @timed
    def getTunerStatus(self, tuner):
        """
        @rtype: TVSTate enum
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_REMOTEENCODER %d' % tuner.tunerId, 'GET_STATE'])
        return int(reply[0])

    @timed
    def getNumFreeTuners(self):
        return int(self._sendRequest(self.cmdSock, ['GET_FREE_RECORDER_COUNT'])[0])

    @timed
    def getNextFreeTuner(self, afterTunerId):
        """ 
        @return: (tunerId, ip address, int port) of the next free tuner after the passed in tunerId
        """
        reply = self._sendRequest(self.cmdSock, ['GET_NEXT_FREE_RECORDER', str(afterTunerId)])
        tunerId = int(reply[0])
        if reply[0] == -1:
            # No tuners available
            return None, None, None
        else:
            # Success
            backendServer = reply[1]
            backendPort = reply[2]
            return (tunerId, backendServer, int(backendPort))

    @timed
    def spawnLiveTV(self, tuner, channelNumber):
        """
        Instructs myth backend to start livetv on the given tuner and channelNumber. 
        A unique chainId is generated and returned if successful. 
        
        @type tuner: Tuner
        @type channelNumber: string 
        @return: generated chainId
        @rtype: string
        @raise ProtocolException: error 
        """
        # void SpawnLiveTV(QString chainid, bool pip, QString startchan);
        chainId = createChainId()
        pip = str(int(False))
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %s' % tuner.tunerId, 'SPAWN_LIVETV', chainId, pip, channelNumber])
        log.debug('spawnLiveTV response = %s' % reply)
        if not self._isOk(reply):
            raise ServerException('Error spawning live tv on tuner %s with reply %s' % (tuner, reply))
        return chainId
        
    @timed
    def stopLiveTV(self, tuner):
        """
        Stops live tv. Throws ServerException on error. 
        
        @param tuner: Tuner on which livetv has already been started
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %s' % tuner.tunerId, 'STOP_LIVETV'])
        log.debug('stopLiveTV response = %s' % reply)
        if not self._isOk(reply):
            raise ServerException('Error stopping live tv on tuner %s with reply %s' % (tuner, reply))
                
    @timed
    def getFreeTuner(self):
        """
        @return: (int tunerId, str IP address, int port) of a tuner that is not busy, tuple of -1 otherwise
        """
        reply = self._sendRequest(self.cmdSock, ['GET_FREE_RECORDER'])
        if reply[0] == '-1':
            # No tuners available
            return (-1, '', -1)
        else:
            tunerId = reply[0]
            backendServer = reply[1]
            backendPort = reply[2]
            return (int(tunerId), backendServer, int(backendPort))
               
    def finishRecording(self, tunerId):
        # TODO: Not used - consider deleting
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %s' % tunerId, 'FINISH_RECORDING'])
        log.debug('FINISH RECORDING: %s' % reply)
        return self._isOk(reply)
            
    def cancelNextRecording(self, tunerId):
        # TODO: Not used - consider deleting
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDER %s' % tunerId, 'CANCEL_NEXT_RECORDING'])
        log.debug('CANCEL NEXT RECORDING: %s' % reply)
        return reply.upper() == 'OK'
    
    def isTunerRecording(self, tuner):
        command = ['QUERY_RECORDER %d' % tuner.tunerId, 'IS_RECORDING']
        if tuner.hostname == self.host:
            reply = self._sendRequest(self.cmdSock, command)
            return reply[0] == '1'
        else:
            # TODO: Refactor on-demand connections to slave backend for all commands that are local only on master be
            log.debug('backend is a slave..creating new connection')
            bs = self.connect(slaveBackend=tuner.hostname)
            reply = self._sendRequest(bs, command)
            self._sendMsg(bs, ['DONE'])
            bs.shutdown(socket.SHUT_RDWR)
            bs.close()
            return reply[0] == '1'
                        
    @timed
    def deleteRecording(self, program):
        """
        @type program: RecordedProgram
        @return: 1 on success, 0 on failure
        """
        msg = program.data()[:]
        msg.insert(0, 'DELETE_RECORDING')
        msg.append('0')
        reply = self._sendRequest(self.cmdSock, msg)
        if sre.match('^-?\d+$', reply[0]):
            rc = int(reply[0])
            self.bus.publish({'id':Event.RECORDING_DELETED, 'source': self, 'program':program})
        else:
            raise ServerException, reply[0]
        log.debug('Deleted recording %s with response %s' % (program.title(), rc))
        return rc

    @timed
    def rerecordRecording(self, program):
        """
        Deletes a program and allows it to be recorded again. 
        
        @type program: RecordedProgram
        @return: 1 on success, 0 on failure
        """
        rc1 = self.deleteRecording(program)
        
        msg = program.data()[:]
        msg.insert(0, 'FORGET_RECORDING')
        msg.append('0')
        reply = self._sendRequest(self.cmdSock, msg)
        if sre.match('^-?\d+$', reply[0]):
            rc2 = int(reply[0])
        else:
            raise ServerException, reply[0]
        log.debug('Allowed re-record of %s with response %s' %(program.title(), rc2))
        return rc1

    @timed
    def generateThumbnail(self, program, backendHost, width=None, height=None):
        """
        Request the backend generate a thumbnail for a program. The backend generates 
        the thumbnail and persists it do the filesystem regardless of whether a 
        thumbnail existed or not. Thumbnail filename = recording filename + '.png'  
        
        @type program: Program
        @param backendHost: hostname of the myth backend which recorded the program
        @type backendHost: string
        @return: True if successful, False otherwise 
        """
        msg = program.data()[:]
        
        # clear out fields - this is based on what mythweb does
        # mythtv-0.16
        msg[0] = ' '    # title
        msg[1] = ' '    # subtitle
        msg[2] = ' '    # description
        msg[3] = ' '    # category
                        # chanid
        msg[5] = ' '    # channum
        msg[6] = ' '    # chansign
        msg[7] = ' '    # channame
                        # filename
        msg[9] = '0'    # upper 32 bits
        msg[10] = '0'   # lower 32 bits
                        # starttime
                        # endtime
        msg[13] = '0'   # conflicting
        msg[14] = '1'   # recording
        msg[15] = '0'   # duplicate
                        # hostname
        msg[17] = '-1'  # sourceid
        msg[18] = '-1'  # cardid
        msg[19] = '-1'  # inputid
        msg[20] = ' '   # recpriority
        msg[21] = ' '   # recstatus  - really int
        msg[22] = ' '   # recordid
        msg[23] = ' '   # rectype
        msg[24] = '15'  # dupin
        msg[25] = '6'   # dupmethod
                        # recstarttime
                        # recendtime
        msg[28] = ' '   # repeat
        msg[29] = ' '   # program flags
        msg[30] = ' '   # recgroup
        msg[31] = ' '   # commfree
        msg[32] = ' '   # chanoutputfilters
                        # seriesid
                        # programid
                        # dummy lastmodified
                        
        msg[36] = '0'   # dummy stars
                        # dummy org airdate
        msg[38] = '0'   # hasAirDate
        msg[39] = '0'   # playgroup
        msg[40] = '0'   # recpriority2
        msg[41] = '0'   # parentid
                        # storagegroup
        
        msg.insert(0, 'QUERY_GENPIXMAP')

        # extra data
        #if width and height:
        msg.append('s')
        timeLow, timeHigh = encodeLongLong(180)
        msg.append('%d' % timeHigh)
        msg.append('%d' % timeLow)
        #msg.append('<EMPTY>')
        msg.append(program.getBareFilename() + '.640x360.png')
        msg.append('%d' % 640)
        msg.append('%d' % 360)
        
        # if a slave backend, establish a new connection otherwise reuse existing connection to master backend.        
        if backendHost != self.settings.getMythTvHost():
            s = self.connect(slaveBackend=backendHost)
            reply = self._sendRequest(s, msg)
            result = self._isOk(reply)
            s.shutdown(socket.SHUT_RDWR)
            s.close()
        else:
            reply = self._sendRequest(self.cmdSock, msg)
            result = self._isOk(reply)
        log.debug('genpixmap reply = %s' % reply)
        return result

    @timed
    def getThumbnailCreationTime(self, program, backendHost):
        """
        Get the time at which the thumbnail for a program was generated.
    
        @type program: Program
        @type backendHost: string
        @return: datetime of thumbnail generation or None if never generated or error
        """
        msg = program.data()[:]
        
        # clear out fields - this is based on what mythweb does
        # mythtv-0.16
        msg[0] = ' '    # title
        msg[1] = ' '    # subtitle
        msg[2] = ' '    # description
        msg[3] = ' '    # category
                        # chanid
        msg[5] = ' '    # channum
        msg[6] = ' '    # chansign
        msg[7] = ' '    # channame
                        # filename
        msg[9] = '0'    # upper 32 bits
        msg[10] = '0'   # lower 32 bits
                        # starttime
                        # endtime
        msg[13] = '0'   # conflicting
        msg[14] = '1'   # recording
        msg[15] = '0'   # duplicate
                        # hostname
        msg[17] = '-1'  # sourceid
        msg[18] = '-1'  # getTunerId
        msg[19] = '-1'  # inputid
        msg[20] = ' '   # recpriority
        msg[21] = ' '   # recstatus - really int
        msg[22] = ' '   # recordid
        msg[23] = ' '   # rectype
        msg[24] = '15'  # dupin
        msg[25] = '6'   # dupmethod
                        # recstarttime
                        # recendtime
        msg[28] = ' '   # repeat
        msg[29] = ' '   # program flags
        msg[30] = ' '   # recgroup
        msg[31] = ' '   # commfree
        msg[32] = ' '   # chanoutputfilters
                        # seriesid
                        # programid
                        # dummy lastmodified
                        
        msg[36] = '0'   # dummy stars
                        # dummy org airdate
        msg[38] = '0'   # hasAirDate
        msg[39] = '0'   # playgroup
        msg[40] = '0'   # recpriority2
        msg[41] = '0'   # parentid
                        # storagegroup
        msg.append('')  # trailing separator
        msg.insert(0, 'QUERY_PIXMAP_LASTMODIFIED')

        if backendHost == self.settings.getMythTvHost():
            reply = self._sendRequest(self.cmdSock, msg)
        else: 
            s = self.connect(slaveBackend=backendHost)
            reply = self._sendRequest(s, msg)
            s.shutdown(socket.SHUT_RDWR)
            s.close()
        
        if reply == None or len(reply) == 0 or reply[0] == 'BAD':
            dt = None
        else:
            dt = datetime.datetime.fromtimestamp(float(reply[0]))
        return dt
    
    @timed
    def getScheduledRecordings(self):
        """
        @rtype: RecordedProgram[]  (even though not yet recorded)
        @return: Programs ordered by title. Not much else of the returned data is of any use. 
                 The good stuff is in getUpcomingRecordings()
        """
        scheduledRecordings = []
        reply = self._sendRequest(self.cmdSock, ['QUERY_GETALLSCHEDULED'])
        cnt = int(reply[0])
        offset = 1
        from mythbox.mythtv.domain import RecordedProgram
        for i in range(cnt):
            scheduledRecordings.append(
                RecordedProgram(
                    reply[offset:(offset+self.protocol.recordSize())],
                    self.settings, 
                    self.translator,
                    self.platform,
                    [self, None][self._db is None]))
            offset += self.protocol.recordSize()
        return scheduledRecordings
    
    @timed
    def getUpcomingRecordings(self, filter=Upcoming.SCHEDULED):
        """
        @type filter: UPCOMING_*
        @rtype: RecordedProgram[]
        
        From mythweb:
        
        // Skip scheduled shows?
        if (in_array($show->recstatus, array('WillRecord', 'ForceRecord'))) {
            if (!$_SESSION['scheduled_recordings']['disp_scheduled'] || $_GET['skip_scheduled'])
                continue;
        }
        // Skip conflicting shows?
        elseif (in_array($show->recstatus, array('Conflict', 'Overlap'))) {
            if (!$_SESSION['scheduled_recordings']['disp_conflicts'] || $_GET['skip_conflicts'])
                continue;
        }
        // Skip duplicate or ignored shows?
        elseif (in_array($show->recstatus, array('NeverRecord', 'PreviousRecording', 'CurrentRecording'))) {
            if (!$_SESSION['scheduled_recordings']['disp_duplicates'] || $_GET['skip_duplicates'])
                continue;
        }
        // Skip deactivated shows?
        elseif ($show->recstatus != 'Recording') {
            if (!$_SESSION['scheduled_recordings']['disp_deactivated'] || $_GET['skip_deactivated'])
                continue;
        }
        // Show specific recgroup only
        if (($_SESSION['scheduled_recordings']['disp_recgroup'] && $show->recgroup != $_SESSION['scheduled_recordings']['disp_recgroup'])
            || ($_GET['recgroup'] && $show->recgroup != $_GET['recgroup']))
            continue;
        // Show specific title only
        if (($_SESSION['scheduled_recordings']['disp_title'] && $show->title != $_SESSION['scheduled_recordings']['disp_title'])
            || ($_GET['title'] && $show->title != $_GET['title']))
            continue;
        // Assign a reference to this show to the various arrays
        $all_shows[] =& $Scheduled_Recordings[$callsign][$starttime][$key];
        }
        """
        upcoming = []
        reply = self._sendRequest(self.cmdSock, ['QUERY_GETALLPENDING', '2'])
        
        log.debug('getUpcomingRecordings reply begin= %s' % reply[:80])
        log.debug('getUpcomingRecordings reply end  = %s' % reply[-80:])
        
        numRows = int(reply[1])
        offset = 2

        from mythbox.mythtv.domain import RecordedProgram
        for i in range(numRows):
            program = RecordedProgram(
                    reply[offset:offset+self.protocol.recordSize()],
                    self.settings, 
                    self.translator,
                    self.platform,
                    [self, None][self._db is None])
            if program.getRecordingStatus() in filter:
                upcoming.append(program)
            offset += self.protocol.recordSize()
        return upcoming

    @timed
    def getAllRecordings(self):
        """
        @return: RecordedProgram[]  (most recently recorded first)
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDINGS Play'])   
        numPrograms = int(reply.pop(0))
        programs = [] 
        offset =0
        recordSize = self.protocol.recordSize()
        from mythbox.mythtv.domain import RecordedProgram
        for i in xrange(numPrograms):
            # use of self._db intentional 
            programs.append(RecordedProgram(reply[offset:offset+recordSize], self.settings, self.translator, self.platform, [self, None][self._db is None])) 
            offset += recordSize
        programs = filter(lambda p: p.getRecordingGroup() != 'LiveTV', programs)
        programs.sort(key=RecordedProgram.starttimeAsTime, reverse=True)
        return programs
    
    @timed
    def getRecordings(self, recordingGroup='default', title='all shows'):
        """
        Returns a list of RecordedProgram for the given recording group and show title (both case insensetive).
        
        @param recordingGroup: Recording group name or 'All Groups'
        @type recordingGroup: string
        @param title: Title of program or 'All Shows'
        @type title: string
        @rtype: RecordedProgram[]
        """
        # TODO: Optimize so it doesn't get all recordings and filters locally
        programs = []
        offset = 0
        reply = self._sendRequest(self.cmdSock, ['QUERY_RECORDINGS Play'])   
        numRows = int(reply.pop(0))
        
        recordingGroup = recordingGroup.upper()
        title = title.upper()
        from mythbox.mythtv.domain import RecordedProgram
        
        for i in xrange(numRows):
            response = reply[offset:offset+self.protocol.recordSize()]
            # use of self._db intentional
            p = RecordedProgram(response, self.settings, self.translator, self.platform, [self, None][self._db is None])
            if  recordingGroup.upper() in ('ALL GROUPS', p.getRecordingGroup().upper(),) and \
                title.upper() in ('ALL SHOWS', p.title().upper(),):
                programs.append(p) 
            offset += self.protocol.recordSize()
        return programs

    @timed
    def getRecording(self, channelId, startTime):
        """
        @type channelId: int
        @type startTime: str or datetime.datetime
        @return: RecordedProgram or None if not found 
        """
        if isinstance(startTime, datetime.datetime):
            from mythbox.mythtv.domain import dbTime2MythTime
            startTime = dbTime2MythTime(startTime)
        query = 'QUERY_RECORDING TIMESLOT %s %s' % (channelId, startTime) 
        reply = self._sendRequest(self.cmdSock, [query])
        from mythbox.mythtv.domain import RecordedProgram
        if self._isOk(reply):
            return RecordedProgram(reply[1:], self.settings, self.translator, self.platform, [self, None][self._db is None])
        else:
            log.debug('Program not found')
            return None

    @timed
    def getBookmark(self, program):
        """
        Return the frame number of the bookmark as a long for the passed in program or 
        zero if no bookmark is found.
        """
        command = 'QUERY_BOOKMARK %s %s' %(program.getChannelId(), program.starttimets())
        reply = self._sendRequest(self.cmdSock, [command])
        bookmarkFrame = decodeLongLong(int(reply[1]), int(reply[0])) 
        log.debug('bookmarkFrame = int %s int %s => long %s' %(reply[0], reply[1], bookmarkFrame))
        return bookmarkFrame
    
    @timed
    def setBookmark(self, program, frameNumber):
        """
        Sets the bookmark for the given program to frameNumber. 
        Raises ServerException on failure.
        """
        lowWord, highWord = encodeLongLong(frameNumber)
        command = 'SET_BOOKMARK %s %s %s %s' %(program.getChannelId(), program.starttimets(), highWord, lowWord)
        reply = self._sendRequest(self.cmdSock, [command])
        
        if reply[0] == 'OK':
            log.debug("Bookmark frameNumber set to %s" % frameNumber)
        elif reply[0] == 'FAILED':
            raise ServerException(
                "Failed to save position in program '%s' to frame %s. Server response: %s" %(
                program.title(), frameNumber, reply[0]))
        else:
            raise ProtocolException('Unexpected return value: %s' % reply[0])
    
    @timed
    def getCommercialBreaks(self, program):
        """
        @type program: RecordedProgram
        @return: List of commercial breaks for the given recording in chronological order
        @rtype: CommercialBreak[]
        """
        COMM_START = 4
        COMM_END   = 5
        
        command = 'QUERY_COMMBREAK %s %s' %(program.getChannelId(), program.starttimets())
        reply = self._sendRequest(self.cmdSock, [command])
        numRecs = int(reply[0])
        commBreaks = []
        
        if numRecs == -1:
            return commBreaks
        
        if numRecs % 2 != 0:
            raise ClientException, 'Expected an even number of comm break records but got %s instead' % numRecs
        
        fps = program.getFrameRate()
        recSize = 3                      # marker, highByte, lowByte
        for i in xrange(0, numRecs, 2):  # skip by 2's - start/end come in pairs
            baseIndex = i * recSize

            commFlagStart = int(reply[baseIndex + 1])
            if commFlagStart != COMM_START:
                raise ProtocolException, 'Expected COMM_START for record %s but got %s instead' % ((i+1), commFlagStart)
            
            frameStart = decodeLongLong(reply[baseIndex + 3], reply[baseIndex + 2])

            commFlagEnd = int(reply[baseIndex + 4])
            if commFlagEnd != COMM_END:
                raise ProtocolException, 'Expected COMM_END for record %s but got %s instead' %((i+2), commFlagEnd)
            
            frameEnd = decodeLongLong(reply[baseIndex + 6], reply[baseIndex + 5])
            from mythbox.mythtv.domain import frames2seconds, CommercialBreak
            commBreaks.append(CommercialBreak(frames2seconds(frameStart, fps), frames2seconds(frameEnd, fps)))
                        
        log.debug('%s commercials in %s' %(len(commBreaks), program.title()))
        return commBreaks
        
    def getDiskUsage(self):
        """
        @rtype: dict with keys: hostname, dir, total, used, free (numbers are ints)
        @return: Disk usage stats for master backend only. Numbers are ints in units of byte.
        @todo: Update so support multiple storage groups. For now, just return the stats on the first storage group
        """
        reply = self._sendRequest(self.cmdSock, ['QUERY_FREE_SPACE'])

        # Reply indices:
        # 0 hostname,
        # 1 directory,
        # 2 1,
        # 3 -1,
        # 4 total size high
        # 5 total size low
        # 6 used size high
        # 7 used size low

        totalSpace = decodeLongLong(int(reply[6]), int(reply[5]))
        usedSpace = decodeLongLong(int(reply[8]), int(reply[7]))
        freeSpace = totalSpace - usedSpace
        return {
            'hostname' : reply[1],
            'dir'      : reply[2],
            'total'    : totalSpace,
            'used'     : usedSpace,     
            'free'     : freeSpace,    
        }
    
    def getLoad(self):
        """
        @rtype: {str:str} with keys '1', '5', '15'
        @return: Backend load for the last 1/5/15 minutes
        """
        reply = self._sendRequest( self.cmdSock, ['QUERY_LOAD'])
        return {'1':reply[0], '5':reply[1], '15':reply[2]}

    def getUptime(self):
        """
        @rtype: datetime.timedelta
        @return: Uptime of the backend. If a non-unix based host, returns None
        """
        uptime = self._sendRequest(self.cmdSock, ['QUERY_UPTIME'])[0]
        try:
            return datetime.timedelta(seconds=int(uptime))
        except:
            return None

    @inject_db
    def getGuideDataStatus(self):
        """
        @return: List programming guide retrieval status as a string
        """
        start = self.db().getMythSetting('mythfilldatabaseLastRunStart')
        end = self.db().getMythSetting('mythfilldatabaseLastRunEnd')
        status = self.db().getMythSetting('mythfilldatabaseLastRunStatus')
        return 'Programming guide info retrieved on %s and ended on %s. %s' % (start, end, status)

    @timed
    def getGuideData(self):
        # TODO: Implement db.getLastShow()
        return ''
#        lastShow = self.db().getLastShow()
#        dataStatus = ""
#        if lastShow == None:
#            dataStatus = "There's no guide data available! Have you run mythfilldatabase?"
#        else:
#            timeDelt = lastShow - datetime.datetime.now()
#            daysOfData = timeDelt.days + 1
#            log.debug("days of data: %s" % daysOfData)
#            log.debug("End Date: %s Now: %s Diff: %s" % (lastShow, datetime.datetime.now(), str(lastShow - datetime.datetime.now())))
#            dataStatus = "There's guide data until %s (%s" % (lastShow.strftime("%Y-%m-%d %H:%M"), daysOfData)
#            if daysOfData == 1:
#                dataStatus += "day"
#            else:
#                dataStatus += "days"
#            dataStatus += ")."
#        if daysOfData <= 3:
#            dataStatus += "WARNING: is mythfilldatabase running?"
#        return dataStatus

    def getFileSize(self, backendPath, theHost):
        """
        Method to retrieve remote file size.  The backendPath is in the format
        described by the transferFile method.
        """
        # TODO: Not used - consider deleting
        rc = 0
        ft,s = self.annFileTransfer(theHost, backendPath)
        log.debug('ft=<%s>' % ft)
        rc = long(ft[2])
        s.shutdown(socket.SHUT_RDWR)
        s.close()
        s = None
        return rc
    
    @inject_db
    def saveSchedule(self, schedule):
        """
        Saves a new schedule or updates an existing schedule and notifies
        the backend.
        
        @type schedule: Schedule
        """
        new = schedule.getScheduleId() is None
        self.db().saveSchedule(schedule)
        self.rescheduleNotify(schedule)

    @inject_db
    def deleteSchedule(self, schedule):
        """
        Deletes an existing schedule and notifies the backend.
        
        @type schedule: Schedule
        """
        self.db().deleteSchedule(schedule)
        self.rescheduleNotify()
   
    @timed    
    def rescheduleNotify(self, schedule=None):
        """
        Method to instruct the backend to reschedule recordings.  If the
        schedule is not specified, all recording schedules will be rescheduled
        by the backend.
        """
        log.debug('rescheduleNotify(schedule= %s)' % schedule)
        scheduleId = 0
        if schedule:
            scheduleId = schedule.getScheduleId()
            if scheduleId is None:
                scheduleId = 0
        reply = self._sendRequest(self.cmdSock, ['RESCHEDULE_RECORDINGS %s' % scheduleId])
        if int(reply[0]) < 0:
            raise ServerException, 'Reschedule notify failed: %s' % reply

    def transferFile(self, backendPath, destPath, backendHost):
        """
        Copy a file from the remote myththv backend to destPath on the local filesystem. 
        Valid files include recordings, thumbnails, and channel icons. 
        
        @param backendPath: myth url to file. Ex: myth://<host>:<port>/<path>
        @param destPath: path of destination file on the local filesystem. Ex: /tmp/somefile.mpg
        @param backendHost: The backend that recorded the file. When None, defaults to master backend
        @rtype: bool
        """
        rc = True
        closeCommandSocket = False
        
        if backendHost ==  None:
            backendHost = self.settings.getMythTvHost()
            log.debug('Backend null, so requesting file from: %s' % backendHost)    
        
        # Don't reuse cmd sock if we're requesting a file from a slave backend
        if backendHost != self.settings.getMythTvHost():
            log.debug('Requesting file from slave backend: %s' % backendHost)
            commandSocket = self.connect(announce='Playback', slaveBackend=backendHost)
            closeCommandSocket = True 
        else:
            commandSocket = self.cmdSock
         
        reply,dataSocket = self.annFileTransfer(backendHost, backendPath)
        filesize = decodeLongLong(reply[2], reply[1])
        log.debug('file = %s reply[0] = %s filesize = %s' % (backendPath, reply[0], filesize))
        
        if filesize == 0:
            rc = False
        else:
            maxBlockSize = 2000000 # 2MB
            remainingBytes = filesize
            fh = file(destPath, 'w+b')
            maxReceived = 0
            
            while remainingBytes > 0:
                blockSize = min(remainingBytes, maxBlockSize)
                requestBlockMsg = ['QUERY_FILETRANSFER ' + reply[0], 'REQUEST_BLOCK', '%s' % blockSize]
                self._sendMsg(commandSocket, requestBlockMsg)
                
                blockTransferred = 0
                while blockTransferred < blockSize:
                    expectedBytes = blockSize - blockTransferred
                    wirelog.debug('waiting for %d bytes' % expectedBytes)
                    data = dataSocket.recv(expectedBytes)
                    actualBytes = len(data)
                    maxReceived = max(maxReceived, actualBytes)
                    wirelog.debug('received %d bytes' % actualBytes)
                    blockTransferred += actualBytes
                    if actualBytes > 0:
                        fh.write(data)
                        wirelog.debug('wrote %d bytes' % actualBytes)
                
                reply = self._readMsg(commandSocket)
                wirelog.debug('reply = %s'%reply)
                remainingBytes = remainingBytes - blockSize

            fh.close()
            wirelog.debug('transferFile rc = %d' % rc)
            wirelog.debug('max rcz size = %d' % maxReceived)

        dataSocket.shutdown(socket.SHUT_RDWR)
        dataSocket.close()
        
        if closeCommandSocket:
            commandSocket.shutdown(socket.SHUT_RDWR)
            commandSocket.close()
        
        return rc

    def _buildMsg(self, msg):
        msg = protocol.separator.join(msg)
        return '%-8d%s' % (len(msg), msg)

    def _readMsg(self, s):
        retMsg = ''
        try:
            #retMsg = s.recv(8, socket.MSG_WAITALL)
            retMsg = self.recv_all(s, 8)
            #wirelog.debug("REPLY: %s"%retMsg)
            reply = ''
            if retMsg.upper() == 'OK':
                return 'OK'
            wirelog.debug('retMsg: [%d] %s' % (len(retMsg), retMsg))
            n = int(retMsg)
            #wirelog.debug("reply len: %d" % n)
            i = 0
            while i < n:
                wirelog.debug (" i=%d n=%d " % (i,n))
                #reply += s.recv(n - i) # , socket.MSG_WAITALL)
                reply += self.recv_all(s, n - i)
                i = len(reply)
                wirelog.debug("total read = %d" % i)

            wirelog.debug('read  <- %s' % reply[:80])
            return reply.split(protocol.separator)
        except:
            log.exception('Error reading message: %s' % retMsg)
            raise

    def recv_all(self, socket, bytes):
        """Receive an exact number of bytes.
    
        Regular Socket.recv() may return less than the requested number of bytes,
        dependning on what's in the OS buffer.  MSG_WAITALL is not available
        on all platforms, but this should work everywhere.  This will return
        less than the requested amount if the remote end closes.
    
        This isn't optimized and is intended mostly for use in testing.
        """
        b = ''
        while len(b) < bytes:
            left = bytes - len(b)
            try:
                new = socket.recv(left)
            except Exception, e:
                #print('left bytes = %d out of %d'  % (left, bytes))
                raise e
            if new == '':
                break # eof
            b += new
        return b
    
    def _sendMsg(self, s, req):
        try: 
            msg = self._buildMsg(req)
            wirelog.debug('write -> %s' % msg[:80])
            s.send(msg)
        except:
            # TODO: Raise instead?
            wirelog.exception('Error sending msg over socket')
            
    def _sendRequest(self, s, msg):
        self._sendMsg(s, msg)
        reply = self._readMsg(s)
        return reply
        
    def _isOk(self, msg):
        """
        @type msg: str[]
        @return: True if myth response message indicates request completed OK, false otherwise
        """
        if msg == None or len(msg) == 0:
            return False
        else:
            return msg[0].upper() == 'OK'

# =============================================================================
class ConnectionFactory(pool.PoolableFactory):
    
    def __init__(self, *args, **kwargs):
        self.settings = kwargs['settings']
        self.translator = kwargs['translator']
        self.platform = kwargs['platform']
        self.bus = kwargs['bus']
    
    def create(self):
        conn = Connection(self.settings, self.translator, self.platform, self.bus)
        return conn
    
    def destroy(self, conn):
        conn.close()
        del conn
