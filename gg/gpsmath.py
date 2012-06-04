# Copyright (C) 2010 Robert Park <rbpark@exolucere.ca>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Trigonometry and other mathematical calculations."""

from __future__ import division

from math import acos, sin, cos, radians
from time import strftime, localtime
from math import modf as split_float
from os.path import join, basename
from gettext import gettext as _
from fractions import Fraction
from pyexiv2 import Rational
from gi.repository import GObject

from territories import get_state, get_country
from build_info import PKG_DATA_DIR

EARTH_RADIUS = 6371 #km

def dms_to_decimal(degrees, minutes, seconds, sign=' '):
    """Convert degrees, minutes, seconds into decimal degrees."""
    return (-1 if sign[0] in 'SWsw' else 1) * (
        float(degrees)        +
        float(minutes) / 60   +
        float(seconds) / 3600
    )

def decimal_to_dms(decimal):
    """Convert decimal degrees into degrees, minutes, seconds."""
    remainder, degrees = split_float(abs(decimal))
    remainder, minutes = split_float(remainder * 60)
    return [
        Rational(degrees, 1),
        Rational(minutes, 1),
        float_to_rational(remainder * 60)
    ]

def float_to_rational(value):
    """Create a pyexiv2.Rational with help from fractions.Fraction."""
    frac = Fraction(abs(value)).limit_denominator(99999)
    return Rational(frac.numerator, frac.denominator)

def valid_coords(lat, lon):
    """Determine the validity of coordinates."""
    if type(lat) not in (float, int): return False
    if type(lon) not in (float, int): return False
    return abs(lat) <= 90 and abs(lon) <= 180

def format_coords(lat, lon):
    """Add cardinal directions to decimal coordinates."""
    return '%s %.5f, %s %.5f' % (
        _('N') if lat >= 0 else _('S'), abs(lat),
        _('E') if lon >= 0 else _('W'), abs(lon)
    )

gproperty = GObject.property

class Coordinates(GObject.GObject):
    """A generic object containing latitude and longitude coordinates.
    
    This class is inherited by Photograph and TrackFile and contains methods
    required by both of those classes.
    
    The geodata attribute of this class is shared across all instances of
    all subclasses of this class. When it is modified by any instance, the
    changes are immediately available to all other instances. It serves as
    a cache for data read from cities.txt, which contains geocoding data
    provided by geonames.org. All subclasses of this class can call
    self.lookup_geoname() and receive cached data if it was already
    looked up by another instance of any subclass.
    """
    
    # Class variable, keeps the geocoding cache
    geodata   = {}
    
    # GObject properties
    filename  = gproperty(type=str, default='')
    latitude  = gproperty(type=float, default=0.0)
    longitude = gproperty(type=float, default=0.0)
    altitude  = gproperty(type=float, default=0.0)
    timestamp = gproperty(type=int, default=0)
    
    # Properties found from geocoding
    provincestate = gproperty(type=str, default='')
    countrycode   = gproperty(type=str, default='')
    countryname   = gproperty(type=str, default='')
    city          = gproperty(type=str, default='')
    # The timezone at our coordinates, in 'Zone/City' format
    geotimezone   = gproperty(type=str, default='')
    
    # Convenience properties calculated from the other ones
    plain_summary  = gproperty(type=str, default='')
    markup_summary = gproperty(type=str, default='')
    
    def __init__(self, **props):
        GObject.GObject.__init__(self, **props)
        self.connect('notify::latitude', self.update_properties, True)
        self.connect('notify::longitude', self.update_properties, True)
        self.connect('notify::altitude', self.update_properties, False)
        self.connect('notify::timestamp', self.update_properties, False)
        
    def valid_coords(self):
        """Check if this object contains valid coordinates."""
        return abs(self.latitude) <= 90 and abs(self.longitude) <= 180
    
    def maps_link(self, link=_('View in Google Maps')):
        """Return a link to Google Maps if this object has valid coordinates."""
        return '<a href="%s?q=%s,%s">%s</a>' % ('http://maps.google.com/maps',
            self.latitude, self.longitude, link) if self.valid_coords() else ''
    
    def lookup_geodata(self):
        """Search cities.txt for nearest city."""
        if not self.valid_coords():
            return
        key = '%.2f,%.2f' % (self.latitude, self.longitude)
        if key in Coordinates.geodata:
            return self.set_geodata(self.geodata[key])
        near, dist = None, float('inf')
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        with open(join(PKG_DATA_DIR, 'cities.txt')) as cities:
            for city in cities:
                name, lat, lon, country, state, tz = city.split('\t')
                lat2, lon2 = radians(float(lat)), radians(float(lon))
                try:
                    delta = acos(sin(lat1) * sin(lat2) +
                                 cos(lat1) * cos(lat2) *
                                 cos(lon2  - lon1))    * EARTH_RADIUS
                except ValueError:
                    delta = 0
                if delta < dist:
                    dist = delta
                    near = [name, state, country, tz]
        Coordinates.geodata[key] = near
        return self.set_geodata(near)
    
    def set_geodata(self, data):
        """Apply geodata to internal attributes."""
        self.city, state, self.countrycode, tz = data
        self.provincestate = get_state(self.countrycode, state)
        self.countryname   = get_country(self.countrycode)
        self.geotimezone      = tz.strip()
        return self.geotimezone
    
    def pretty_time(self):
        """Convert epoch seconds to a human-readable date."""
        if type(self.timestamp) is int:
            return strftime('%Y-%m-%d %X', localtime(self.timestamp))
    
    def pretty_coords(self):
        """Add cardinal directions to decimal coordinates."""
        return format_coords(self.latitude, self.longitude) \
            if self.valid_coords() else _('Not geotagged')
    
    def pretty_geoname(self):
        """Display city, state, and country, if present."""
        return ', '.join(
            [s for s in (self.city, self.provincestate, self.countryname) if s])
    
    def pretty_altitude(self):
        """Convert elevation into a human readable format."""
        if self.altitude <> 0.0:
            return '%.1f%s' % (abs(self.altitude), _('m above sea level')
                        if self.altitude >= 0 else _('m below sea level'))
        return ''
    
    def build_plain_summary(self):
        """Plaintext summary of photo metadata."""
        self.plain_summary =  '\n'.join([s for s in [self.pretty_geoname(),
                                      self.pretty_time(),
                                      self.pretty_coords(),
                                      self.pretty_altitude()] if s])
    
    def build_markup_summary(self):
        """Longer summary with Pango markup."""
        self.markup_summary = '<span %s>%s</span>\n<span %s>%s</span>' % (
            'size="larger"', basename(self.filename),
            'style="italic" size="smaller"', self.plain_summary
        )
    
    def update_properties(self, object, property, lookup = False):
        if lookup:
            self.lookup_geodata()
        self.build_plain_summary()
        self.build_markup_summary()

