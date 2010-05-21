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

log = logging.getLogger('mythbox.event')

# =============================================================================
class Event(object):
    RECORDING_DELETED    = 'RECORDING_DELETED'  # key: id, program
    SETTING_CHANGED      = 'SETTING_CHANGED'    # keys: id, tag, old, new

# =============================================================================
class EventBus(object):
    
    def __init__(self):
        self.listeners = []
        
    def register(self, listener):
        self.listeners.append(listener)

    def deregister(self, listener):
        try:
            self.listeners.remove(listener)
        except ValueError, ve:
            log.error(ve)

    def publish(self, event):
        """
        @type event: dict
        @param event: Put in whatever you like. The only mandatory key is 'id'
        """
        for listener in self.listeners:
            try:
                listener.onEvent(event)
            except:
                log.exception('Error publishing event %s to %s' % (event, listener))
