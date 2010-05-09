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
import logging
import os
import socket
import string

from mythbox.bus import Event, EventBus
from mythbox.mythtv.db import MythDatabase
from mythbox.platform import WindowsPlatform, MacPlatform, UnixPlatform
from xml.dom import minidom

slog = logging.getLogger('mythbox.settings')

# =============================================================================
class SettingsException(Exception):
    """Thrown when a setting fails validation in MythSettings""" 
    pass

# =============================================================================
class MythSettings(object):
    """
    Settings reside in $HOME/.xbmc/userdata/script_data/MythBox/settings.xml
    """

    def __init__(self, platform, translator, filename='settings.xml', bus=None):
        self.platform = platform
        self.initDefaults()
        self.d = self.defaults.copy()
        self.translator = translator
        self.settingsFilename = filename
        self.settingsPath = os.path.join(self.platform.getScriptDataDir(), self.settingsFilename)
        self.bus = None
        self.listeners = []
        try:
            self.load()
        except SettingsException:
            pass
        self.bus = bus # defer event publishing until after initial load

    def getFFMpegPath(self): return self.get('paths_ffmpeg')
    def setFFMpegPath(self, ffmpegPath): self.put('paths_ffmpeg', ffmpegPath)
 
    def setLiveTvBuffer(self, sizeKB): self.put('mythtv_minlivebufsize', '%s' % sizeKB)
    def getLiveTvBuffer(self): return int(self.get('mythtv_minlivebufsize'))

    def setLiveTvTimeout(self, seconds): self.put('mythtv_tunewait', '%s' % seconds)
    def getLiveTvTimeout(self): int(self.get('mythtv_tunewait'))
     
    def isConfirmOnDelete(self): return self.getBoolean('confirm_on_delete')
    def setConfirmOnDelete(self, b): self.put('confirm_on_delete', ['False', 'True'][b])
            
    def getMySqlHost(self): return self.get('mysql_host')
    def setMySqlHost(self, host): self.put('mysql_host', host)

    def setMySqlPort(self, port): self.put('mysql_port', '%s' % port)
    def getMySqlPort(self): return int(self.get('mysql_port'))

    def getMySqlDatabase(self): return self.get('mysql_database')
    def setMySqlDatabase(self, db): self.put('mysql_database', db)
    
    def getMySqlUser(self): return self.get('mysql_user')
    def setMySqlUser(self, user): self.put('mysql_user', user)

    def getMySqlPassword(self): return self.get('mysql_password')
    def setMySqlPassword(self, password): self.put('mysql_password', password)

    def getMythTvHost(self): return self.get('mythtv_host')
    def setMythTvHost(self, host): self.put('mythtv_host', host)
    
    def getMythTvPort(self): return int(self.get('mythtv_port'))
    def setMythTvPort(self, port): self.put('mythtv_port', '%s' % port)

    def addListener(self, listener):
        self.listeners.append(listener)
        
    def setRecordingDirs(self, dirs):
        """
        @type dirs: str  - one or more separated by os.pathsep      
        @type dirs: str[] 
        """
        if type(dirs) == str:
            self.put('paths_recordedprefix', dirs)
        elif type(dirs) == list:
            self.put('paths_recordedprefix', os.pathsep.join(dirs))
        else:
            raise Exception("unsupported param type for dirs: %s" + type(dirs))
        
    def getRecordingDirs(self):
        """
        @return: MythTV recording directories on the local filesystem
        @rtype: str[]
        """
        return self.get('paths_recordedprefix').split(os.pathsep)
        
    def get(self, tag):
        if self.d.has_key(tag):
            return self.d[tag]
        else:
            return None

    def put(self, tag, value):
        old = None
        if self.d.has_key(tag):
            old = self.d[tag]
        self.d[tag] = value
        
        # Only notify of changes if the new value is different
        if old is not None and old != value:
            # TODO: Listener support deprecated in favor of event bus
            for listener in self.listeners:
                listener.settingChanged(tag, old, value)
            if self.bus:
                self.bus.publish({'id': Event.SETTING_CHANGED, 'tag': tag, 'old': old, 'new': value})
                
        #if slog.isEnabledFor(logging.DEBUG):
        #    pvalue = value
        #    if 'password' in tag:
        #        pvalue = '*secret*'
        #    slog.debug("=> settings['%s'] = %s" % (tag, pvalue))

    def initDefaults(self):
        self.defaults = {
            'mythtv_host'             : 'localhost',
            'mythtv_port'             : '6543',
            'mysql_host'              : 'localhost',
            'mysql_port'              : '3306',
            'mysql_database'          : 'mythconverg',
            'mysql_user'              : 'mythtv',
            'mysql_password'          : 'change_me',
            'mysql_encoding_override' : 'latin1',
            'paths_recordedprefix'    : self.platform.getDefaultRecordingsDir(),
            'paths_ffmpeg'            : self.platform.getFFMpegPath(),
            'recorded_view_by'        : '2', 
            'upcoming_view_by'        : '2',
            'confirm_on_delete'       : 'True',
            'fanart_tvdb'             : 'True',
            'fanart_tmdb'             : 'True',
            'fanart_imdb'             : 'True',
            'fanart_google'           : 'True',
            'feeds_twitter'           : 'mythboxfeed',
            'lirc_hack'               : 'False',
            'logging_enabled'         : 'False',
            'schedules_last_selected' : '0',
            'livetv_last_selected'    : '0',
            'recordings_last_selected': '0',
            'recordings_sort_by'      : 'Date',
            'recordings_sort_ascending':'False',
            'recordings_recording_group':'Default',
            'tv_guide_last_selected'  : '0'
        }

    def load(self):
        """
        @raise SettingsException: when settings file not found
        """
        filePath = self.settingsPath
        slog.debug("Loading settings from %s" % filePath)
        if not os.path.exists(filePath):
            raise SettingsException('File %s does not exist.' % filePath)
        else:
            # use saved configuration
            dom = minidom.parse(filePath)
            mythtv = dom.getElementsByTagName('mythtv')[0]
            assert(mythtv is not None)
            for tag in self.defaults.keys():
                results = mythtv.getElementsByTagName(tag)
                if len(results) > 0:
                    #print results[0].toxml()
                    self.d[tag] = string.strip(results[0].firstChild.nodeValue)
                else:
                    slog.error('no tag found for %s ' % tag)
                    
    def save(self):
        settingsDir = self.platform.getScriptDataDir()
        
        if not os.path.exists(settingsDir):
            slog.debug('Creating mythbox settings dir %s' % self.platform.getScriptDataDir())
            os.makedirs(settingsDir)

        dom = minidom.parseString('<mythtv></mythtv>')
        for key in self.d.keys():
            e = dom.createElement(key)
            n = dom.createTextNode(string.strip(self.d[key]))
            e.appendChild(n)
            dom.childNodes[0].appendChild(e)
        slog.debug('Saving settings to %s' % self.settingsPath)
        fh = file(self.settingsPath, 'w')
        fh.write(dom.toxml())
        fh.close()

    def getBoolean(self, tag):
        return self.get(tag) in ('True', 'true', '1')
    
    def verify(self):
        """
        @raise SettingsException: on invalid settings
        """
        for tag in self.defaults.keys():
            if self.get(tag) is None:
                raise SettingsException('%s %s' % (self.translator.get(34), tag))
        
        MythSettings.verifyMythTVHost(self.getMythTvHost())
        MythSettings.verifyMythTVPort(self.get('mythtv_port'))
        MythSettings.verifyMySQLHost(self.get('mysql_host'))
        MythSettings.verifyMySQLPort(self.get('mysql_port'))
        MythSettings.verifyMySQLDatabase(self.get('mysql_database'))
        MythSettings.verifyString(self.get('mysql_user'), 'Enter MySQL user. Hint: mythtv is the MythTV default')
        MythSettings.verifyRecordingDirs(self.get('paths_recordedprefix'))
        MythSettings.verifyFFMpeg(self.get('paths_ffmpeg'), self.platform)
        MythSettings.verifyBoolean(self.get('confirm_on_delete'), 'Confirm on delete must be True or False')
        self.verifyMySQLConnectivity()
        self.verifyMythTVConnectivity()
        slog.debug('verified settings')

    def verifyMythTVConnectivity(self):
        try:
            from mythbox.mythtv.conn import Connection
            session = Connection(self, translator=self.translator, platform=self.platform, bus=EventBus(), db=None)
            session.close()
        except Exception, ex:
            slog.exception(ex)
            raise SettingsException('Connection to MythTV failed: %s' % ex)
    
    def verifyMySQLConnectivity(self):
        try:
            db = MythDatabase(self, self.translator)
            db.close()
            del db
        except Exception, ex:
            raise SettingsException("Connect to MySQL failed: %s" % ex)
    
    def __repr__(self):
        sb = ''
        for tag in self.defaults.keys():
            sb += '%s = %s\n' % (tag, [self.get(tag), '<EMPTY>'][self.get(tag) is None]) 
        return sb
            
    @staticmethod
    def verifyFFMpeg(filepath, p): # =platform.getPlatform()
        MythSettings.verifyString(filepath, "Enter the absolute path of your ffmpeg executable")
        
        if not os.path.exists(filepath):
            raise SettingsException("ffmpeg executable '%s' does not exist." % filepath)
        
        if not os.path.isfile(filepath):
            raise SettingsException("ffmpeg executable '%s' is not a file" % filepath)
        
        ptype = type(p)
        if ptype in (WindowsPlatform,):
            pass
        elif ptype in (UnixPlatform, MacPlatform):
            if not os.access(filepath, os.X_OK):
                raise SettingsException("ffmpeg executable '%s' is not chmod +x" % filepath)
        else:
            raise SettingsException('Verifying FFMPEG - unsupported platform: %s' % ptype)
    
    @staticmethod    
    def verifyRecordingDirs(recordingDirs):
        MythSettings.verifyString(recordingDirs, "Enter one or more '%s' separated MythTV recording directories" % os.pathsep)
        for dir in recordingDirs.split(os.pathsep):
            if not os.path.exists(dir):
                raise SettingsException("Recording directory '%s' does not exist." % dir)
            if not os.path.isdir(dir):
                raise SettingsException("Recording directory '%s' is not a directory." % dir)
    
    @staticmethod        
    def verifyMythTVHost(host):
        MythSettings.verifyString(host, 'Enter MythTV master backend hostname or IP address')
        MythSettings.verifyHostnameOrIPAddress(host, "Hostname '%s' cannot be resolved to an IP address."%host)
    
    @staticmethod
    def verifyMythTVPort(port):
        errMsg = 'Enter MythTV master backend port. Hint: 6543 is the MythTV default'
        MythSettings.verifyString(port, errMsg)
        MythSettings.verifyNumberBetween(port, 1, 65536, errMsg)
        
    @staticmethod    
    def verifyMySQLHost(host):
        MythSettings.verifyString(host, 'Enter MySQL server hostname or IP address')
        MythSettings.verifyHostnameOrIPAddress(host, "Hostname '%s' cannot be resolved to an IP address." % host)

    @staticmethod
    def verifyMySQLPort(port):
        errMsg = 'Enter MySQL server port. Hint: 3306 is the MySQL default'
        MythSettings.verifyString(port, errMsg)
        MythSettings.verifyNumberBetween(port, 0, 65336, errMsg)

    @staticmethod
    def verifyMySQLUser(user):
        errMsg = 'Enter MySQL user name for MythTV database'
        MythSettings.verifyString(user, errMsg)
        
    @staticmethod    
    def verifyMySQLDatabase(dbName):
        MythSettings.verifyString(dbName, 'Enter MySQL database name. Hint: mythconverg is the MythTV default')
    
    @staticmethod    
    def verifyLiveTVBufferSize(numKB):
        MythSettings.verifyString(numKB, 'Live TV buffer size must be between 1,000 and 20,000 KB')
        MythSettings.verifyNumberBetween(numKB, 1000, 20000, 'Live TV buffer size must be between 1,000 and 20,000 KB')

    @staticmethod    
    def verifyLiveTVTimeout(numSecs):
        MythSettings.verifyString(numSecs, 'Live TV timeout must be between 10 and 180 seconds')
        MythSettings.verifyNumberBetween(numSecs, 10, 180, 'Live TV timeout must be between 10 and 180')
        
    @staticmethod    
    def verifyHostnameOrIPAddress(host, errMsg):
        try:
            socket.gethostbyname(host)
        except Exception:
            raise SettingsException("%s %s" % (errMsg, ''))

    @staticmethod
    def verifyBoolean(s, errMsg):
        MythSettings.verifyString(s, errMsg)
        if not s in ('True', 'False', '0', '1'):
            raise SettingsException(errMsg)
            
    @staticmethod
    def verifyString(s, errMsg):
        """
        @param s: string to verify
        @param errMsg: Error message
        @raise SettingsException: if passed in string is None or blank. 
        """
        if s is None or s.strip() == '':
            raise SettingsException(errMsg)
    
    @staticmethod    
    def verifyNumberBetween(num, min, max, errMsg):
        n = None
        try:
            n = int(num)
        except Exception:
            raise SettingsException("%s %s" % (errMsg, ''))
        if not min <= n <= max:
            raise SettingsException(errMsg)