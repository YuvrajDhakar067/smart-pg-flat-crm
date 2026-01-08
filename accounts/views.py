from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Account
from .serializers import AccountSerializer
from api.permissions import IsOwnerOrManager
from api.filters import AccountFilterBackend


# Template views (for frontend)
@csrf_protect
def register(request):
    """User self-registration"""
    from users.models import User
    from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
    
    class UserCreationForm(BaseUserCreationForm):
        """Custom form that works with our User model"""
        class Meta:
            model = User
            fields = ("username",)
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            
            # Create account first
            account_name = request.POST.get('account_name', username)
            account = Account.objects.create(
                name=account_name,
                plan='FREE',
                phone=request.POST.get('phone', '')
            )
            
            # Create user with account
            user = form.save(commit=False)
            user.account = account
            user.role = 'OWNER'
            user.phone = request.POST.get('phone', '')
            user.save()
            
            # Auto login
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f'Welcome {username}! Your account has been created.')
                return redirect('properties:dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


@csrf_protect
def login_view(request):
    """Login view"""
    from django.contrib.auth import authenticate, login
    
    if request.user.is_authenticated:
        return redirect('properties:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('properties:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')


@login_required
def profile(request):
    """User profile page"""
    account = getattr(request, 'account', None)
    if not account and hasattr(request.user, 'account'):
        account = request.user.account
    return render(request, 'accounts/profile.html', {'account': account})


# API views
class AccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Account management
    Only owners can create/update accounts
    """
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrManager]
    filter_backends = [AccountFilterBackend]
    
    def get_queryset(self):
        """Return accounts for the authenticated user - OPTIMIZED"""
        # OPTIMIZED: No need for select_related on Account itself, but ensure efficient query
        account_id = self.request.user.account.id
        return Account.objects.filter(id=account_id).only('id', 'name', 'plan', 'is_active', 'created_at')
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current user's account"""
        account = request.user.account
        serializer = self.get_serializer(account)
        return Response(serializer.data)
