## [MythBox](MythBox.md) is a [MythTV](http://www.mythtv.org) frontend for [XBMC](http://www.xbmc.org). ##

### Features ###
  * Watch recordings with commercial skipping
  * Watch Live TV
  * Create and update recording schedules
  * Fanart from [tvdb.com](http://www.thetvdb.com), [themoviedb.org](http://www.themoviedb.org), [imdb.com](http://www.imdb.com) and [Google image search](http://www.google.com/images?hl=en&safe=off&gbv=2&tbs=isch:1&sa=1&q=seinfeld&aq=f&aqi=g10&aql=&oq=&gs_rfai=&start=0).
  * Season and episode info from [tvrage.com](http://www.tvrage.com) and [tvdb.com](http://www.thetvdb.com)
  * View upcoming recordings
  * Enhanced program guide
  * View tuner and job queue info
  * Compatible with MythTV 0.24
  * Add your own public Twitter feeds
  * Move comm flagging jobs to the front of the queue
  * Trigger user jobs, comm flagging, or transcoding for a recording
### Install ###
  * Launch XBMC (Eden 11.0 BETA1 required)
  * Navigate to System > Add-ons > Get Add-Ons > XBMC.org Add-ons > Video Add-ons > MythBox > Install
### Platforms ###
[![](http://wiki.mythbox.googlecode.com/hg/images/linux.png)](http://en.wikipedia.org/wiki/Linux)[![](http://wiki.mythbox.googlecode.com/hg/images/mac.png)](http://en.wikipedia.org/wiki/Mac_OS_X)[![](http://wiki.mythbox.googlecode.com/hg/images/windows.png)](http://en.wikipedia.org/wiki/Microsoft_Windows)
[![](http://xbmc.org/files/files/appletv_128.png)](http://wiki.xbmc.org/?title=XBMC_for_Mac_on_Apple_TV)

---

## MythBox 1.1.0  1/8/2012 ##

**New**
  * Support for XBMC 11.0 BETA (Eden)
  * A thumbnail for which there is no associated recording is automatically deleted
  * Added 'Refresh Fan Art' button to the Recording Details > Advanced menu
  * IMDbPY 4.7
  * TVRage 0.3.2
  * MythTV protocols 66 - 70 (based on patch from mitch capper)
  * iOS device support (verified on IPad 1)

**Fixed**
  * EPG was broken for Python 2.7
  * Re-record button on coverflow popup fixed
  * Loading of persistent TVRage metadata failed on file corruption
  * [EDEN](EDEN.md) Fixed crash on startup
  * [EDEN](EDEN.md) Support for Apple Remote menu button
  * Bunch of other minor bug fixes


---

## MythBox 1.0.3  5/9/2011 ##

**New**
  * Recordings Window
    * [Issue 128](https://code.google.com/p/mythbox/issues/detail?id=128) - Recordings grouped by title
    * Wallpapers from TVDB/TMDB added as backdrop

  * Recording Schedules Window
    * Added # Recorded column
    * Sortable by Title, # Recorded, or Priority

  * Recording Schedule Dialog
    * [Issue 155](https://code.google.com/p/mythbox/issues/detail?id=155) - Added User Jobs
    * Added Recording Profile

  * TV Guide Window
    * Selecting a program that is currently playing starts Live TV
    * Selecting a program with a schedule edits the schedule
    * Selecting a program with no schedule creates a schedule
    * Added banners from TVDB to the program details (bottom)

  * Watch TV Window
    * Added banners from TVDB to each channel

  * Upcoming Recordings Window
    * Launches faster (smart caching)

  * Settings Window
    * [Issue 111](https://code.google.com/p/mythbox/issues/detail?id=111) - Stream recordings directly from the backend by selecting MythTV > Enable Streaming
    * Advanced tab - Log location add as help text
    * Playback tab - Editable values for seeking during playback
      * Small Skip Forward
      * Small Skip Backward
      * Big Skip Forward
      * Big Skip Backward

  * Removed dependency on ffmpeg for determining recording framerate
  * Google Image Search updated with API key and size restrictions
  * Slovak translations - tnx Juraj Belobrad

**Fixed**
  * [Issue 161](https://code.google.com/p/mythbox/issues/detail?id=161) - schedule from TV Guide impossible if show category contains (french) accented characters
  * Some 1080i ATSC recordings from a HD Homerun were incorrectly getting commskipped due to incorrect fps detection
  * Twitter newsfeed no longer renders linebreaks which were causing multiline output


---

## MythBox 1.0.2  1/25/2011 ##

New
  * [Issue 148](https://code.google.com/p/mythbox/issues/detail?id=148) - Dutch translations (tnx Fred van Zwieten)

Fixed
  * [Issue 145](https://code.google.com/p/mythbox/issues/detail?id=145) - Fixed unicode error in Live TV window
  * [Issue 147](https://code.google.com/p/mythbox/issues/detail?id=147) - Changes to the recording schedule do not take effect immediately
  * [Issue 149](https://code.google.com/p/mythbox/issues/detail?id=149) - Help text on Settings screen gets truncated based on the translation
  * Added support for ScheduleType.NOT\_RECORDING
  * TVRage grabber more resilient to incomplete season and episode information
  * Google image search now works for programs with unicode chars in the title


---

## MythBox 1.0.1  1/13/2011 ##

New
  * [Issue 132](https://code.google.com/p/mythbox/issues/detail?id=132) - Support for MythTV 0.24 except for LiveTV (thx mitch capper)
  * TVRage season and episode matching now uses the program's subtitle when the original air date search fails
  * Added Episode column to the recordings screen
  * TV Guide shows upcoming recordings in a different color
  * Readme and FAQ viewable from MythBox > Settings > Readme and FAQ
  * Czech translations (tnx Pavel Mlčoch)
  * Swedish translations (tnx Magnus Gustafsson)
  * Polish translations (tnx Michał Sawicz)

Fixed
  * [Issue 136](https://code.google.com/p/mythbox/issues/detail?id=136) - mythbox.log moved to standard log dir on Mac OSX
  * [Issue 141](https://code.google.com/p/mythbox/issues/detail?id=141) - settings.xml parsing failed when removing mythboxfeed
  * [Issue 142](https://code.google.com/p/mythbox/issues/detail?id=142) - could not save new recording schedules that contained unicode chars
  * TVRage metadata with missing seasons caused lookup failures
  * Resuming from last position now works for ad-hoc recordings
  * Thumbnail generation for 0.24 backends fixed
  * Changing sort order or hitting refresh on some windows didn't re-invoke inflight rendering threads


---

## MythBox 1.0.0  11/25/2010 (Requires XBMC 10.0) ##

New
  * [Issue 125](https://code.google.com/p/mythbox/issues/detail?id=125) - Added Frech translations (thanks ddekani)
  * TVRage metadata caching for Season & Episode
  * FFMpeg binary for Mac and Windows unbundled from installation zip and also removed from Settings screen. Now downloads on demand.
  * New icon (tnx freezy)
  * Installs directly from the XBMC Addons repo:
> > XBMC > System > Addons > Get Addons > XBMC.org Addons > Video Addons > MythBox

Fixed
  * [Issue 124](https://code.google.com/p/mythbox/issues/detail?id=124) - Fixed parsing another variation of ffmpeg output
  * [Issue 130](https://code.google.com/p/mythbox/issues/detail?id=130) - Unable to play a recording when the cache lookup for a thumbnail fails
  * [Issue 131](https://code.google.com/p/mythbox/issues/detail?id=131) - Hours in timestamps are not displayed correctly on Macs
  * Comm skips on HDPVR 1080i recordings incorrect because ffmpeg reports incorrect framerate


---

## RC 2 ([MythBox-RC2](http://mythbox.googlecode.com/files/mythbox-RC2.tar.gz)) Released on 10/11/2010 ##

New
  * Added Sort feature to the Upcoming Recordings screen
  * [Issue 93](https://code.google.com/p/mythbox/issues/detail?id=93) - Added splash screen
  * FFmpeg output is cached for framerate extraction used by comm flagging
  * Added 'Enable Aggressive Caching' to Settings->MythTV to pre-cache framerate and commercial break info
  * Added Season and Episode to the Recording Details screen when available
  * Added TVRage as a provider of TV show metadata (used for season & episode)
  * Commercial breaks are only skipped once during playback (restarting playback in 'Play' only mode is no longer necessary if the comm break info is incorrect)
  * [Issue 97](https://code.google.com/p/mythbox/issues/detail?id=97) - Myth TV hostname and port are now queried directly from the database. Changed to read-only on the Settings->MythTV screen
  * [Issue 106](https://code.google.com/p/mythbox/issues/detail?id=106) - More responsive fanart lookup based on the current list selection in the Watch TV screen
  * [Issue 109](https://code.google.com/p/mythbox/issues/detail?id=109) - Enabled navigation from the MythBox Settings screen to the XBMC Settings screen
  * [Issue 114](https://code.google.com/p/mythbox/issues/detail?id=114) - Added slave backend hostname to the comm flag status on the Home screen
  * [Issue 118](https://code.google.com/p/mythbox/issues/detail?id=118) - MythTV 0.23-1 compatibility (Protocol 57)
  * [Issue 121](https://code.google.com/p/mythbox/issues/detail?id=121) - German translation updates (thanks to linuxluemmel)

Fixed
  * [Issue 96](https://code.google.com/p/mythbox/issues/detail?id=96) - Translations updated (ready for non-English contributions)
  * [Issue 98](https://code.google.com/p/mythbox/issues/detail?id=98) - IP addresses are used throughout the codebase. No more host not found errors.
  * [Issue 107](https://code.google.com/p/mythbox/issues/detail?id=107) - Database connections are now closed when idle and reconnect on demand.
  * [Issue 108](https://code.google.com/p/mythbox/issues/detail?id=108) - Focus changes to Play+Skip button in Recording Details screen after user has already switched focus to another button
  * [Issue 117](https://code.google.com/p/mythbox/issues/detail?id=117) - Selecting the currently playing program in the TV Guide launched the Create Schedule window instead of starting Live TV
  * Last focused recording was not restored correctly after a Refresh in the Recordings screen


---

## RC 1 ([MythBox-RC1](http://mythbox.googlecode.com/files/mythbox-RC1.tar.gz)) Released on 06/12/2010 ##

  * new     : MythTV 0.23 support added - Protocol version 56
  * new     : PageUp/PageDn (Channel Up/Channel Down on the remote) in the Recording Details screen now navigates to the next or previous recording
  * new     : Automatic forwarding through a commercial break when you land in the middle of the commercial break
  * new     : Added selected position and total number of items to the Recordings, Schedules, and Upcoming Recordings screens
  * new     : Selecting a recording in the Upcoming Recordings screen launches the Recording Schedule editor
  * new     : UI responsiveness tweaked to run well on an Acer Aspire Revo (1.6Ghz Atom + NVidia ION GPU)
  * new     : TV Guide screen is back
    * PgUp/PgDown keys now scroll up/down an entire page
    * Clicking on a currently playing program starts Live TV

> ![http://wiki.mythbox.googlecode.com/hg/screenshots/tvguide.png](http://wiki.mythbox.googlecode.com/hg/screenshots/tvguide.png)
  * new     : Program cells in the TV guide have an HD overlay indicator when appropriate
  * new     : Added keybindings and remote control buttons section to the README
  * new     : Non-idle tuners bubble to the top of the tuners list when there are more than two tuners
  * updated : Higher resolution thumbnails in Recording Details screen
  * updated : Replaced autoexpire flag with original air date on the Recording Details screen
  * updated : Faster fanart lookup on all screens + wait indicators
  * updated : Library updates: tvdb\_api 1.5, IMDbPy 4.5.1
  * updated : After deleting a recording from the Recording Details window the Recordings window would take quite a while to update for a large number of recordings
  * fixed   : Requesting a recording's thumbnail from a slave backend didn't work
  * fixed   : UI tweaks when the active skin is confluence (radio button color, active selection in coverflow, etc)
  * fixed   : Unnecessary refresh of the program listings on the Watch TV screen after stopping live tv.
  * fixed   : XBMC crashes occasionally when exiting from MythBox
  * fixed   : Clicking on Edit Schedule in the Recording Details screen when the schedule no longer exists how shows an error message
  * fixed   : Attempting to watch live tv on tuner which is already recording on a slave backend no longer fails silently


---

## Beta 7 ([SVN 1798](http://mythbox.googlecode.com/files/mythbox-svn-1798.tar.gz)) Released on 01/17/2010 ##

  * new     : Watch Recordings screen rewritten in WindowXML
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/recordings.png](http://wiki.mythbox.googlecode.com/hg/screenshots/recordings.png)
  * wip     : TV Guide screen temporarily disabled -- work in progress
  * new     : Home screen coverflow now supports a context menu from which you can delete or re-rerecord the recording
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/home-recent-context.png](http://wiki.mythbox.googlecode.com/hg/screenshots/home-recent-context.png)
  * new     : Twitter feed of mythbox news events added to the bottom of the home screen
  * new     : [Public twitter feeds](http://twitterholic.com/) can be added to the news feed from Settings -> Advanced -> Twitter
  * update  : Codebase purged of all legacy windowing/skinning code (non-WindowXML)
  * fixed   : File cache thread safety issues fixed
  * new     : All screens with listboxes now restore the last selected listitem
  * fixed   : Unnecessary induced reject on all but the first myth connection negotiation
  * updated : The 'x' in the mythbox logo fixed to match the xbmc logo (tnx Jezz\_X)
  * fixed   : Home screen coverflow images scaled instead of stretched
  * fixed   : Delete recording thumbnail from cache when recording deleted or marked for re-record
  * updated : Added Q15 to the FAQ - Connect to MySQL failed: 1156 (08S01): Got packets out of order,10000)
  * updated : IMDbPy updated to download higher resolution box covers (4.5)
  * new     : Tuners table on home screen now shows the time of the next scheduled recording if the tuner is currently idle
  * fixed   : Cover flow on Home screen would not get updated when a recording was deleted from the Recording Details screen
  * fixed   : [Issue 70](https://code.google.com/p/mythbox/issues/detail?id=70) - recordings not visible in Recording Schedules screen
  * fixed   : [Issue 79](https://code.google.com/p/mythbox/issues/detail?id=79) - extra set of quotes needed in call to os.system(...) on Windows (tschutte)
  * fixed   : [Issue 80](https://code.google.com/p/mythbox/issues/detail?id=80) - worker threads reaped before exiting script - prevents xbmc from dumping core
  * fixed   : [Issue 83](https://code.google.com/p/mythbox/issues/detail?id=83) - recordings from all recording groups are shown instead of just the ones from Default


---

## Beta 6 (SVN 1558) Released on 10/23/2009 ##

  * new    : Home screen rewrite with coverflow of recent recordings, tuners, and jobs
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/home.png](http://wiki.mythbox.googlecode.com/hg/screenshots/home.png)
  * new    : Recording schedules screen rewrite with fan art, schedule type, and priority
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/recording-schedules.png](http://wiki.mythbox.googlecode.com/hg/screenshots/recording-schedules.png)
  * new    : Upcoming recordings screen rewrite with fan art, channel logos, etc
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/upcoming-recordings.png](http://wiki.mythbox.googlecode.com/hg/screenshots/upcoming-recordings.png)


---

## Beta 5 (SVN 1260) Released on 7/26/2009 ##

  * new    : Live TV screen rewrite in WindowXML with fanart and channel logos
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/watchtv.png](http://wiki.mythbox.googlecode.com/hg/screenshots/watchtv.png)
  * new    : Fanart support added for tvdb.org, themoviedb.org, imdb, and google image search.
  * new    : Added Fan Art section to settings screen with the ability to clear the cached fan art.
  * changed: Bumped up max value for live tv buffer size to 20MB
  * new    : German translations (tnx to linuxluemmel.ch)
  * new    : Spanish translations (tnx to jkpalo@yahoo.es)
  * fixed  : Tweaks to work with mediastream skin


---

## Beta 4 (SVN 1105) Released on 6/2/2009 ##

  * fixed  : [Issue 37](https://code.google.com/p/mythbox/issues/detail?id=37) - Startup failure on windows
  * fixed  : [Issue 2](https://code.google.com/p/mythbox/issues/detail?id=2) - MySQL shared object library for amd64
  * fixed  : [Issue 31](https://code.google.com/p/mythbox/issues/detail?id=31) - Channel duplication across multipe tuners with same guide data fixed in Live TV screen
  * fixed  : [Issue 30](https://code.google.com/p/mythbox/issues/detail?id=30) - Fixed one terabyte+ diskspace reported incorrectly
  * changed: Settings windows rewritten in WindowXML, help added, and save button removed
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/settings.png](http://wiki.mythbox.googlecode.com/hg/screenshots/settings.png)
  * changed: Live TV progress bar now includes buffer size while buffering
  * updated: support for MythTV 0.22 (trunk) protocol 45


---

## Beta 3 (SVN 1062) Released on 5/6/2009 ##

  * updated: support for MythTV 0.22 (trunk) procotol 44
  * new    : recording detail screen - added date/time to header
  * new    : recording detail screen - mini-video window replaces thumbnail when video is playing
  * changed: recording detail screen - improved load time - WindowXML rewrite + async pre/post fetching + mythtv connection & db pooling
  * new    : recording detail screen - added ability to move a queued comm flag job to the beginning of the queue - MythTV doesn't even have this!
  * new    : recording detail screen - added number of commercial breaks, position in queue, or percent completed if still in progress
> ![http://wiki.mythbox.googlecode.com/hg/screenshots/recording-details.png](http://wiki.mythbox.googlecode.com/hg/screenshots/recording-details.png)
  * changed: recording detail screen - enlarged thumbnail and added drop shadow; recording details re-arranged
  * changed: recording detail screen - Play+Skip button has default focus if recording is comm flagged
  * new    : create/edit recording schedule dialog - start and end offsets can now be edited
  * updated: [Issue 24](https://code.google.com/p/mythbox/issues/detail?id=24) - Default buffer size is too low
  * fixed  : [Issue 25](https://code.google.com/p/mythbox/issues/detail?id=25) - can't change recording schedule from tv guide
  * fixed  : [Issue 22](https://code.google.com/p/mythbox/issues/detail?id=22) - support for ffmpeg 0.5 on ubuntu 9.04 jaunty

---

