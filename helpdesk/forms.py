from dataclasses import fields
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Ticket, Comment


class UserCreateForm(UserCreationForm, forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['is_student', 'user_name', 'avatar', 'first_name', 'other_name', 'email', 'password1', 'password2']
        widgets = {
            'is_student': forms.CheckboxInput(),
        }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['is_student', 'user_name', 'avatar', 'first_name', 'other_name', 'department', 'biography', 'password']


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = '__all__'
        exclude = ['creator', 'contributors']


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['body']

