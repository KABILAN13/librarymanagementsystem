from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser
from .models import Book


# In forms.py
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['user_type'].choices = [(3, 'Member')]  # Only show Member option

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=True)
    address = forms.CharField(widget=forms.Textarea, required=True)
    user_type = forms.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES,
        widget=forms.RadioSelect,  # Makes it appear as radio buttons
        initial=3,  # Default to Member
        required=True
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2', 
                'user_type', 'phone', 'address', 'first_name', 'last_name']

class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)

    username = forms.CharField(widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Username or Email'}),
        label="Username or Email")

    password = forms.CharField(widget=forms.PasswordInput(
        attrs={'class': 'form-control', 'placeholder': 'Password'}))

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add any custom field attributes here if needed
        self.fields['email'].required = True

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'genre', 'isbn', 'publisher', 
                 'publication_date', 'quantity', 'cover_image', 'description']
        
        widgets = {
            'publication_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BookSearchForm(forms.Form):
    title = forms.CharField(required=False)
    author = forms.CharField(required=False)
    genre = forms.ChoiceField(choices=Book.GENRE_CHOICES, required=False)
    publisher = forms.CharField(required=False)