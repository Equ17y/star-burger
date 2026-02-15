import logging
from geopy.distance import geodesic
from geopy.geocoders import Yandex
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable, GeocoderQueryError
from django.conf import settings
from geocoding.models import Location

logger = logging.getLogger(__name__)

def fetch_coordinates(address):
    if not address:
        return None
    
    location, created = Location.objects.get_or_create(
        address=address,
        defaults={'lat': None, 'lon': None}
    )
    
    if location.lat is not None and location.lon is not None:
        return (location.lat, location.lon)
    
    try:
        geolocator = Yandex(api_key=getattr(settings, 'YANDEX_GEOCODER_API_KEY', None))
        location_data = geolocator.geocode(address)
        if location_data:
            coordinates = (location_data.latitude, location_data.longitude)
            location.lat = coordinates[0]
            location.lon = coordinates[1]
            location.save()
            return coordinates
    except (GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable, GeocoderQueryError) as e:
        logger.exception(f"Geocoder error for address '{address}': {e}")
    return None

def calculate_distance(coord1, coord2):
    if coord1 and coord2:
        return geodesic(coord1, coord2).km
    return None