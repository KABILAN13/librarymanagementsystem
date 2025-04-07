from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import connection
from django.utils import timezone
from .models import Book, Checkout, CustomUser
from .forms import UserRegisterForm
from accounts import models

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    add_form = UserRegisterForm
    
    list_display = ['username', 'email', 'get_user_type_display', 'is_staff']
    list_filter = ['user_type', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'address')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 
                      'groups', 'user_permissions', 'user_type'),
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 
                'password1', 'password2',
                'user_type', 'phone', 'address',
                'first_name', 'last_name'
            ),
        }),
    )

    def get_user_type_display(self, obj):
        return obj.get_user_type_display()
    get_user_type_display.short_description = 'User Type'

admin.site.register(CustomUser, CustomUserAdmin)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'genre', 
        'available_copies', 'total_copies', 
        'is_available'
    ]
    list_filter = ['genre', 'author']
    search_fields = ['title', 'author', 'isbn']
    readonly_fields = ['available']
    actions = ['reset_availability']
    
    def available_copies(self, obj):
        return obj.available
    available_copies.short_description = 'Available'
    
    def total_copies(self, obj):
        return obj.quantity
    total_copies.short_description = 'Total'
    
    def is_available(self, obj):
        return obj.available > 0
    is_available.boolean = True
    is_available.short_description = 'Available?'
    
    def reset_availability(self, request, queryset):
        updated = queryset.update(available=models.F('quantity'))
        self.message_user(request, f"{updated} books availability reset")
    reset_availability.short_description = "Reset available copies to total"
    
    def delete_model(self, request, obj):
        try:
            obj.delete()
        except Exception as e:
            if 'accounts_checkout' in str(e):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM accounts_book WHERE id = %s",
                        [obj.id]
                    )
                self.message_user(request, "Book deleted (used emergency method)")
            else:
                raise

@admin.register(Checkout)
class CheckoutAdmin(admin.ModelAdmin):
    list_display = [
        'book_title', 'member_name', 
        'checkout_date', 'due_date', 
        'return_status','get_due_status', 'days_overdue' ,'total_fine'
    ]
    list_filter = ['returned', 'checkout_date', 'due_date']
    search_fields = ['book__title', 'member__username']
    date_hierarchy = 'checkout_date'
    actions = ['mark_returned','send_overdue_notices','recalculate_fines']
    
    def book_title(self, obj):
        return obj.book.title
    book_title.short_description = 'Book'
    book_title.admin_order_field = 'book__title'
    
    def member_name(self, obj):
        return f"{obj.member.get_full_name()} ({obj.member.username})"
    member_name.short_description = 'Member'
    
    def return_status(self, obj):
        if obj.returned:
            return f"Returned on {obj.return_date.strftime('%Y-%m-%d')}"
        return "Checked Out"
    return_status.short_description = 'Status'
    
    def days_overdue(self, obj):
        if not obj.returned and timezone.now() > obj.due_date:
            return (timezone.now() - obj.due_date).days
        return 0
    days_overdue.short_description = 'Days Overdue'
    
    def mark_returned(self, request, queryset):
        updated = 0
        for checkout in queryset:
            if not checkout.returned:
                checkout.returned = True
                checkout.return_date = timezone.now()
                checkout.book.return_copy()
                checkout.save()
                updated += 1
        self.message_user(request, f"{updated} checkouts marked as returned")
    mark_returned.short_description = "Mark selected as returned"

    def recalculate_fines(self, request, queryset):
        for checkout in queryset:
            checkout.calculate_fine()
        self.message_user(request, "Fines recalculated")
    recalculate_fines.short_description = "Recalculate fines for selected checkouts"

    @admin.action(description='Send overdue notices')
    def send_overdue_notices(self, request, queryset):
        overdue = queryset.filter(
            returned=False,
            due_date__lt=timezone.now()
        )
        # Add your email sending logic here
        self.message_user(request, f"{overdue.count()} overdue notices sent")