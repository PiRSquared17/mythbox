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

import os
import logging
from xml.dom.minidom import parseString

log = logging.getLogger('mythbox.settings')

class AdvancedSettings(object):
    '''
    Editor for XBMC's advancedsettings.xml
    Details @ http://wiki.xbmc.org/index.php?title=Advancedsettings.xml
    '''
    
#    <video> <!-- "VideoSettings" instead of "video" for builds prior to May 22, 2006 -->
#      <smallstepbackseconds>7</smallstepbackseconds>  <!-- Length of the small skip back (normally the BACK button) when playing a video -->
#      <smallstepbacktries>3</smallstepbacktries>
#      <smallstepbackdelay>300</smallstepbackdelay>
#      <usetimeseeking>true</usetimeseeking>  <!-- Whether to use time based or percentage based seeking. -->
#      <timeseekforward>30</timeseekforward>  <!-- Time to seek forward in seconds when doing a short seek.  Defaults to 30. -->
#      <timeseekbackward>-30</timeseekbackward>  <!-- Time to seek backward in seconds when doing a short seek.  Defaults to -30. -->
#      <timeseekforwardbig>600</timeseekforwardbig>  <!-- Time to seek forward in seconds when doing a long seek.  Defaults to 600 (10 minutes). -->
#      <timeseekbackwardbig>-600</timeseekbackwardbig>  <!-- Time to seek forward in seconds when doing a long seek.  Defaults to -600 (10 minutes). -->
#    </video>
    
          
    def __init__(self, *args, **kwargs):
        self.init_with = None
        [setattr(self, name, value) for name,value in kwargs.items() if name in ('platform', 'init_with') ]
        self.filename = os.path.join(self.platform.getUserDataDir(), 'advancedsettings.xml')
        if self.init_with:
            self.dom = parseString(self.init_with)
        else:
            self.dom = parseString(self._read())        
        
    def _read(self):
        if os.path.exists(self.filename) and os.path.isfile(self.filename):
            log.debug('advancedsettings.xml exists')
            f = open (self.filename, 'r')
            contents = f.read()
            f.close()
            return contents
        else:
            log.debug('%s does not exist. Starting fresh')
            return u'<advancedsettings/>'
                
    def _write(self):
        f = open(self.filename, 'w')
        f.write(self.contents)
        f.close()
        
    def __str__(self):
        return self.dom.toprettyxml(indent='  ', encoding='utf8')
    
    def hasSetting(self, name):
        segments = name.split('/')
        current = self.dom.getElementsByTagName('advancedsettings')[0]
        for i,segment in enumerate(segments):
            nodes = current.getElementsByTagName(segment)
            if i == (len(segments) - 1) and len(nodes) > 0:
                return True
            elif len(nodes) > 0:
                current = nodes[0]
            else:
                return False
        return False

    def getSetting(self, name):
        if not self.hasSetting(name):
            return None
        
        segments = name.split('/')
        current = self.dom.getElementsByTagName('advancedsettings')[0]
        for i,segment in enumerate(segments):
            nodes = current.getElementsByTagName(segment)
            if i == (len(segments) - 1) and len(nodes) > 0:
                assert len(nodes) == 1
                textNodes = nodes[0].childNodes
                if len(textNodes) == 1:
                    return textNodes[0].data
                elif len(textNodes) == 0:
                    return u''
            elif len(nodes) > 0:
                current = nodes[0]
        return None
    
    def setSetting(self, name, value):
        segments = name.split('/')
        current = self.dom.getElementsByTagName('advancedsettings')[0]
        for i,segment in enumerate(segments):
            nodes = current.getElementsByTagName(segment)
            if i == (len(segments) - 1):
                # last node in path
                if len(nodes) > 0:
                    # last node exists
                    assert len(nodes) == 1
                    textNodes = nodes[0].childNodes
                    if len(textNodes) == 1:
                        # last node has text
                        textNodes[0].data = value
                    elif len(textNodes) == 0:
                        # last node has no text
                        textNode = self.dom.createTextNode(value)
                        nodes[0].appendChild(textNode)
                else:
                    # last node does not exist
                    node = self.dom.createElement(segment)
                    node.appendChild(self.dom.createTextNode(value))
                    current.appendChild(node)
            else:
                # intermediate node
                if len(nodes) == 0:  
                    # intermediate node doesnt exist
                    newNode = self.dom.createElement(segment)
                    current.appendChild(newNode)
                    current = newNode
                else:
                    # intermediate node does exist
                    current = nodes[0]
                