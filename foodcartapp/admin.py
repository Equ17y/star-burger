from django.contrib import admin
from django.shortcuts import reverse
from django.templatetags.static import static
from django.utils.html import format_html

from .models import Product
from .models import ProductCategory
from .models import Restaurant
from .models import RestaurantMenuItem
from .models import Order
from .models import OrderItem
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme

class RestaurantMenuItemInline(admin.TabularInline):
    model = RestaurantMenuItem
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    search_fields = [
        'name', 
        'address', 
        'contact_phone'
    ]
    list_display = [
        'name', 
        'address', 
        'contact_phone'
    ]
    inlines = [RestaurantMenuItemInline]
    
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = [
        'product', 
        'quantity',
        'price'
    ]
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'price':
            field.widget.attrs['min'] = '0'
        return field
    
    
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = [
        'id',
        'firstname', 
        'lastname', 
        'phonenumber', 
        'address',
        'status'
    ]
    search_fields = [
        'firstname', 
        'lastname', 
        'phonenumber', 
        'address'
    ]
    
    
    def response_change(self, request, obj):
        next_url = request.GET.get('next')
        
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure()
        ):
            return HttpResponseRedirect(next_url)
        
        return super().response_change(request, obj)       


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'get_image_list_preview',
        'name',
        'category',
        'price',
    ]
    list_display_links = [
        'name',
    ]
    list_filter = [
        'category',
    ]
    search_fields = [
        # FIXME SQLite can not convert letter case for cyrillic words properly, so search will be buggy.
        # Migration to PostgreSQL is necessary
        'name',
        'category__name',
    ]

    inlines = [
        RestaurantMenuItemInline
    ]
    fieldsets = (
        ('Общее', {
            'fields': [
                'name',
                'category',
                'image',
                'get_image_preview',
                'price',
            ]
        }),
        ('Подробно', {
            'fields': [
                'special_status',
                'description',
            ],
            'classes': [
                'wide'
            ],
        }),
    )

    readonly_fields = [
        'get_image_preview',
    ]

    class Media:
        css = {
            "all": (
                static("admin/foodcartapp.css")
            )
        }

    def get_image_preview(self, obj):
        if not obj.image:
            return 'выберите картинку'
        return format_html('<img src="{url}" style="max-height: 200px;"/>', url=obj.image.url)
    get_image_preview.short_description = 'превью'

    def get_image_list_preview(self, obj):
        if not obj.image or not obj.id:
            return 'нет картинки'
        edit_url = reverse('admin:foodcartapp_product_change', args=(obj.id,))
        return format_html('<a href="{edit_url}"><img src="{src}" style="max-height: 50px;"/></a>', edit_url=edit_url, src=obj.image.url)
    get_image_list_preview.short_description = 'превью'


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    pass
