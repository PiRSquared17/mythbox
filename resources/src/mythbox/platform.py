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
import sys
import xbmc
import urllib
import stat

log = logging.getLogger('mythbox.core')

__instance = None


def getPlatform():
    global __instance
    if not __instance:
        if 'win32' in sys.platform:
            __instance = WindowsPlatform()
        elif 'linux' in sys.platform:
            __instance = UnixPlatform()
        elif 'darwin' in sys.platform:
            __instance = MacPlatform()
        else:
            log.error('ERROR: Platform check did not match win32, linux, or darwin. Was %s instead' % sys.platform)
            __instance = UnixPlatform()
    return __instance


class Platform(object):

    def __init__(self, *args, **kwargs):
        try:
            import xbmcaddon
            self.addon = xbmcaddon.Addon('script.mythbox')
            self.cwd = self.addon.getAddonInfo('path')
        except:
            self.addon = None
            # os.getcwd() can and does change @ runtime. retain and use initial value
            self.cwd = os.getcwd()
            
        self._scriptDataDir = None

        datadir = self.getScriptDataDir()
        if not os.path.exists(datadir): 
            os.makedirs(datadir)
        
        cachedir = self.getCacheDir()
        if not os.path.exists(cachedir): 
            os.makedirs(cachedir)
            
        #self.requireFFMpeg()

    def addLibsToSysPath(self):
        '''Add 3rd party libs in ${scriptdir}/resources/lib to the PYTHONPATH'''
        libs = [
            'pyxcoder', 
            'decorator', 
            'odict', 
            'elementtree', 
            'tvdb_api', 
            'tvrage',
            'themoviedb', 
            'IMDbPY', 
            'simplejson', 
            'mysql-connector-python',
            'python-twitter',
            'twisted',
            'zope.interface']
        
        for lib in libs:
            sys.path.append(os.path.join(self.getScriptDir(), 'resources', 'lib', lib))
            
        for i, path in enumerate(sys.path):    
            log.debug('syspath[%d] = %s' % (i, path))
    
    def getName(self):
        return "N/A"
    
    def getScriptDir(self):
        '''
        @return: directory that this xbmc script resides in.
        
        linux  : ~/.xbmc/addons/script.mythbox
        windows: c:\Documents and Settings\[user]\Application Data\XBMC\addons\script.mythbox
        mac    : ~/Library/Application Support/XBMC/addons/script.mythbox
        '''
        try:
            return self.addon.getAddonInfo('path')
        except:
            return self.cwd
    
    def getScriptDataDir(self):
        '''
        @return: directory for storing user settings for this xbmc script.
        
        linux  : ~/.xbmc/userdata/addon_data/script.mythbox
        windows: c:\Documents and Settings\[user]\Application Data\XBMC\UserData\addon_data\script.mythbox
        mac    : ~/Library/Application Support/XBMC/UserData/addon_data/script.mythbox
        '''
        if self._scriptDataDir is None:
            try:
                self._scriptDataDir = xbmc.translatePath(self.addon.getAddonInfo('profile'))
            except:
                self._scriptDataDir = xbmc.translatePath("T:\\script_data") + os.sep + os.path.basename(self.getScriptDir())
        return self._scriptDataDir
    
    def getCacheDir(self):
        return os.path.join(self.getScriptDataDir(), 'cache')
    
    def getHostname(self):
        try:
            return socket.gethostname()
        except:
            return xbmc.getIPAddress()
        
    def isUnix(self):
        return False
    
    def __repr__(self):
        bar = "=" * 80
        s = bar + \
"""
hostname        = %s
platform        = %s 
script dir      = %s
script data dir = %s
""" % (self.getHostname(), type(self).__name__, self.getScriptDir(), self.getScriptDataDir())
        s += bar
        return s
    
    def getFFMpegPath(self):
        return ''

    def getDefaultRecordingsDir(self):
        return ''

    def getMediaPath(self, mediaFile):
        # TODO: Fix when we support multiple skins
        return os.path.join(self.getScriptDir(), 'resources', 'skins', 'Default', 'media', mediaFile)
        
    def showPopup(self, title, text, millis=10000):
        # filter all commas out of text since they delimit args
        title = title.replace(',', ';')
        text = text.replace(',', ';')
        s = 'XBMC.Notification(%s,%s,%s)'  % (title, text, millis)
        xbmc.executebuiltin(s)

    def requireFFMpeg(self, path):
        if os.path.exists(path) and os.path.isfile(path):
            return

        dir, exe = os.path.split(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        
        self.showPopup('Downloading FFMPEG', 'This may take a couple mins...hang tight', millis=10000)
        filename, headers = urllib.urlretrieve(self.ffmpegUrl, path)
            
        if os.path.exists(path) and os.path.isfile(path):
            os.chmod(path, stat.S_IRWXG|stat.S_IRWXO|stat.S_IRWXU)
            self.showPopup('Downloading FFMPEG', 'All done!', millis=10000)
            return
        
        raise Exception, 'FFMpeg could not be downloaded'


class UnixPlatform(Platform):

    def __init__(self, *args, **kwargs):
        Platform.__init__(self, *args, **kwargs)
        self.ffmpegUrl = '/usr/bin/ffmpeg'
        
    def getName(self):
        return "unix"
    
    def isUnix(self):
        return True
        
    def getFFMpegPath(self):
        return '/usr/bin/ffmpeg'

#    def getFFMpegPath(self):
#        path = os.path.join(self.getScriptDataDir(), 'ffmpeg')
#        self.requireFFMpeg(path)
#        return path

    def getDefaultRecordingsDir(self):
        return '/var/lib/mythtv/recordings'
    

class WindowsPlatform(Platform):

    def __init__(self, *args, **kwargs):
        Platform.__init__(self, *args, **kwargs)
        self.ffmpegUrl = 'http://mythbox.googlecode.com/hg/resources/bin/win32/ffmpeg.exe'
    
    def getName(self):
        return "windows"

    def getFFMpegPath(self):
        path = os.path.join(self.getScriptDataDir(), 'ffmpeg.exe')
        self.requireFFMpeg(path)
        return path
    
    def getDefaultRecordingsDir(self):
        return 'c:\\change\\me'

        
class MacPlatform(Platform):

    def __init__(self, *args, **kwargs):
        Platform.__init__(self, *args, **kwargs)
        self.ffmpegUrl = 'http://mythbox.googlecode.com/hg/resources/bin/osx/ffmpeg'
        
    def getName(self):
        return 'mac'

    def getFFMpegPath(self):
        path = os.path.join(self.getScriptDataDir(), 'ffmpeg')
        self.requireFFMpeg(path)
        return path

    def getDefaultRecordingsDir(self):
        return '/change/me'
