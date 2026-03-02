from django import forms
from django.db import models
from django.shortcuts import redirect, render
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.decorators import user_passes_test

from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views

from foodcartapp.models import Product, Restaurant, Order, OrderItem
from .utils import (
    get_restaurants_by_ids,
    fetch_coordinates_for_addresses,
    calculate_distance_for_order,
    mark_coords_errors,
)


class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    products_with_restaurant_availability = []
    for product in products:
        availability = {item.restaurant_id: item.availability for item in product.menu_items.all()}
        ordered_availability = [availability.get(restaurant.id, False) for restaurant in restaurants]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurant_availability': products_with_restaurant_availability,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_orders(request):
    # 1. Получаем заказы (без координат)
    orders = Order.objects.exclude(status='COMPLETED').with_total_price().prefetch_related(
        models.Prefetch(
            'items',
            queryset=OrderItem.objects.select_related('product')
        )
    )
    
    # 2. Разделяем на необработанные и остальные
    unprocessed_orders = []
    other_orders = []
    
    for order in orders:
        if order.status == 'UNPROCESSED':
            unprocessed_orders.append(order)
        else:
            other_orders.append(order)
    
    # 3. Для необработанных: находим доступные рестораны и считаем расстояния
    if unprocessed_orders:
        unprocessed_ids = [order.id for order in unprocessed_orders]
        
        # Получаем заказы с available_restaurant_ids (только ID, без координат!)
        orders_with_restaurants = Order.objects.filter(
            id__in=unprocessed_ids
        ).with_available_restaurants()
        
        # Собираем все ID ресторанов для загрузки
        all_restaurant_ids = set()
        for order in orders_with_restaurants:
            all_restaurant_ids.update(order.available_restaurant_ids)
        
        # Загружаем рестораны одним запросом
        restaurants = get_restaurants_by_ids(all_restaurant_ids)
        restaurants_dict = {r.id: r for r in restaurants}
        
        # Собираем адреса для геокодинга
        addresses = set()
        for order in orders_with_restaurants:
            if order.address:
                addresses.add(order.address)
        for r in restaurants:
            if r.address:
                addresses.add(r.address)
        
        # Получаем координаты (атомарная функция)
        coords_cache = fetch_coordinates_for_addresses(addresses)
        
        # Считаем расстояния для каждого заказа
        error_order_ids = []
        
        for order in orders_with_restaurants:
            # Получаем объекты ресторанов для этого заказа
            order_restaurants = [
                restaurants_dict[rid] 
                for rid in order.available_restaurant_ids 
                if rid in restaurants_dict
            ]
            
            # Атомарная функция: считает расстояния
            distances, has_error = calculate_distance_for_order(
                order, order_restaurants, coords_cache
            )
            
            if has_error:
                order.coords_error = True
                order.available_restaurants = []
                error_order_ids.append(order.id)
            else:
                order.coords_error = False
                order.available_restaurants = distances
        
        # Сохраняем ошибки координат в БД
        mark_coords_errors(error_order_ids)
        
        # Обновляем unprocessed_orders на обработанные версии
        orders_by_id = {order.id: order for order in orders_with_restaurants}
        for index, order in enumerate(unprocessed_orders):
            if order.id in orders_by_id:
                unprocessed_orders[index] = orders_by_id[order.id]
    
    # 4. Объединяем и возвращаем
    all_orders = unprocessed_orders + other_orders
    
    return render(request, template_name='order_items.html', context={
        'order_items': all_orders,
    })