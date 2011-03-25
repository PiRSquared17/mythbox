#
#  MythBox for XBMC - http://mythbox.googlecode.com
#  Copyright (C) 2011 analogue@yahoo.com
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
import xbmcaddon
import xbmcgui
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
            # gotta be a better way to detect ipad/iphone/atv
            if 'USER' in os.environ and os.environ['USER'] in ('mobile','frontrow',):
                __instance = IOSPlatform()
            else: 
                __instance = MacPlatform()
        else:
            log.error('ERROR: Platform check did not match win32, linux, darwin, or iOS. Was %s instead' % sys.platform)
            __instance = UnixPlatform()
    return __instance


def requireDir(dir):
    '''Create dir with missing path segments and return for chaining'''
    if not os.path.exists(dir):
        os.makedirs(dir)
    return dir


class Platform(object):

    def __init__(self, *args, **kwargs):
        self.addon = xbmcaddon.Addon('script.mythbox')
        requireDir(self.getScriptDataDir())
        requireDir(self.getCacheDir())

    def addLibsToSysPath(self):
        '''Add 3rd party libs in ${scriptdir}/resources/lib to the PYTHONPATH'''
        libs = [
            'pyxcoder', 
            'decorator', 
            'odict',
            'bidict', 
            'elementtree', 
            'tvdb_api', 
            'tvrage',
            'themoviedb', 
            'IMDbPY', 
            'simplejson', 
            'mysql-connector-python',
            'python-twitter',
            'twisted',
            'zope.interface',
            'mockito',
            'unittest2',
            'unittest']
        
        for lib in libs:
            sys.path.append(os.path.join(self.getScriptDir(), 'resources', 'lib', lib))
        
        sys.path.append(os.path.join(self.getScriptDir(), 'resources', 'test'))
            
        for i, path in enumerate(sys.path):    
            log.debug('syspath[%d] = %s' % (i, path))
    
    def getName(self):
        return "N/A"
    
    def getXbmcLog(self):
        raise Exception('abstract method')

        #  Linux
        # 
        #  CStdString userHome;
        #    769   if (getenv("HOME"))
        #    770     userHome = getenv("HOME");
        #    771   else
        #    772     userHome = "/root";
        #    773 
        #    774   CStdString xbmcBinPath, xbmcPath;
        #    775   CUtil::GetHomePath(xbmcBinPath, "XBMC_BIN_HOME");
        #    776   xbmcPath = getenv("XBMC_HOME");
        #    777 
        #    778   if (xbmcPath.IsEmpty())
        #    779   {
        #    780     xbmcPath = INSTALL_PATH;
        #    781     /* Check if xbmc binaries and arch independent data files are being kept in
        #    782      * separate locations. */
        #    783     if (!CFile::Exists(URIUtils::AddFileToFolder(xbmcPath, "language")))
        #    784     {
        #    785       /* Attempt to locate arch independent data files. */
        #    786       CUtil::GetHomePath(xbmcPath);
        #    787       if (!CFile::Exists(URIUtils::AddFileToFolder(xbmcPath, "language")))
        #    788       {
        #    789         fprintf(stderr, "Unable to find path to XBMC data files!\n");
        #    790         exit(1);
        #    791       }
        #    792     }
        #    793   }
    
        #    OSX
        #
        #            // xbmc.log file location
        #    894     #if defined(__arm__)
        #    895       strTempPath = userHome + "/Library/Preferences";
        #    896     #else
        #    897       strTempPath = userHome + "/Library/Logs";
        #    898     #endif
        #    899     URIUtils::AddSlashAtEnd(strTempPath);
        #    900     g_settings.m_logFolder = strTempPath;
            
        # 
        # CSettings
        #
        #          #ifdef __APPLE__
        #    111     CStdString logDir = getenv("HOME");
        #    112     logDir += "/Library/Logs/";
        #    113     m_logFolder = logDir;
        #    114   #else
        #    115     m_logFolder = "special://home/";              // log file location
        #    116   #endif
            
        return os.path.join(xbmc.translatePath())
    
    def getScriptDir(self):
        '''
        @return: directory that this xbmc script resides in.
        
        linux  : ~/.xbmc/addons/script.mythbox
        windows: c:\Documents and Settings\[user]\Application Data\XBMC\addons\script.mythbox
        mac    : ~/Library/Application Support/XBMC/addons/script.mythbox
        '''
        return self.addon.getAddonInfo('path')
    
    def getScriptDataDir(self):
        '''
        @return: directory for storing user settings for this xbmc script.
        
        linux  : ~/.xbmc/userdata/addon_data/script.mythbox
        windows: c:\Documents and Settings\[user]\Application Data\XBMC\UserData\addon_data\script.mythbox
        mac    : ~/Library/Application Support/XBMC/UserData/addon_data/script.mythbox
        '''
        return xbmc.translatePath(self.addon.getAddonInfo('profile'))
    
    def getCacheDir(self):
        return os.path.join(self.getScriptDataDir(), 'cache')
    
    def getUserDataDir(self):
        return xbmc.translatePath('special://userdata')
    
    def getHostname(self):
        try:
            return socket.gethostname()
        except:
            return xbmc.getIPAddress()
     
    def isUnix(self):
        return False
    
    def getVersion(self):
        return self.addon.getAddonInfo('version')
            
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
    
    def getFFMpegPath(self, prompt=False):
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
        s = u'XBMC.Notification(%s,%s,%s)' % (title, text, millis)
        xbmc.executebuiltin(s)

    def requireFFMpeg(self, path):
        if os.path.exists(path) and os.path.isfile(path):
            return

        dir, exe = os.path.split(path)
        requireDir(dir)
        
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
        
    def getName(self):
        return "unix"
    
    def isUnix(self):
        return True
        
    def getFFMpegPath(self, prompt=False):
        f = '/usr/bin/ffmpeg'
        if os.path.exists(f) and os.path.isfile(f):
            return f
        else:
            if prompt:
                xbmcgui.Dialog().ok('Error', 'Please install ffmpeg.', 'Ubuntu/Debian: apt-get install ffmpeg')
            raise Exception, 'ffmpeg not installed'

    def getDefaultRecordingsDir(self):
        return '/var/lib/mythtv/recordings'

    def getXbmcLog(self):    
        return os.path.join(xbmc.translatePath('special://temp'), 'xbmc.log')
    

class WindowsPlatform(Platform):

    def __init__(self, *args, **kwargs):
        Platform.__init__(self, *args, **kwargs)
        self.ffmpegUrl = 'http://mythbox.googlecode.com/hg/resources/bin/win32/ffmpeg.exe'
    
    def getName(self):
        return "windows"

    def getFFMpegPath(self, prompt=False):
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

    def getFFMpegPath(self, prompt=False):
        path = os.path.join(self.getScriptDataDir(), 'ffmpeg')
        self.requireFFMpeg(path)
        return path

    def getDefaultRecordingsDir(self):
        return '/change/me'

    
class IOSPlatform(Platform):
    
    def __init__(self, *args, **kwargs):
        Platform.__init__(self, *args, **kwargs)
        
    def getName(self):
        return 'ios'

    def getFFMpegPath(self, prompt=False):
        f = '/usr/local/bin/ffmpeg'
        if os.path.exists(f) and os.path.isfile(f):
            return f
        else:
            if prompt:
                xbmcgui.Dialog().ok('Error', 'Please install ffmpeg via Cydia', '1) Sections > Repositories > ModMyi.com > Install', '2) Sections > Multimedia > FFmpeg > Install')
            raise Exception, 'ffmpeg not installed'

    def getDefaultRecordingsDir(self):
        return '/var/mobile'
