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
import threading
import xbmcgui
import xbmc

from mythbox.mythtv.db import inject_db
from mythbox.mythtv.conn import inject_conn
from mythbox.mythtv.domain import Channel
from mythbox.mythtv.conn import ServerException
from mythbox.ui.player import MythPlayer, NoOpCommercialSkipper
from mythbox.ui.toolkit import *
from mythbox.util import catchall, catchall_ui, timed, run_async, lirc_hack, ui_locked, coalesce, ui_locked2
from odict import odict

log = logging.getLogger('mythbox.ui')
    
# =============================================================================
class BaseLiveTvBrain(object):

    def __init__(self, settings):
        self.settings = settings          
        self.tuner = None

    def watchLiveTV(self, channel):
        raise Exception, 'Subclass should implement'
        
    @inject_conn
    def _findAvailableTunerWithChannel(self, channel):
        """
        @param channel: Channel to find a tuner for
        @return: Tuner that is availble for livetv, None otherwise
        @raise ServerException: If a tuner is not currently available
        """
        # 1. Check at least one tuner available
        numFreeTuners = self.conn().getNumFreeTuners()
        if numFreeTuners <= 0:
            raise ServerException('All tuner(s) are busy.')
        
        # 2. Make sure available tuner can watch requested channel
        tuners = self.conn().getTuners()
        for tuner in tuners:
            if not tuner.isRecording() and tuner.hasChannel(channel):
                log.debug("Found tuner %s to view channel %s" % (tuner.tunerId, channel.getChannelNumber()))
                return tuner
            
        raise ServerException('Tuner(s) with channel %s are all busy.' % channel.getChannelNumber())
        
# =============================================================================
class MythLiveTvBrain(BaseLiveTvBrain):
    """
    Orchestrates live tv using XBMC's built in myth:// URL support
    """

    def __init__(self, settings):
        BaseLiveTvBrain.__init__(self, settings)

    def watchLiveTV(self, channel):
        try:
            self.tuner = self._findAvailableTunerWithChannel(channel)
            livePlayer = MythLiveTvPlayer()
            livePlayer.watchChannel(self.settings, channel)
            #del livePlayer # induce GC so on* callbacks unregistered
            return self.tuner
        except ServerException, se:
            xbmcgui.Dialog().ok('Info', str(se))

# ==============================================================================
class MythLiveTvPlayer(xbmc.Player):
    """
    Plays live tv using XBMC's built in myth:// URL support
    """
    
    def __init__(self):
        xbmc.Player.__init__(self)    
        self._active = True
    
    def watchChannel(self, settings, channel):
        # This player doesn't care about on* callbacks, so no need to wait for playback
        # completion. 

        # url must not be unicode!
        url = 'myth://%s:%s@%s:%s/channels/%s.ts' % (
            str(settings.get('mysql_user')),
            str(settings.get('mysql_password')),
            str(settings.get('mythtv_host')),
            str(settings.get('mythtv_port')),
            str(channel.getChannelNumber()))
        self.play(url)

# =============================================================================
class FileLiveTvBrain(BaseLiveTvBrain):
    """
    Orchestrates live tv using the livetv recording available on the filesystem
    """
    def __init__(self, settings):
        BaseLiveTvBrain.__init__(self, settings)
            
    def watchLiveTV(self, channel):
        """
        Starts watching LiveTV for the given channel. Blocks until stopped, LiveTV ends, or error occurs.
        
        @param channel: Channel the couch potato would like to watch
        @return: Tuner picked to watch live tv
        @raise ServerException: When tuner not available
        """
        liveBuffer = max(int(self.settings.get('mythtv_minlivebufsize')), 1024)
        liveTimeout = max(int(self.settings.get('mythtv_tunewait')), 60)
        
        progress = xbmcgui.DialogProgress()
        progress.create('Watch TV', 'Finding tuner...')
        self.tuner = self._findAvailableTunerWithChannel(channel)
        
        progress.update(20, '', 'Tuning channel...')
        self.tuner.startLiveTV(channel.getChannelNumber())
        
        try:
            progress.update(40, '', 'Starting recording...')
            self.tuner.waitForRecordingToStart(timeout=liveTimeout)

            # callback to update progress dialog
            def updateBuffered(kb):
                progress.update(70, '', 'Buffering %sKB ...' % kb)
                
            progress.update(60, '', 'Buffering...')
            self.tuner.waitForRecordingWritten(numKB=liveBuffer, timeout=liveTimeout, callback=updateBuffered)
            
            progress.update(80, '', 'Starting player...')
            whatsPlaying = self.tuner.getWhatsPlaying()
            log.debug('Currently playing = %s' % whatsPlaying.getLocalPath())
            
            progress.close()
            livePlayer = FileLiveTvPlayer()
            livePlayer.addListener(self)
            livePlayer.playRecording(whatsPlaying, NoOpCommercialSkipper(livePlayer, whatsPlaying))
            # del livePlayer # induce GC so on* callbacks unregistered
        except:
            # If things went south after starting livetv, attempt to stop livetv
            try:
                if self.tuner.isRecording():
                    log.info('Stopping LiveTV because start live TV failed...')
                    self.tuner.stopLiveTV()
            except:
                log.exception('Trying to clean up after start liveTV failed')
            raise  # propagate
                
        return self.tuner
    
    def getLiveTVStatus(self):
        return self.tuner.getLiveTVStatus()

    #
    # Callbacks initiated by LiveTVPlayer
    # 
    def onPlayBackStarted(self):
        pass
    
    def onPlayBackStopped(self):
        self.tuner.stopLiveTV()
            
    def onPlayBackEnded(self):
        self.tuner.stopLiveTV()
    
# =============================================================================
class FileLiveTvPlayer(MythPlayer):
    """
    Play live tv using the livetv recording available on the filesystem
    """
    
    # TODO: Callback listener registration needs to be pushed down to MythPlayer
    #       eventually making this class obsolete.
    
    def __init__(self):
        MythPlayer.__init__(self)
        self.listeners = []  
    
    def addListener(self, listener):
        self.listeners.append(listener)
    
    @catchall    
    def onPlayBackStarted(self):
        log.debug('> onPlayBackStarted')
        if self._active:
            try:
                for listener in self.listeners:
                    try: 
                        listener.onPlayBackStarted()
                    except:
                        log.exception('listener %s callback blew up' % listener)
            finally:
                log.debug('< onPlayBackStarted')

    @catchall
    def onPlayBackStopped(self):
        log.debug('> onPlayBackStopped')
        if self._active:
            try:
                for listener in self.listeners:
                    try: 
                        listener.onPlayBackStopped()
                    except:
                        log.exception('listener %s callback blew up' % listener)
            finally:
                self._playbackCompletedLock.set()
                log.debug('< onPlayBackStopped')
            
    @catchall
    def onPlayBackEnded(self):
        log.debug('> onPlayBackEnded')
        if self._active:
            try:
                for listener in self.listeners:
                    try: 
                        listener.onPlayBackEnded()
                    except:
                        log.exception('listener %s callback blew up' % listener)
            finally:
                self._playbackCompletedLock.set()
                log.debug('< onPlayBackEnded')

    def _reset(self, program):
        """
        Overrides super impl
        """
        self._program = program
        self._playbackCompletedLock = threading.Event()
        self._playbackCompletedLock.clear()

# ==============================================================================
class LiveTvWindow(BaseWindow):
    
    @timed
    def __init__(self, *args, **kwargs):
        BaseWindow.__init__(self, *args, **kwargs)
        
        self.settings = kwargs['settings']
        self.translator = kwargs['translator']
        self.mythChannelIconCache = kwargs['mythChannelIconCache']
        self.platform = kwargs['platform']
        self.fanArt = kwargs['fanArt']

        self.channels = None                     # Channels sorted and merged (if multiple tuners)
        self.channelsById = None                 # {int channelId:Channel}
        self.programs = None                     # [TVProgram]
        self.listItemsByChannel = odict()        # {Channel:ListItem}
        self.closed = False
        
        self.lastSelected = int(self.settings.get('livetv_last_selected'))
        
    @catchall_ui
    def onInit(self):
        if not self.win:
            self.win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            self.channelsListBox = self.getControl(600)
            self.refreshButton = self.getControl(250)
        
        if self.programs:
            # only refresh if program data stale
            for p in self.programs:
                if not p.isShowing():
                    self.refresh()
                    break;
        else:
            self.refresh()

    @window_busy
    def refresh(self):
        self.loadPrograms()
        self.render()
        self.renderPosters()
    
    @lirc_hack    
    @catchall    
    def onClick(self, controlId):
        source = self.getControl(controlId)
        if source == self.channelsListBox: 
            self.watchSelectedChannel()
        elif source == self.refreshButton:
            self.refresh()
             
    def onFocus(self, controlId):
        pass
            
    @catchall_ui
    @lirc_hack            
    def onAction(self, action):
        if action.getId() in (Action.PREVIOUS_MENU, Action.PARENT_DIR):
            self.closed = True
            self.settings.put('livetv_last_selected', str(self.channelsListBox.getSelectedPosition()))
            self.close()

    @window_busy
    @inject_conn
    def watchSelectedChannel(self):
        self.lastSelected = self.channelsListBox.getSelectedPosition()
        listItem = self.channelsListBox.getSelectedItem()
        channelId = int(listItem.getProperty('channelId'))
        channel = self.channelsById[channelId]
        
        # Use myth:// based player for 0.21
        # Use file based player for 0.22 until myth:// supports 0.22 
        brain = self.conn().protocol.getLiveTvBrain(self.settings)
        
        try:
            try:
                brain.watchLiveTV(channel)
            except Exception, e:
                log.error(e)
                xbmcgui.Dialog().ok('Error', '', str(e))
        finally:
            pass    
            #del brain

    @timed
    @inject_db
    def loadChannels(self):
        """
        @attention: Cached after initial invocation
        @postcondition: self.channels contains list of channels in presentation order
        @postcondition: self.channelsById contains channels keyed on channelId
        """
        if self.channels == None:
            self.channels = Channel.mergeChannels(self.db().getChannels())
            self.channels.sort(key=Channel.getSortableChannelNumber)
            self.channelsById = odict()
            for c in self.channels:
                self.channelsById[c.getChannelId()] = c

    @timed
    @inject_db
    def loadPrograms(self):
        self.loadChannels()
        now = datetime.datetime.now()
        self.programs = self.db().getTVGuideDataFlattened(now, now, self.channels)
        programsByChannelId = odict()
        
        for p in self.programs:
            programsByChannelId[p.getChannelId()] = p
        
        # make TVProgram accessible as Channel.currentProgram    
        for channelId, channel in self.channelsById.items():
            if programsByChannelId.has_key(channelId):
                channel.currentProgram = programsByChannelId[channelId]
            else:
                channel.currentProgram = None

    @ui_locked
    def render(self):
        log.debug('Rendering....')
        self.listItemsByChannel.clear()
        listItems = []

        @ui_locked2
        def buildListItems():
            for i, channel in enumerate(self.channels):
                #log.debug('Working channel: %d' %i)
                listItem = xbmcgui.ListItem()
                self.setListItemProperty(listItem, 'channelId', str(channel.getChannelId()))
                
                if channel.getIconPath():
                    cachedIcon = self.mythChannelIconCache.get(channel)
                    if cachedIcon:
                        self.setListItemProperty(listItem, 'channelIcon', cachedIcon)
                    
                self.setListItemProperty(listItem, 'channelName', channel.getChannelName())
                self.setListItemProperty(listItem, 'channelNumber', channel.getChannelNumber())
                self.setListItemProperty(listItem, 'callSign', channel.getCallSign())
                
                if channel.currentProgram:
                    self.setListItemProperty(listItem, 'title', channel.currentProgram.title())
                    self.setListItemProperty(listItem, 'description', channel.currentProgram.formattedDescription())
                    self.setListItemProperty(listItem, 'category', channel.currentProgram.category())
                    
                    if self.fanArt.hasPosters(channel.currentProgram):
                        channel.needsPoster = False
                        self.lookupPoster(listItem, channel)
                    else:
                        channel.needsPoster = True
                        self.setListItemProperty(listItem, 'poster', 'loading.gif')
                else:
                    self.setListItemProperty(listItem, 'title', 'No Data')
                    
                listItems.append(listItem)
                self.listItemsByChannel[channel] = listItem
        
        buildListItems()
        self.channelsListBox.reset()
        self.channelsListBox.addItems(listItems)
        self.channelsListBox.selectItem(self.lastSelected)
    
    def lookupPoster(self, listItem, channel):
        posterPath = self.fanArt.getRandomPoster(channel.currentProgram)
        if not posterPath:
            if channel.getIconPath():
                posterPath = self.mythChannelIconCache.get(channel)
                if not posterPath:
                    posterPath =  'mythbox-logo.png'
            else:
                posterPath = 'mythbox-logo.png'
        self.setListItemProperty(listItem, 'poster', posterPath)
        
    @run_async
    @catchall
    @coalesce
    def renderPosters(self):
        for channel in self.listItemsByChannel.keys():
            if self.closed: 
                return
            try:
                if channel.currentProgram and channel.needsPoster:
                    listItem = self.listItemsByChannel[channel]
                    self.lookupPoster(listItem, channel)
            except:
                log.exception('channel = %s' % channel)