from rest_framework import serializers
from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    """Serializer for Account"""
    
    class Meta:
        model = Account
        fields = ['id', 'name', 'plan', 'is_active', 'phone', 'address', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

