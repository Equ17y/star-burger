import logging
from geopy.distance import geodesic
from geopy.geocoders import Yandex
from django.conf import settings

logger = logging.getLogger(__name__)

def fetch_coordinates(address):
    if not address:
        return None
    
    try:
        geolocator = Yandex(api_key=settings.YANDEX_GEOCODER_API_KEY)
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        logger.exception(f"Geocoder error for address: {address}")
    return None

def calculate_distance(coord1, coord2):
    if coord1 and coord2:
        return geodesic(coord1, coord2).km
    return None