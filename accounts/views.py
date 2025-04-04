from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, permission_required, PermissionDenied
from django.contrib import messages
from .forms import UserRegisterForm, UserLoginForm
from .forms import UserUpdateForm  
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Book, CustomUser
from .forms import BookForm, BookSearchForm
from django.http import HttpResponse
from django.db import connection


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'accounts/book_detail.html', {'book': book})

@login_required
def home(request):
    try:
        # Basic data for the home page
        context = {
            'welcome_message': 'Welcome to Our Library',
            'recent_books': Book.objects.order_by('-id')[:4],  # Get 4 most recent books
            'user': request.user
        }
        return render(request, 'accounts/home.html', context)
    except Exception as e:
        from django.http import HttpResponse
        return HttpResponse(f"Home page is currently unavailable. Error: {str(e)}")


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # For security, you might want to override the user_type here
            # For example, force all public registrations to be Members:
            user.user_type = 3  # Member
            user.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            login(request, user)
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"You are now logged in as {username}.")
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.info(request, "You have successfully logged out.") 
    return redirect('login')

@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {'user': request.user})

@login_required
def profile_update(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)
    
    return render(request, 'accounts/profile_update.html', {'form': form})

@login_required
def book_list(request):
    books = Book.objects.all()
    form = BookSearchForm(request.GET or None)
    
    if form.is_valid():
        if form.cleaned_data['title']:
            books = books.filter(title__icontains=form.cleaned_data['title'])
        if form.cleaned_data['author']:
            books = books.filter(author__icontains=form.cleaned_data['author'])
        if form.cleaned_data['genre']:
            books = books.filter(genre=form.cleaned_data['genre'])
        if form.cleaned_data['publisher']:
            books = books.filter(publisher__icontains=form.cleaned_data['publisher'])
    
    paginator = Paginator(books, 10)  # Show 10 books per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'accounts/book_list.html', {
        'page_obj': page_obj,
        'form': form
    })

@login_required
def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)  # Important for file uploads
        if form.is_valid():
            book = form.save()
            return redirect('book-list')  # Redirect to book list after success
    else:
        form = BookForm()
    
    return render(request, 'books/add.html', {'form': form})

@login_required
def book_add(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('book-list')  # Redirect to book list after success
    else:
        form = BookForm()
    return render(request, 'books/add.html', {'form': form})

@login_required
def book_edit(request, pk):
    # Only allow librarians and admins to edit books
    if not (request.user.is_librarian() or request.user.is_admin()):
        return redirect('home')
    
    book = get_object_or_404(Book, pk=pk)
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book updated successfully!')
            return redirect('book-detail', pk=book.pk)
    else:
        form = BookForm(instance=book)
    
    return render(request, 'accounts/book_edit.html', {
        'form': form,
        'book': book
    })

@login_required
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    
    if request.method == 'POST':
        book.delete()
        messages.success(request, f'"{book.title}" was deleted successfully')
        return redirect('book-list')
    
    return render(request, 'accounts/book_confirm_delete.html', {'book': book})

@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'accounts/book_detail.html', {'book': book})


@login_required
def member_list(request):
    members = CustomUser.objects.filter(user_type=3)  # Assuming 3 is member type
    return render(request, 'accounts/member_list.html', {'members': members})

@login_required
def member_detail(request, pk):
    member = get_object_or_404(CustomUser, pk=pk)
    return render(request, 'accounts/member_detail.html', {'member': member})