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
import sys

import xbmc
import xbmcgui

from mythbox import pool
from mythbox.bus import Event
from mythbox.mythtv.db import MythDatabaseFactory
from mythbox.mythtv.domain import StatusException
from mythbox.mythtv.enums import JobStatus, JobType
from mythbox.mythtv.conn import inject_conn, inject_db, ConnectionFactory
from mythbox.settings import SettingsException
from mythbox.ui.player import MythPlayer, TrackingCommercialSkipper
from mythbox.ui.toolkit import *
from mythbox.util import catchall_ui, catchall, lirc_hack, run_async, coalesce 
from mythbox.util import hasPendingWorkers, waitForWorkersToDie, formatSize

log = logging.getLogger('mythbox.ui')

ID_COVERFLOW_GROUP    = 499
ID_COVERFLOW_WRAPLIST = 500
MAX_COVERFLOW         = 6


class HomeWindow(BaseWindow):
    
    def __init__(self, *args, **kwargs):
        BaseWindow.__init__(self, *args, **kwargs)
        self.settings     = kwargs['settings']
        self.translator   = kwargs['translator']
        self.platform     = kwargs['platform']
        self.fanArt       = kwargs['fanArt']
        self.cachesByName = kwargs['cachesByName']
        self.bus          = kwargs['bus']
        self.feedHose     = kwargs['feedHose']
        self.win = None
        self.lastFocusId = None
        
        self.mythThumbnailCache = self.cachesByName['mythThumbnailCache']
        self.mythChannelIconCache = self.cachesByName['mythChannelIconCache']
        self.httpCache = self.cachesByName['httpCache']

        self.bus.register(self)
        
    def onFocus(self, controlId):
        log.debug('lastfocusid = %s' % controlId)
        self.lastFocusId = controlId
    
    @catchall_ui
    def onInit(self):
        if not self.win:
            self.win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
            self.tunersListBox = self.getControl(249)
            self.jobsListBox = self.getControl(248)
            self.coverFlow = self.getControl(ID_COVERFLOW_WRAPLIST)
            
            # button ids -> funtion ptr
            self.dispatcher = {
                250 : self.goWatchRecordings,
                251 : self.goWatchTv,
                252 : self.goTvGuide,
                253 : self.goRecordingSchedules,
                254 : self.goUpcomingRecordings,
                256 : self.goSettings,
                255 : self.refreshOnInit,
                ID_COVERFLOW_WRAPLIST : self.goPlayRecording
            }
            
            self.initCoverFlow()
            self.startup()
            self.refreshOnInit()
        else:
            self.refresh()
   
    def initCoverFlow(self):
        self.coverItems = []
        for i in range(MAX_COVERFLOW):
            coverItem = xbmcgui.ListItem()
            self.setListItemProperty(coverItem, 'thumb', 'loading.gif')
            self.coverItems.append(coverItem)
        self.coverFlow.addItems(self.coverItems)
   
    @catchall_ui
    @lirc_hack            
    def onAction(self, action):
        if action.getId() in (Action.PREVIOUS_MENU, Action.PARENT_DIR):
            self.closed = True
            self.shutdown()
            self.close()
        elif action.getId() in (Action.CONTEXT_MENU,) and self.lastFocusId in (ID_COVERFLOW_GROUP, ID_COVERFLOW_WRAPLIST):
            selection = xbmcgui.Dialog().select('context menu', ['Delete', 'Re-record'])
            if selection == 0:
                self.deleteRecording()
            elif selection == 1:
                self.rerecordRecording()
            else:
                log.debug('dialog cancelled')
        else:
            pass #log.debug('Unhandled action: %s  lastFocusId = %s' % (action, self.lastFocusId))

    @window_busy
    @inject_conn
    def deleteRecording(self):
        yes = True
        if self.settings.isConfirmOnDelete():
            yes = xbmcgui.Dialog().yesno(self.translator.get(28), self.translator.get(65))
            
        if yes:
            program = self.recordings[self.coverFlow.getSelectedPosition()]
            self.conn().deleteRecording(program)

    @window_busy
    @inject_conn
    def rerecordRecording(self):
        yes = True
        if self.settings.isConfirmOnDelete():
            yes = xbmcgui.Dialog().yesno(self.translator.get(28), self.translator.get(65))
            
        if yes:
            program = self.recordings[self.coverFlow.getSelectedPosition()]
            self.conn().rerecordRecording(program)

    @catchall_ui
    @lirc_hack    
    def onClick(self, controlId):
        try:
            self.dispatcher[controlId]()
        except KeyError:
            log.exception('onClick')
   
    @window_busy
    def startup(self):
        """
        @return: True if startup successful, False otherwise
        """
        self.settingsOK = False
        try:
            self.settings.verify()
            self.settingsOK = True
        except SettingsException, se:
            showPopup('Settings Error', str(se), 7000)
            self.goSettings()
            try:
                self.settings.verify() # TODO: optimize unnecessary re-verify
                self.settingsOK = True
            except SettingsException:
                self.shutdown()
                self.close()
                return False
            
        if self.settingsOK:      
            pool.pools['dbPool'] = pool.EvictingPool(MythDatabaseFactory(settings=self.settings, translator=self.translator), maxAgeSecs=10*60, reapEverySecs=10)
            
            # TODO: Conn pool is non-evicting (I think we have to maintain connections to backends don't go to sleep/suspend)
            pool.pools['connPool'] = pool.Pool(ConnectionFactory(settings=self.settings, translator=self.translator, platform=self.platform, bus=self.bus))
        
        if self.settingsOK:
            self.dumpBackendInfo()
             
        return self.settingsOK
    
    @inject_db
    def dumpBackendInfo(self):
        backends = [self.db().getMasterBackend()]
        backends.extend(self.db().getSlaveBackends())
        log.warn('Backend info')
        for b in backends:
            log.warn('\t' + str(b))
            
    def shutdown(self):
        self.setBusy(True)
        self.bus.deregister(self)
        try:
            self.settings.save()
        except:
            log.exception('Saving settings on exit')

        self.fanArt.shutdown()

        self.bus.publish({'id':Event.SHUTDOWN})
        
        try:
            # HACK ALERT:
            #   Pool reaper thread is @run_async so we need to 
            #   allow it to die before we start waiting for the 
            #   worker threads to exit in waitForWorkersToDie(). 
            #   pool.shutdown() is the normal way to do it but we can't shut
            #   down the pools until theads (which may have 
            #   refs to pooled resources) have all exited.
            #   
            # TODO: 
            #   Fix is to refactor EvictingPool to not use
            #   the @run_async decorator
            
            #for (poolName, poolInstance) in pool.pools.items():
            #    poolInstance.stopReaping = True
            pool.pools['dbPool'].stopReaping = True
            
            if hasPendingWorkers():
                showPopup('Please wait', 'Closing connections...', 3000)
                waitForWorkersToDie(30.0) # in seconds
        except:
            log.exception('Waiting for worker threads to die')
            
        try:
            # print pool stats and shutdown
            for (poolName, poolInstance) in pool.pools.items():
                log.info('Pool %s: available = %d  size = %d' % (poolName, poolInstance.available(), poolInstance.size()))
                poolInstance.shutdown()
        except:
            log.exception('Error while shutting down')

        try:
            log.info('Goodbye!')
            logging.shutdown()
            #sys.modules.clear()  -- crashes XBMC
        except Exception, e:
            xbmc.log('%s' % str(e))            
        
    def goWatchTv(self):
        from livetv import LiveTvWindow2 
        LiveTvWindow2(
            'mythbox_livetv.xml', 
            os.getcwd(), 
            settings=self.settings, 
            translator=self.translator, 
            mythChannelIconCache=self.mythChannelIconCache, 
            fanArt=self.fanArt, 
            platform=self.platform).doModal()

    @window_busy
    def goPlayRecording(self):
        p = MythPlayer(mythThumbnailCache=self.mythThumbnailCache)
        program=self.recordings[self.coverFlow.getSelectedPosition()]
        p.playRecording(program, TrackingCommercialSkipper(p, program))
        del p 
            
    def goWatchRecordings(self):
        from mythbox.ui.recordings import RecordingsWindow
        RecordingsWindow(
            'mythbox_recordings.xml', 
            os.getcwd(), 
            settings=self.settings, 
            translator=self.translator, 
            platform=self.platform, 
            fanArt=self.fanArt, 
            cachesByName=self.cachesByName).doModal()
        
    def goTvGuide(self):
        from tvguide import TvGuideWindow 
        TvGuideWindow(
            'mythbox_tvguide.xml', 
            os.getcwd(), 
            settings=self.settings, 
            translator=self.translator, 
            platform=self.platform, 
            fanArt=self.fanArt, 
            cachesByName=self.cachesByName).doModal()
    
    def goRecordingSchedules(self):
        from schedules import SchedulesWindow 
        SchedulesWindow(
            'mythbox_schedules.xml', 
            os.getcwd(), 
            settings=self.settings, 
            translator=self.translator, 
            platform=self.platform, 
            fanArt=self.fanArt, 
            cachesByName=self.cachesByName).doModal()
            
    def goUpcomingRecordings(self):
        from upcoming import UpcomingRecordingsWindow
        UpcomingRecordingsWindow(
            'mythbox_upcoming.xml', 
            os.getcwd(), 
            settings=self.settings, 
            translator=self.translator, 
            platform=self.platform, 
            fanArt=self.fanArt, 
            cachesByName=self.cachesByName).doModal()
        
    def goSettings(self):
        from uisettings import SettingsWindow
        SettingsWindow(
            'mythbox_settings.xml', 
            os.getcwd(), 
            settings=self.settings, 
            translator=self.translator, 
            platform=self.platform, 
            fanArt=self.fanArt, 
            cachesByName=self.cachesByName).doModal()

    @window_busy
    def refresh(self):
        if self.settingsOK:
            self.renderTuners()
            self.renderJobs()
            self.renderStats()

    @window_busy
    def refreshOnInit(self):
        if self.settingsOK:
            self.initCoverFlow()
            self.renderTuners()
            self.renderJobs()
            self.renderStats()
            self.renderCoverFlow()
            self.renderNewsFeed()
            
    @run_async
    @catchall
    @inject_conn
    @coalesce
    def renderCoverFlow(self, exclude=None):
        log.debug('>> renderCoverFlow begin')
        self.recordings = self.conn().getAllRecordings()
        
        if exclude:
            try:
                self.recordings.remove(exclude)
            except:
                pass
            
        for i, r in enumerate(self.recordings[:MAX_COVERFLOW]):
            log.debug('Coverflow %d/%d: %s' % (i+1, MAX_COVERFLOW, r.title()))
            listItem = self.coverItems[i] 
            self.setListItemProperty(listItem, 'title', r.title())
            self.setListItemProperty(listItem, 'description', r.description())
            
            cover = self.fanArt.getRandomPoster(r)
            if not cover:
                cover = self.mythThumbnailCache.get(r)
                if not cover:
                    cover = 'mythbox-logo.png'
            self.setListItemProperty(listItem, 'thumb', cover)
        log.debug('<<< renderCoverFlow end')
        
    @run_async
    @inject_conn
    @coalesce
    def renderTuners(self):
        tuners = self.conn().getTuners()[:]
        
        for t in tuners:
            t.listItem = xbmcgui.ListItem()
            self.setListItemProperty(t.listItem, 'tuner', '%s %s' % (t.tunerType, t.tunerId))
            self.setListItemProperty(t.listItem, 'hostname', t.hostname)
            self.setListItemProperty(t.listItem, 'status', t.formattedTunerStatus())

        if len(tuners) > 2:    
            
            def nextToRecordFirst(t1, t2):
                r1 = t1.getNextScheduledRecording()
                r2 = t2.getNextScheduledRecording()
                
                if not r1 or not r2:
                    return 0
                elif r1 and not r2:
                    return 1
                elif not r1 and r2:
                    return -1
                else:
                    return cmp(r1.starttimeAsTime(), r2.starttimeAsTime())
                
            def idleTunersLast(t1, t2):
                t1Idle = t1.listItem.getProperty('status').startswith('Idle')
                t2Idle = t2.listItem.getProperty('status').startswith('Idle')

                if t1Idle and t2Idle:
                    return nextToRecordFirst(t1,t2)
                elif t1Idle and not t2Idle:
                    return 1
                elif not t1Idle and t2Idle:
                    return -1
                else:
                    return cmp(t1.listItem.getProperty('tuner'), t2.listItem.getProperty('tuner'))            

            tuners.sort(idleTunersLast)

        self.tunersListBox.addItems(map(lambda t: t.listItem, tuners))

    @run_async
    @inject_db
    @coalesce
    def renderJobs(self):
        running = self.db().getJobs(program=None, jobType=None, jobStatus=JobStatus.RUNNING)
        queued = self.db().getJobs(program=None, jobType=None, jobStatus=JobStatus.QUEUED)
        listItems = []

        def getTitle(job):
            if j.getProgram(): 
                return j.getProgram().title()
            else:
                return 'Unknown'

        def getJobStats(job):
            if job.jobStatus == JobStatus.QUEUED:
                position, numJobs = job.getPositionInQueue() 
                return 'Queued %d of %d' % (position, numJobs)
            elif job.jobStatus == JobStatus.RUNNING:
                try:
                    return 'Completed %d%% at %2.0f fps' % (job.getPercentComplete(), job.getCommFlagRate())
                except StatusException:
                    return job.comment
            else:                                    
                return job.formattedJobStatus()
        
        def getHostInfo(job):
            commFlagBackend = self.db().toBackend(job.hostname)
            if commFlagBackend.slave:
                return ' on %s' % commFlagBackend.hostname
            else:
                return ''
            
        i = 1    
        for j in running:
            listItem = xbmcgui.ListItem()
            self.setListItemProperty(listItem, 'jobNumber', '%d'%i)
            title = getTitle(j)
            
            if j.jobType == JobType.COMMFLAG:
                status = 'Commercial flagging %s%s. %s' % (title, getHostInfo(j), getJobStats(j))
            elif j.jobType == JobType.TRANSCODE: 
                status = 'Transcoding %s' % title
            else: 
                status = '%s processing %s' % (j.formattedJobType(), title)
                
            self.setListItemProperty(listItem, 'status', status)
            listItems.append(listItem)
            i += 1

        for j in queued:
            listItem = xbmcgui.ListItem()
            self.setListItemProperty(listItem, 'jobNumber', '%d'%i)
            title = getTitle(j)

            if j.jobType == JobType.COMMFLAG: 
                status = 'Waiting to commercial flag %s' % title
            elif j.jobType == JobType.TRANSCODE: 
                status = 'Waiting to transcode %s' % title
            else: 
                status = 'Waiting to run %s on %s' % (j.formattedJobType(), title)
                
            self.setListItemProperty(listItem, 'status', status)
            listItems.append(listItem)
            i+=1
        
        self.jobsListBox.addItems(listItems)
               
    @run_async     
    @inject_conn
    @coalesce
    def renderStats(self):
        return
        log.debug('renderStats enter')
        du = self.conn().getDiskUsage()
        self.setWindowProperty('spaceFree', formatSize(du['free'], True))
        self.setWindowProperty('spaceTotal', formatSize(du['total'], True))
        self.setWindowProperty('spaceUsed', formatSize(du['used'], True))

        load = self.conn().getLoad()
        self.setWindowProperty('load1', load['1'])
        self.setWindowProperty('load5', load['5'])
        self.setWindowProperty('load15', load['15'])

        self.setWindowProperty('guideDataStatus', self.conn().getGuideDataStatus())
        self.setWindowProperty('guideData', self.conn().getGuideData())
        log.debug('renderStats exit')
        
    @run_async
    @catchall
    @coalesce
    def renderNewsFeed(self):
        log.debug('renderNewsFeed enter')
        t = u'' 
        for entry in self.feedHose.getLatestEntries():
            t += '[COLOR=ffe2ff43]%s[/COLOR] [COLOR=white]%s[/COLOR]       ' % (entry.username, entry.text)
        t = ' ' * 300 + t
        self.setWindowProperty('newsfeed', t)
        log.debug('renderNewsFeed exit')
        
    def onEvent(self, event):
        log.debug('home window received event: %s' % event)
        if event['id'] == Event.RECORDING_DELETED:
            self.renderCoverFlow(exclude=event['program'])
        elif event['id'] == Event.SETTING_CHANGED and event['tag'] == 'feeds_twitter':
            self.renderNewsFeed()
                            