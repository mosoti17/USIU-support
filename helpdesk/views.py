from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
import os
from django.conf import settings
import json
from datetime import date, datetime, timedelta
import pytz
import tzlocal
from django.utils import timezone
from django.db import connection
from django.http import JsonResponse
from django.core import serializers
from multiprocessing import context
from typing import Any
from unicodedata import name
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
# from django.core.mail import send_mail
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser, Department, Ticket, Subject, Comment
from .forms import TicketForm, CommentForm, UserCreateForm, UserUpdateForm


# Views

def login_options(request):
    return render(request, 'base/login_options.html')


def staff_login_page(request):
    login_page = 'staff_login'
    
    if request.user.is_authenticated:
        if request.user.is_staff and request.user.is_superuser == False:
            request.user.is_active = True
            return redirect('home')
        elif request.user.is_staff and request.user.is_superuser == True:
            request.user.is_active = True
            return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if email == "" and password == "":
            return HttpResponse("Please fill out email and password field.")
        elif email == "":
            return HttpResponse("Please fill out email field.")
        elif password == "":
            return HttpResponse("Please fill out password field.")
        elif user is not None and user.is_staff:
            login(request, user)
            return redirect('home')
        else:
            # loginMsgError = messages.error(request, "Invalid username or password")
            return HttpResponse("Invalid username or password. You may want to try logging in as a student.")
            # return loginMsgError

    context = {'page': login_page}

    return render(request, 'base/staff_login_register.html', context)


def student_login_page(request):
    login_page = 'student_login'
    
    if request.user.is_authenticated:
        if request.user.is_student and (request.user.is_staff == False or request.user.is_staff == True):
            request.user.is_active = True
            return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        user= authenticate(request, email=email, password=password)

        if email == "" and password == "":
            return HttpResponse("Please fill out email and password field.")
        elif email == "":
            return HttpResponse("Please fill out email field.")
        elif password == "":
            return HttpResponse("Please fill out password field.")
        elif user is not None and user.is_student:
            login(request, user)
            return redirect('home')
        else:
            # loginMsgError = messages.error(request, "Invalid username or password")
            return HttpResponse("Invalid username or password. You may want to try logging in as a staff.")
            # return loginMsgError

    context = {'page': login_page}

    return render(request, 'base/student_login_register.html', context)


# def admin_login(request):
#     return render(request, 'base/')


def logout_user(request):
    logout(request)
    request.user.is_active = False

    return redirect('login_options')


def staff_register_page(request):
    form = UserCreateForm()

    try:
        if request.method == 'POST':
            form = UserCreateForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                user.user_name = user.user_name
                user.is_staff = True
                user.is_active = True
                user.save()
                login(request, user)
                return redirect('home')
    except Exception as e:
        return HttpResponse("Oops! An error occurred during staff registration. " + e)
        
    context = {'form': form}
    return render(request, 'base/staff_login_register.html', context)


def student_register_page(request):
    form = UserCreateForm()

    try:
        if request.method == 'POST':
            form = UserCreateForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                user.user_name = user.user_name
                user.is_student = True
                user.is_active = True
                user.save()
                login(request, user)
                return redirect('home')
    except Exception as e:
        return HttpResponse("Oops! An error occurred during student registration. " + e)
        
    context = {'form': form}
    return render(request, 'base/student_login_register.html', context)


# @login_required(login_url='login_options')
def home(request):
    query = request.GET.get('query') if request.GET.get('query') != None else ''

    tickets = Ticket.objects.filter(
        Q(subject__name__icontains=query) |
        Q(creator__user_name__icontains=query) |
        Q(creator__department__name__icontains=query) |
        Q(is_open__icontains=query) |
        Q(is_in_progress__icontains=query) |
        Q(is_resolved__icontains=query) |
        Q(is_closed__icontains=query)
    ).distinct()
    
    departments = Department.objects.filter(Q(name__icontains=query)).distinct()
    all_users = CustomUser.objects.all()
    subjects = Subject.objects.all()[0:8]
    
    ticket_comments = Comment.objects.filter(Q(ticket__subject__name__icontains=query))
    ticket_count = tickets.count()

    context = {'tickets': tickets, 'subjects': subjects, 'ticket_comments': ticket_comments, 
               'departments': departments, 'ticket_count': ticket_count, 'all_users': all_users
               }
    if request.user.is_authenticated:
        return render(request, 'base/home.html', context)
    else:
        return render(request, 'base/login_options.html', context)


@login_required(login_url='login_options')
def ticket(request, pk):
    ticket = Ticket.objects.get(id=pk)
    ticket_comments = ticket.comment_set.all()
    contributors = ticket.contributors.all()
    comment_count = ticket_comments.count()

    if request.method == 'POST':
        user = request.user
        body=request.POST.get('comment_body')
        
        if body == "":
            return HttpResponse("Please fill in comment field to contribute.")
        else:
            comment = Comment.objects.create(
                user=request.user,
                ticket=ticket,
                body=request.POST.get('comment_body'),
            )
            
        ticket.contributors.add(user)
        
        return redirect('ticket', pk=ticket.id)

    context = {'ticket': ticket, 'ticket_comments': ticket_comments, 
               'comment_count': comment_count, 'contributors': contributors
               }
    return render(request, 'base/ticket.html', context)


@login_required(login_url='staff_login')
def user_profile(request, pk):
    user = CustomUser.objects.get(id=pk)
    tickets = user.ticket_set.all()
    ticket_comments = user.comment_set.all()
    tickets_count = tickets.count()
    subjects = Subject.objects.all()[0:6]

    context = {'user': user, 'tickets': tickets, 
               'ticket_comments': ticket_comments, 
               'tickets_count': tickets_count, 'subjects': subjects}
    return render(request, 'base/user_profile.html', context)


@login_required(login_url='login_options')
def create_ticket(request):
    form = TicketForm()
    subjects = Subject.objects.all()

    if request.method == 'POST':
        subject = request.POST.get('subject')
        subject, created = Subject.objects.get_or_create(name=subject)

        Ticket.objects.create(
            creator=request.user,
            subject=subject,
            description=request.POST.get('description')
        )
        
        # if form.is_valid():
        #     ticket = form.save(commit=False)
        #     ticket.creator = request.user
        #     ticket.save()
        
        return redirect('home')

    context = {'form': form, 'subjects':subjects}
    return render(request, 'base/ticket_creation_form.html', context)


@login_required(login_url='login_options')
def update_ticket(request, pk):
    ticket = Ticket.objects.get(id=pk)
    form = TicketForm(instance=ticket)
    subjects = Subject.objects.all()

    if request.user != ticket.creator:
        return HttpResponse("You have no permission to modify this ticket.")

    if request.method == 'POST':
        subject = request.POST.get('subject')
        subject, created = Subject.objects.get_or_create(name=subject)
        ticket.subject = subject
        ticket.description = request.POST.get('description')
        ticket.save()
        
        # form = TicketForm(request.POST, instance=ticket)
        # if form.is_valid():
        #     form.save()
        
        return redirect('home')

    context = {'form': form, 'subjects': subjects, 'ticket': ticket}
    return render(request, 'base/ticket_update_form.html', context)


@login_required(login_url='login_options')
def delete_ticket(request, pk):
    ticket = Ticket.objects.get(id=pk)

    if request.user != ticket.creator:
        return HttpResponse("You have no permission to delete this ticket.")

    if request.method == 'POST':
        ticket.delete()
        return redirect('home')

    context = {'obj_to_delete': ticket}
    return render(request, 'base/delete.html', context)


@login_required(login_url='login_options')
def delete_comment(request, pk):
    comment = Comment.objects.get(id=pk)

    if request.user != comment.user:
        return HttpResponse("You have no permission to delete this comment.")

    if request.method == 'POST':
        comment.delete()
        return redirect('ticket')

    context = {'obj_to_delete': comment}
    return render(request, 'base/delete.html', context)


@login_required(login_url='login_options')
def edit_comment(request, pk):
    comment = Comment.objects.get(id=pk)
    form = CommentForm(instance=comment)
    
    if request.user != comment.user:
        return HttpResponse("You have no permission to modify this comment.")

    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect('ticket', pk=comment.ticket.id)

    context = {'form': form}
    return render(request, 'base/comment_form.html', context)


@login_required(login_url='staff_login')
def update_user(request):
    user = request.user
    form = UserUpdateForm(instance=user)
    
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user-profile', pk=user.id)
    
    context = {'form': form}
    return render(request, 'base/update_user.html',context )


@login_required(login_url='login_options')
def subjects_page(request):
    query = request.GET.get('query') if request.GET.get('query') != None else ''
    subjects = Subject.objects.filter(name__icontains=query)
    
    context = {'subjects': subjects}
    return render(request, 'base/subjects.html', context )


@login_required(login_url='login_options')
def activity_page(request):
    ticket_comments = Comment.objects.all()
    
    context = {'ticket_comments': ticket_comments}
    return render(request, 'base/activity.html', context)


@login_required(login_url='staff_login')
def dashboard(request):
    query = request.GET.get('query') if request.GET.get('query') != None else ''
    
    subjects = Subject.objects.all()
    tickets = Ticket.objects.filter(
        Q(subject__name__icontains=query) |
        Q(creator__user_name__icontains=query)
    )[:6]
    
    ticket_comments = Comment.objects.filter(
        Q(user__user_name__icontains=query) |
        Q(ticket__subject__name__icontains=query)
        )[:3]
    ticket_count = tickets.count()
    open_ticket_count = Ticket.objects.filter(is_open=True).count()
    in_progress_ticket_count = Ticket.objects.filter(is_in_progress=True).count()
    resolved_ticket_count = Ticket.objects.filter(is_resolved=True).count()
    closed_ticket_count = Ticket.objects.filter(is_closed=True).count()

    # Get tickets per day
    open_ticket_per_day = Ticket.objects.filter(created__date=date.today()).count()
    # open_ticket_per_day = Ticket.objects.filter(created__date=date.today()).aggregate(count=Count('id'))
    
    # Get tickets per week
    start_of_week = date.today() - timedelta(days=date.today().weekday())
    end_of_week = start_of_week + timedelta(days=6)
    open_ticket_per_week = Ticket.objects.filter(created__range=(start_of_week, end_of_week)).count()
    # open_ticket_per_week = Ticket.objects.filter(created__date__gte=start_of_week, created__date__lte=end_of_week).aggregate(count=Count('id'))

    # Get tickets per month
    current_month = datetime.now().month
    open_ticket_per_month = Ticket.objects.filter(created__month=current_month).count()
    # open_ticket_per_month = Ticket.objects.filter(created__year=date.today().year, created__month=date.today().month).aggregate(count=Count('id'))

    # Get tickets per year
    current_year = datetime.now().year
    open_ticket_per_year = Ticket.objects.filter(created__year=current_year).count()
    # open_ticket_per_year = Ticket.objects.filter(created__year=date.today().year).aggregate(count=Count('id'))

    # Get registered users per day
    registered_users_per_day = CustomUser.objects.filter(start_date__date=date.today()).aggregate(count=Count('id'))

    # Get the current time
    current_time = datetime.now()

    # Define the time interval (last 24 hours)
    time_interval = current_time - timedelta(hours=24)

    open_ticket_records = Ticket.objects.filter(is_open=True, created__gte=time_interval)
    open_tickets_on_interval = open_ticket_records.count()

    in_progress_ticket_records = Ticket.objects.filter(is_in_progress=True, created__gte=time_interval)
    in_progress_tickets_on_interval = in_progress_ticket_records.count()

    resolved_ticket_records = Ticket.objects.filter(is_resolved=True, created__gte=time_interval)
    resolved_tickets_on_interval = resolved_ticket_records.count()

    closed_ticket_records = Ticket.objects.filter(is_closed=True, created__gte=time_interval)
    closed_tickets_on_interval = closed_ticket_records.count()

    # Get default timezone of system (for Windows)
    time_zone = tzlocal.get_localzone().zone
    default_time_zone = pytz.timezone(time_zone)

    # Get default timezone and time
    time_now = current_time.strftime(' %H:%M %p')
    time_zone_with_time = time_zone + time_now

    # Get current date of system
    dt = datetime.now(pytz.timezone(time_zone))
    current_date = dt.strftime('%a, %d %b %Y')
    
    context = {'subjects': subjects, 'tickets': tickets, 'ticket_comments': ticket_comments, 
               'ticket_count': ticket_count, 'default_time_zone': default_time_zone, 
               'time_zone_with_time': time_zone_with_time, 'current_date': current_date,
               'open_ticket_count': open_ticket_count, 'in_progress_ticket_count': in_progress_ticket_count,
               'resolved_ticket_count': resolved_ticket_count, 'closed_ticket_count': closed_ticket_count,
               'time_interval': time_interval, 'open_tickets_on_interval': open_tickets_on_interval,
               'in_progress_tickets_on_interval': in_progress_tickets_on_interval,
               'resolved_tickets_on_interval': resolved_tickets_on_interval,
               'closed_tickets_on_interval': resolved_tickets_on_interval,
               'open_ticket_per_day': open_ticket_per_day, 'open_ticket_per_week': open_ticket_per_week,
               'open_ticket_per_month': open_ticket_per_month, 'open_ticket_per_year': open_ticket_per_year,
               'registered_users_per_day': registered_users_per_day}
    return render(request, 'base/dashboard.html', context)


@login_required(login_url='staff_login')
def pivot_dashboard(request):
    return render(request, 'base/pivot_dashboard.html')


def pivot_data(request):
    dataset = Ticket.objects.all()
    data = serializers.serialize('json', dataset)
    # return JsonResponse(data, safe=False)

    # # Initialize PyWebDataRocks pivot table package
    # webdatarocks_instance = webdatarocks.Pivot()

    # # Set the data source for the pivot table
    # webdatarocks_instance.set_data_source({
    # "dataSource": rows,
    # "dataSourceType": "json",
    # "filename": "yourfilename.json"
    # })

    # # Render the pivot table
    # webdatarocks_instance.render()


    file_path = os.path.join(settings.STATIC_ROOT, 'salaries-by-college-major.csv')
    # filepath = "QHelpDesk/json file/dbfile.json"
    
    with open(file_path, 'w') as f:
        json.dump(data, f)

        f.close()
    return render(request, 'base/pivot_dashboard.html')

    
@login_required(login_url='staff_login')    
def fetch_data(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM helpdesk_ticket")
        data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
    rows = []
    for row in data:
        rows.append(dict(zip(columns, row)))
    # return JsonResponse(rows, safe=False)

    # file_path = os.path.join(settings.STATIC_ROOT, 'salaries-by-college-major.csv')

    # with open(file_path, 'w') as f:
    #     json.dump(rows, f)

    #     f.close()
    context = {'jsonData': rows}
    print(context)
    return render(request, 'base/pivot_dashboard.html', context=context)


# class MyLoginView(LoginView):
#     template_name = 'login.html'

#     def form_valid(self, form):
#         response = super().form_valid(form)
#         self.request.user.set_online()
#         return response

# class MyLogoutView(LogoutView):
#     next_page = reverse_lazy('login')

#     @method_decorator(login_required)
#     def dispatch(self, request, *args, **kwargs):
#         self.request.user.set_offline()
#         return super().dispatch(request, *args, **kwargs)

