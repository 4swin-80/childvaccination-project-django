from django import forms
from .models import Child

class ChildForm(forms.ModelForm):

    class Meta:
        model = Child
        fields = ['name', 'dob', 'gender', 'blood_group']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }
