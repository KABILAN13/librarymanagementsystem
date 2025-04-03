from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import UserRegisterForm
from .models import Book




class CustomUserAdmin(UserAdmin):
    model = CustomUser
    add_form = UserRegisterForm
    
    # Fields to display in the admin list view
    list_display = ['username', 'email', 'user_type', 'is_staff']
    
    # Fields to filter by in the admin
    list_filter = ['user_type', 'is_staff', 'is_superuser']
    
    # Fieldsets for the edit page
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone', 'address')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'user_type'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Fieldsets for the add page
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_type', 'phone', 'address'),
        }),
    )
    
    search_fields = ('username', 'email')
    ordering = ('username',)

# Register the CustomUser with the custom admin class
admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    def delete_model(self, request, obj):
        from django.db import connection
        try:
            obj.delete()
        except Exception as e:
            if 'accounts_checkout' in str(e):
                # Direct SQL fallback
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM accounts_book WHERE id = %s",
                        [obj.id]
                    )
                self.message_user(request, "Book deleted (used emergency method)")
            else:
                raise