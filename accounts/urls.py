from django.urls import include, path
from . import views
from django.contrib.auth import views as auth_views
from .views import add_book

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('reports/issued-books/', views.IssuedBooksReportView.as_view(), name='issued-books-report'),
    path('reports/overdue-books/', views.OverdueBooksReportView.as_view(), name='overdue-books-report'),
    path('reports/issued-books/pdf/', views.generate_issued_pdf, name='generate-issued-pdf'),
    path('reports/overdue-books/pdf/', views.generate_overdue_pdf, name='generate-overdue-pdf'),
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
    
    path('books/request/', views.request_book, name='request-book'),
    path('requests/', include([
        path('my/', views.my_requests, name='my-requests'),
        path('manage/', views.manage_requests, name='manage-requests'),
        path('process/<int:pk>/', views.process_request, name='process-request'),
    ])),
    path('reports/due-dates/', views.due_date_report, name='due-date-report'),
    path('loans/<int:checkout_id>/return/', views.return_book, name='return-book'),
    path('members/<int:pk>/', views.member_detail, name='member-detail'),
    path('members/', views.member_list, name='member-list'),
    path('books/<int:pk>/edit/', views.book_edit, name='book-edit'),
    path('books/', views.book_list, name='book-list'),
    path('books/add/', views.add_book, name='book-add'),
    path('books/<int:pk>/', views.book_detail, name='book-detail'),
    path('books/<int:pk>/edit/', views.book_edit, name='book-edit'),
    path('books/<int:pk>/delete/', views.book_delete, name='book-delete'),
    path('books/add/', views.add_book, name='book-add'),
    path('books/issue/', views.issue_book, name='issue-book'),
    path('books/return/<int:checkout_id>/', views.return_book, name='return-book'),
    path('loans/', include([
        path('', views.loan_list, name='loan-list'),
        path('active/', views.active_loans, name='active-loans'),
        path('history/', views.loan_list, name='loan-history'),
        path('loans/<int:pk>/', views.loan_detail, name='loan-detail'),
    ])),
]