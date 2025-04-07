from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.views.generic import ListView
from io import BytesIO
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Checkout
from .models import Book, Checkout, CustomUser, BookRequest  # Add BookRequest here
from .forms import (
    BookForm, BookSearchForm, CheckoutForm,
    UserRegisterForm, UserLoginForm, UserUpdateForm,
    BookRequestForm  # Make sure this is imported
)
from datetime import timedelta
from django.db.models import Q


def home(request):
    context = {
        'welcome_message': 'Welcome to Our Library',
        'recent_books': Book.objects.order_by('-id')[:4],
        'user': request.user
    }
    return render(request, 'accounts/home.html', context)

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.user_type = 3  # Force Member role for public registration
            user.save()
            login(request, user)
            messages.success(request, f'Account created for {user.username}!')
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user:
                login(request, user)
                messages.info(request, f"You are now logged in as {user.username}.")
                return redirect('home')
        messages.error(request, "Invalid username or password.")
    return render(request, 'accounts/login.html', {'form': UserLoginForm()})

@login_required
def user_logout(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')

@login_required
def profile(request):
    return render(request, 'accounts/profile.html')

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
        if title := form.cleaned_data['title']:
            books = books.filter(title__icontains=title)
        if author := form.cleaned_data['author']:
            books = books.filter(author__icontains=author)
        if genre := form.cleaned_data['genre']:
            books = books.filter(genre=genre)
        if publisher := form.cleaned_data['publisher']:
            books = books.filter(publisher__icontains=publisher)
    
    paginator = Paginator(books, 10)
    return render(request, 'accounts/book_list.html', {
        'page_obj': paginator.get_page(request.GET.get('page')),
        'form': form
    })

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def add_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.available = book.quantity  # Set available copies
            book.save()
            messages.success(request, f'Book "{book.title}" added successfully!')
            return redirect('book-list')
    else:
        form = BookForm(initial={'quantity': 10})
    return render(request, 'books/add.html', {'form': form})

@login_required
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    return render(request, 'accounts/book_detail.html', {'book': book})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def book_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Book updated successfully!')
            return redirect('book-detail', pk=book.pk)
    else:
        form = BookForm(instance=book)
    return render(request, 'accounts/book_edit.html', {'form': form, 'book': book})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def book_delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        messages.success(request, f'"{book.title}" was deleted successfully')
        return redirect('book-list')
    return render(request, 'accounts/book_confirm_delete.html', {'book': book})

@login_required
def member_list(request):
    members = CustomUser.objects.filter(user_type=3)
    return render(request, 'accounts/member_list.html', {'members': members})

@login_required
def member_detail(request, pk):
    member = get_object_or_404(CustomUser, pk=pk)
    return render(request, 'accounts/member_detail.html', {'member': member})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def issue_book(request):
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    checkout = form.save(commit=False)
                    checkout.checkout_date = timezone.now()
                    if not checkout.book.checkout_copies(checkout.quantity):
                        raise ValidationError("Not enough copies available")
                    checkout.save()
                    messages.success(request, 
                        f'Checked out {checkout.quantity} copy(ies) of "{checkout.book.title}"')
                    return redirect('active-loans')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    else:
        initial = {}
        if 'book_id' in request.GET:
            initial['book'] = get_object_or_404(Book, id=request.GET['book_id'])
        form = CheckoutForm(initial=initial)
    
    return render(request, 'accounts/issue_book.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def return_book(request, checkout_id):
    checkout = get_object_or_404(Checkout, id=checkout_id)
    
    if request.method == 'POST':
        checkout.returned = True
        checkout.return_date = timezone.now()
        checkout.save()  # This will trigger fine calculation
        
        if checkout.total_fine > 0:
            messages.warning(request, 
                f'Book returned late! Fine: ${checkout.total_fine:.2f}')
        else:
            messages.success(request, 'Book returned successfully')
        
        return redirect('active-loans')
    
    # Calculate potential fine if returned today
    potential_fine = 0
    if timezone.now() > checkout.due_date:
        days_late = (timezone.now() - checkout.due_date).days
        potential_fine = days_late * checkout.daily_fine_rate
    
    context = {
        'checkout': checkout,
        'potential_fine': potential_fine,
        'status': checkout.get_status()
    }
    return render(request, 'accounts/return_book.html', context)

@login_required
def loan_list(request):
    loans = Checkout.objects.all()
    if request.user.is_member():
        loans = loans.filter(member=request.user)
    return render(request, 'accounts/loan_list.html', {'loans': loans.order_by('-checkout_date')})

@login_required
def loan_history(request):
    loans = Checkout.objects.all()
    
    # For existing records without the new fields
    for loan in loans:
        if not hasattr(loan, 'daily_fine_rate'):
            loan.daily_fine_rate = 10.00  # Default value
        if not hasattr(loan, 'total_fine'):
            loan.total_fine = 0.00
    
    return render(request, 'accounts/loan_history.html', {'loans': loans})

@login_required
def active_loans(request):
    loans = Checkout.objects.filter(returned=False)
    if request.user.is_member():
        loans = loans.filter(member=request.user)
    return render(request, 'accounts/active_loans.html', {'loans': loans})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def return_book(request, checkout_id):
    checkout = get_object_or_404(Checkout, id=checkout_id)
    
    if request.method == 'POST':
        if checkout.mark_returned():
            messages.success(request, 
                f'Successfully returned {checkout.quantity} copy(ies) of "{checkout.book.title}"')
            return redirect('active-loans')
        else:
            messages.error(request, 'This book was already returned')
    
    context = {
        'checkout': checkout,
        'status': checkout.get_status()
    }
    return render(request, 'accounts/return_book.html', context)


@login_required
def due_date_report(request):
    # Get loans due soon or overdue
    checkouts = Checkout.objects.filter(
        returned=False
    ).filter(
        Q(due_date__lte=timezone.now() + timedelta(days=3)) | 
        Q(due_date__lt=timezone.now())
    ).order_by('due_date')
    
    context = {
        'overdue': checkouts.filter(due_date__lt=timezone.now()),
        'due_soon': checkouts.filter(
            due_date__gte=timezone.now(),
            due_date__lte=timezone.now() + timedelta(days=3)
        ),
    }
    return render(request, 'accounts/due_date_report.html', context)


@login_required
@user_passes_test(lambda u: u.is_member())
def request_book(request):
    if request.method == 'POST':
        form = BookRequestForm(request.POST)
        if form.is_valid():
            request_obj = form.save(commit=False)
            request_obj.member = request.user
            request_obj.save()
            messages.success(request, 'Your book request has been submitted!')
            return redirect('my-requests')
    else:
        form = BookRequestForm()
    return render(request, 'accounts/request_book.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_member())
def my_requests(request):
    requests = BookRequest.objects.filter(member=request.user)
    return render(request, 'accounts/my_requests.html', {'requests': requests})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def manage_requests(request):
    requests = BookRequest.objects.filter(status='PENDING')
    return render(request, 'accounts/manage_requests.html', {'requests': requests})

@login_required
@user_passes_test(lambda u: u.is_librarian_or_admin())
def process_request(request, pk):
    req = get_object_or_404(BookRequest, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('response_notes', '')
        
        if action in ['approve', 'reject']:
            req.status = 'APPROVED' if action == 'approve' else 'REJECTED'
            req.response_notes = notes
            req.response_date = timezone.now()
            req.save()
            
            if action == 'approve':
                messages.success(request, 'Request approved!')
            else:
                messages.warning(request, 'Request rejected.')
                
            return redirect('manage-requests')
    
    return render(request, 'accounts/process_request.html', {'req': req})

@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Checkout, pk=pk)
    
    # Verify permission - users should only see their own loans unless staff
    if not request.user.is_admin and loan.member != request.user:
        raise PermissionDenied("You don't have permission to view this loan")
    
    context = {
        'loan': loan,
        'can_return': not loan.returned and request.user.is_staff,
    }
    return render(request, 'accounts/loan_detail.html', context)

class IssuedBooksReportView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Checkout
    template_name = 'accounts/reports/issued_books.html'
    context_object_name = 'checkouts'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_librarian_or_admin()

    def get_queryset(self):
        return Checkout.objects.filter(returned=False).select_related('book', 'member')

class OverdueBooksReportView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Checkout
    template_name = 'accounts/reports/overdue_books.html'
    context_object_name = 'checkouts'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_librarian_or_admin()

    def get_queryset(self):
        return Checkout.objects.filter(
            returned=False,
            due_date__lt=timezone.now()
        ).select_related('book', 'member')
    
@login_required
def generate_issued_pdf(request):
    if not request.user.is_staff and not request.user.is_librarian_or_admin():
        return HttpResponse("Unauthorized", status=401)
    
    from .models import Checkout
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="issued_books.pdf"'
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "Currently Issued Books Report")
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Table Header
    p.drawString(100, 700, "Book Title")
    p.drawString(300, 700, "Member")
    p.drawString(450, 700, "Due Date")
    p.drawString(550, 700, "Status")
    
    # Table Content
    y = 680
    p.setFont("Helvetica", 10)
    checkouts = Checkout.get_issued_books_report()
    
    for checkout in checkouts:
        p.drawString(100, y, checkout.book.title[:30])  # Limit title length
        p.drawString(300, y, checkout.member.get_full_name())
        p.drawString(450, y, checkout.due_date.strftime('%Y-%m-%d'))
        
        if checkout.is_overdue:
            status = f"Overdue ({checkout.days_overdue} days)"
            p.setFillColorRGB(1, 0, 0)  # Red
        elif checkout.due_soon:
            status = "Due Soon"
            p.setFillColorRGB(1, 0.5, 0)  # Orange
        else:
            status = "On Time"
            p.setFillColorRGB(0, 0.5, 0)  # Green
            
        p.drawString(550, y, status)
        p.setFillColorRGB(0, 0, 0)  # Reset to black
        y -= 20
        
        if y < 50:  # New page if running out of space
            p.showPage()
            y = 750
    
    p.showPage()
    p.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

def generate_overdue_pdf(request):
    if not request.user.is_staff and not request.user.is_librarian_or_admin():
        return HttpResponse("Unauthorized", status=401)
    
    from .models import Checkout
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="overdue_books.pdf"'
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "Overdue Books Report")
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Table Header
    p.drawString(100, 700, "Book Title")
    p.drawString(300, 700, "Member")
    p.drawString(450, 700, "Due Date")
    p.drawString(550, 700, "Days Overdue")
    p.drawString(650, 700, "Fine")
    
    # Table Content
    y = 680
    p.setFont("Helvetica", 10)
    checkouts = Checkout.get_overdue_books_report()
    
    for checkout in checkouts:
        p.drawString(100, y, checkout.book.title[:30])
        p.drawString(300, y, checkout.member.get_full_name())
        p.drawString(450, y, checkout.due_date.strftime('%Y-%m-%d'))
        p.drawString(550, y, str(checkout.days_overdue))
        p.drawString(650, y, f"${checkout.total_fine:.2f}")
        y -= 20
        
        if y < 50:
            p.showPage()
            y = 750
    
    p.showPage()
    p.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response