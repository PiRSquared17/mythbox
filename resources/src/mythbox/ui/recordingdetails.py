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
import xbmcgui
import mythbox.msg as m

from mythbox.mythtv.db import inject_db
from mythbox.mythtv.conn import inject_conn
from mythbox.mythtv.domain import StatusException
from mythbox.mythtv.enums import JobType, JobStatus
from mythbox.ui.player import MountedPlayer, StreamingPlayer, NoOpCommercialSkipper, TrackingCommercialSkipper
from mythbox.ui.schedules import ScheduleDialog
from mythbox.ui.toolkit import Action, BaseWindow, window_busy
from mythbox.util import safe_str, catchall, catchall_ui, run_async, coalesce, to_kwargs

log = logging.getLogger('mythbox.ui')

class RecordingDetailsWindow(BaseWindow):
    
    def __init__(self, *args, **kwargs):
        BaseWindow.__init__(self, *args, **kwargs)
        [setattr(self,k,v) for k,v in kwargs.iteritems() if k in ('settings', 'translator', 'platform', 'fanArt', 'cachesByName', 'programIterator',)]
        [setattr(self,k,v) for k,v in self.cachesByName.iteritems() if k in ('mythChannelIconCache', 'mythThumbnailCache',)]
        
        self.t = self.translator.get
        self.program = self.programIterator.current() 
        self.isDeleted = False
        self.initialized = False
        self.streaming = self.settings.getBoolean('streaming_enabled')
            
    @catchall_ui
    def onInit(self):
        if not self.initialized:
            self.initialized = True
            self.win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            
            # Buttons
            self.playButton = self.getControl(250)
            self.playSkipButton = self.getControl(251)
            self.deleteButton = self.getControl(252)
            self.rerecordButton = self.getControl(253)
            self.firstInQueueButton = self.getControl(254)
            self.refreshButton = self.getControl(255)
            self.editScheduleButton = self.getControl(256)
            
            self.dispatcher = {
                self.playButton.getId()        : self.play,
                self.playSkipButton.getId()    : self.playWithCommSkip,
                self.deleteButton.getId()      : self.delete,
                self.rerecordButton.getId()    : self.rerecord,
                self.firstInQueueButton.getId(): self.moveToFrontOfJobQueue,
                self.refreshButton.getId()     : self.refresh,
                self.editScheduleButton.getId(): self.editSchedule
            }
            self.render()
        
    @inject_db    
    def autoexpire(self):
        self.db().setRecordedAutoexpire(
            self.program.getChannelId(), 
            self.program.starttime(), 
            not self.program.isAutoExpire())
        self.refresh()

    def delete(self):
        yes = True
        if self.settings.isConfirmOnDelete():
            yes = xbmcgui.Dialog().yesno(self.t(m.CONFIRMATION), self.t(m.ASK_DELETE_RECORDING))

        @run_async
        @catchall
        @inject_conn
        def deleteAsync(self):
            self.conn().deleteRecording(self.program)
            
        if yes:
            deleteAsync(self)
            self.isDeleted = True
            self.close()
    
    def rerecord(self):
        yes = True
        if self.settings.isConfirmOnDelete():
            yes = xbmcgui.Dialog().yesno(self.t(m.CONFIRMATION), self.t(m.ASK_RERECORD_RECORDING))

        @run_async
        @catchall
        @inject_conn
        def rerecordAsync(self):
            self.conn().rerecordRecording(self.program)
            
        if yes:
            rerecordAsync(self)
            self.isDeleted = True
            self.close()

    @inject_db
    def moveToFrontOfJobQueue(self):
        jobs = self.db().getJobs(program=self.program, jobStatus=JobStatus.QUEUED, jobType=JobType.COMMFLAG)
        if len(jobs) == 1:
            job = jobs[0]
            job.moveToFrontOfQueue()
            self.refresh()
        else:
            xbmcgui.Dialog().ok(self.t(m.ERROR), self.t(m.JOB_NOT_FOUND)) 

    @inject_conn
    def canStream(self):
        # TODO: Merge with duplicate method in RecordingDetailsWindow
        if not self.conn().protocol.supportsStreaming(self.platform):
            xbmcgui.Dialog().ok(self.t(m.ERROR), 
                'Streaming from a MythTV %s backend to XBMC' % self.conn().protocol.mythVersion(), 
                '%s is broken. Try playing again after deselecting' % self.platform.xbmcVersion(),
                'MythBox > Settings > MythTV > Enable Streaming')
            return False
        return True
        
    @catchall_ui
    def play(self):
        log.debug("Playing %s .." % safe_str(self.program.title()))
        deps = to_kwargs(self, ['program', 'mythThumbnailCache', 'translator', 'settings', 'platform'])
        
        if self.streaming:
            if not self.canStream():
                return
            # Play via myth://
            p = StreamingPlayer(**deps)
            p.playRecording(NoOpCommercialSkipper(p, self.program, self.translator))
        else:
            # Play via local fs
            p = MountedPlayer(**deps)
            p.playRecording(NoOpCommercialSkipper(p, self.program, self.translator))
            del p 
    
    def playWithCommSkip(self):
        log.debug("Playing with skip %s .." % safe_str(self.program.title()))
        deps = to_kwargs(self, ['program', 'mythThumbnailCache', 'translator', 'settings', 'platform'])
        
        if self.streaming:
            if not self.canStream():  
                return
            # Play via myth://
            p = StreamingPlayer(**deps)
            p.playRecording(NoOpCommercialSkipper(p, self.program, self.translator))
        else:
            # Play via local fs
            p = MountedPlayer(**deps)
            p.playRecording(TrackingCommercialSkipper(p, self.program, self.translator))
            del p
        
    @inject_db
    def editSchedule(self):
        if self.program.getScheduleId() is None:
            xbmcgui.Dialog().ok(self.t(m.INFO), self.t(m.ERR_NO_RECORDING_SCHEDULE))
            return
    
        schedules = self.db().getRecordingSchedules(scheduleId=self.program.getScheduleId())
        if len(schedules) == 0:
            xbmcgui.Dialog().ok(self.t(m.INFO), self.t(m.ERR_SCHEDULE_NOT_FOUND) % self.program.getScheduleId())
            return 

        editScheduleDialog = ScheduleDialog(
            'mythbox_schedule_dialog.xml', 
            self.platform.getScriptDir(), 
            forceFallback=True,
            schedule=schedules[0],
            **to_kwargs(self, ['translator', 'platform', 'settings', 'mythChannelIconCache'])) 
        editScheduleDialog.doModal()
        if editScheduleDialog.shouldRefresh:
            self.render()
    
    def nextRecording(self):
        self.program = self.programIterator.next()
        self.render()
        
    def previousRecording(self):
        self.program = self.programIterator.previous()
        self.render()
                
    @catchall_ui 
    def onAction(self, action):
        id = action.getId()
        if id in (Action.PREVIOUS_MENU, Action.PARENT_DIR):
            self.close()
        elif id == Action.PAGE_UP:
            self.previousRecording()
        elif id == Action.PAGE_DOWN:
            self.nextRecording()
        else: 
            log.debug('unhandled action = %s  id = %s' % (action, action.getId()))

    def onFocus(self, controlId):
        pass
            
    @catchall_ui 
    @window_busy
    def onClick(self, controlId):
        #log.debug('onClick %s ' % controlId)
        source = self.getControl(controlId)
        try:
            self.dispatcher[source.getId()]()
            return True
        except KeyError:
            return False

    @inject_conn
    def refresh(self):
        refreshedProgram = self.conn().getRecording(self.program.getChannelId(), self.program.recstarttime())
        if refreshedProgram:
            self.program = refreshedProgram
            self.render()
        else:
            raise Exception, self.t(m.RECORDING_NOT_FOUND) % self.program.title() 

    @window_busy
    def render(self):
        self.renderDetail()
        self.renderThumbnail()
        self.renderChannel()          # async
        self.renderCommBreaks()       # async
        self.renderSeasonAndEpisode(self.program) # async
    
    def renderDetail(self):
        s = self.program
        self.setWindowProperty('title', s.fullTitle())
        self.setWindowProperty('airDate', s.formattedAirDateTime())
        self.setWindowProperty('originalAirDate', s.formattedOriginalAirDate())
        self.setWindowProperty('channel', s.formattedChannel())
        self.setWindowProperty('description', s.formattedDescription())
        self.setWindowProperty('category', s.category())
        self.setWindowProperty('episode', '...')
        self.setWindowProperty('fileSize', s.formattedFileSize())
        self.setWindowProperty('autoExpire', (('No', 'Yes')[s.isAutoExpire()]))
        self.setWindowProperty('commBreaks', '...')     
        self.setWindowProperty('recordingNofM', self.t(m.RECORDING_N_OF_M) % (str(self.programIterator.index() + 1), str(self.programIterator.size())))  

    @run_async
    @catchall        
    @inject_db
    @coalesce
    def renderChannel(self):
        channels = filter(lambda c: c.getChannelId() == self.program.getChannelId(), self.db().getChannels())
        if channels:
            icon = self.mythChannelIconCache.get(channels.pop())
            if icon:
                self.setWindowProperty('channelIcon', icon)

    def renderThumbnail(self):
        thumbFile = self.mythThumbnailCache.get(self.program)
        self.setWindowProperty('thumbnailShadow', 'mb-DialogBack.png')
        if thumbFile:
            self.setWindowProperty('thumbnail', thumbFile)
        else:
            self.setWindowProperty('thumbnail', 'mythbox-logo.png')
            log.error('Recording thumbnail preview image not found: %s' % safe_str(self.program.title()))
                    
    @run_async
    @catchall
    @inject_db
    @coalesce
    def renderCommBreaks(self):
        self.playSkipButton.setEnabled(self.program.hasCommercials())
        self.firstInQueueButton.setEnabled(False)
        commBreaks = '-'
        if self.program.isCommFlagged():
            if self.program.hasCommercials():
                # Only move focus to Skip button if user hasn't changed the initial focus
                if self.getFocusId() == self.playButton.getId():
                    self.setFocus(self.playSkipButton)
                commBreaks = "%d" % len(self.program.getCommercials())
            else:
                commBreaks = self.t(m.NONE)
        else:
            jobs = self.db().getJobs(program=self.program, jobType=JobType.COMMFLAG)
            if len(jobs) == 1:
                job = jobs[0]
                if job.jobStatus == JobStatus.QUEUED:
                    position, numJobs = job.getPositionInQueue() 
                    commBreaks = self.t(m.QUEUED_N_OF_M) % (position, numJobs)
                    if position != 1:
                        self.firstInQueueButton.setEnabled(True)
                elif job.jobStatus == JobStatus.RUNNING:
                    try:
                        commBreaks = self.t(m.N_AT_M_FPS) % ('%d%%' % job.getPercentComplete(), '%2.0f' % job.getCommFlagRate())
                    except StatusException:
                        commBreaks = job.comment
                else:                                    
                    commBreaks = job.formattedJobStatus()
                    
        if log.isEnabledFor(logging.DEBUG):
            commBreaks += ' (%s)' % self.program.getFPS()
        
        self.setWindowProperty('commBreaks', commBreaks)

    @run_async
    @catchall
    @coalesce
    def renderSeasonAndEpisode(self, boundProgram):
        season, episode = None, None
        try:
            season, episode = self.fanArt.getSeasonAndEpisode(boundProgram)
        finally:
            if boundProgram == self.program:
                self.setWindowProperty('episode', ['-', '%sx%s' % (season, episode)][bool(season) and bool(episode)])
            else:
                log.debug('Program changed since spawning...recursing...')
                self.renderSeasonAndEpisode(self.program)