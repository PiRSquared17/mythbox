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
import time

class LogScraper(object):

    def __init__(self, fname):
        self.fname = fname
        
    def matchLine(self, s, timeout=10):  
        '''Waits for a line of text containing s to be written to the file. 
        Returns the line if found, or None in the case of a timeout (seconds)'''
        elapsed = 0
        before = time.clock()
        try:
            f = open(self.fname, 'rb+')

            # os.SEEK_END was introduced in python 2.5 so have no choice but to use f.read()
            # TODO: Update to use f.seek(0, os.SEEK_END) after we've ditched python 2.4
            f.read()
            
            while elapsed < timeout:
                line = f.readline()
                if s in line:
                    return s
                now = time.clock()
                elapsed += now - before
                before = now
        finally:
            try: 
                f.close() 
            except: 
                pass

        return None
