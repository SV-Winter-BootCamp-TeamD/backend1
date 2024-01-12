from rest_framework import serializers
from .models import Component


class TextUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ['component_url']