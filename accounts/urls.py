from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import add_book

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.profile_update, name='profile-update'),
    path('password-change/',
         auth_views.PasswordChangeView.as_view(
             template_name='accounts/password_change.html',
             success_url='/password-change/done/'
         ),
         name='password-change'),
    path('password-change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='accounts/password_change_done.html'
         ),
         name='password-change-done'),
    
    path('members/<int:pk>/', views.member_detail, name='member-detail'),
    path('members/', views.member_list, name='member-list'),
    path('books/<int:pk>/edit/', views.book_edit, name='book-edit'),
    path('books/', views.book_list, name='book-list'),
    path('books/add/', views.book_add, name='book-add'),
    path('books/<int:pk>/', views.book_detail, name='book-detail'),
    path('books/<int:pk>/edit/', views.book_edit, name='book-edit'),
    path('books/<int:pk>/delete/', views.book_delete, name='book-delete'),
    path('books/add/', views.book_add, name='book-add'),
]