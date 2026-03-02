from geocoding.utils import fetch_coordinates, calculate_distance
from geocoding.models import Location
from foodcartapp.models import Restaurant, Order


def get_restaurants_by_ids(restaurant_ids):
    """Получает рестораны по списку ID. Атомарная функция."""
    if not restaurant_ids:
        return []
    return list(Restaurant.objects.filter(id__in=restaurant_ids))


def fetch_coordinates_for_addresses(addresses):
    """
    Получает координаты для адресов.
    Возвращает словарь: адрес → (lat, lon).
    """
    if not addresses:
        return {}
    
    coords_cache = {}
    
    # Берем из кэша БД
    locations = Location.objects.filter(address__in=addresses)
    for loc in locations:
        if loc.lat is not None and loc.lon is not None:
            coords_cache[loc.address] = (loc.lat, loc.lon)
    
    # Запрашиваем недостающие у геокодера
    missing = addresses - set(coords_cache.keys())
    for address in missing:
        coords = fetch_coordinates(address)
        if coords:
            coords_cache[address] = coords
            Location.objects.get_or_create(
                address=address,
                defaults={'lat': coords[0], 'lon': coords[1]}
            )
    
    return coords_cache


def calculate_distance_for_order(order, restaurants, coords_cache):
    """
    Считает расстояния для ОДНОГО заказа до списка ресторанов.
    Возвращает (список_с_расстояниями, есть_ли_ошибка_координат).
    """
    order_coords = coords_cache.get(order.address)
    
    if not order_coords:
        return [], True  # Ошибка координат
    
    results = []
    for restaurant in restaurants:
        rest_coords = coords_cache.get(restaurant.address)
        distance = calculate_distance(order_coords, rest_coords)
        results.append({
            'restaurant': restaurant,
            'distance': distance
        })
    
    # Сортируем по расстоянию
    results.sort(
        key=lambda x: x['distance'] if x['distance'] is not None else float('inf')
    )
    
    return results, False


def mark_coords_errors(order_ids):
    """Обновляет флаг coords_error для заказов. Атомарная функция."""
    if order_ids:
        Order.objects.filter(id__in=order_ids).update(coords_error=True)