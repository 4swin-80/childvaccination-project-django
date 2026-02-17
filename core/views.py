from datetime import datetime, timedelta, date
from .decorators import admin_only
from .forms import ChildForm
from django.db.models import F
from django.utils import timezone
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import User, Hospital, Appointment, Child, Vaccine, Reminder



@admin_only
def delete_parent_admin(request, id):
    parent = get_object_or_404(User, id=id, role='PARENT')

    if request.method == 'POST':
        parent.delete()
        return redirect('admin_dashboard')

    return render(request, 'system-admin/confirm_delete.html', {
        'parent': parent
    })



@admin_only
def edit_parent_admin(request, id):
    parent = get_object_or_404(User, id=id, role='PARENT')

    if request.method == 'POST':
        parent.username = request.POST['username']
        parent.phone = request.POST['phone']
        parent.address = request.POST['address']
        parent.save()
        return redirect('admin_dashboard')

    return render(request, 'system-admin/edit_parent.html', {
        'parent': parent
    })



@login_required
def delete_appointment(request, id):
    hospital = Hospital.objects.get(user=request.user)

    appointment = get_object_or_404(
        Appointment,
        id=id,
        hospital=hospital
    )

    appointment.delete()
    return redirect('hospital_appointments')



@login_required
def add_vaccine(request):
    if request.user.role != 'HOSPITAL':
        return redirect('login')

    if request.method == 'POST':
        Vaccine.objects.create(
            name=request.POST['name'],
            description=request.POST['description'],
            recommended_age=request.POST['recommended_age']
        )
        return redirect('hospital_dashboard')

    return render(request, 'hospital/add_vaccine.html')



@login_required
def all_appointments(request):
    appointments = Appointment.objects.select_related(
        'child', 'hospital__user', 'vaccine'
    ).filter(
        child__parent=request.user
    ).order_by('-appointment_date')

    return render(request, 'parent/all_appointments.html', {
        'appointments': appointments
    })



@login_required
def edit_parent_profile(request):
    if request.user.role != 'PARENT':
        return redirect('login')

    if request.method == 'POST':
        request.user.phone = request.POST['phone']
        request.user.address = request.POST['address']
        request.user.save()
        return redirect('parent_profile')

    return render(request, 'parent/edit_profile.html')



@login_required
def parent_profile(request):
    if request.user.role != 'PARENT':
        return redirect('login')

    children_count = Child.objects.filter(parent=request.user).count()

    return render(request, 'parent/profile.html', {
        'children_count': children_count
    })


@login_required
def edit_child(request, id):
    child = get_object_or_404(Child, id=id, parent=request.user)

    if request.method == 'POST':
        form = ChildForm(request.POST, instance=child)
        if form.is_valid():
            form.save()
            return redirect('parent_dashboard')
    else:
        form = ChildForm(instance=child)

    return render(request, 'parent/edit_child.html', {
        'form': form
    })



@login_required
def delete_child(request, id):
    child = get_object_or_404(Child, id=id, parent=request.user)
    child.delete()
    return redirect('parent_dashboard')



@login_required
def my_reminders(request):
    today = timezone.now().date()

    reminders = Reminder.objects.select_related(
        'child', 'vaccine'
    ).filter(
        child__parent=request.user,
        child__appointment__vaccine=F('vaccine'),  # ✅ correct
        child__appointment__status__in=['PENDING', 'APPROVED'],
        child__appointment__appointment_date__gte=today
    ).distinct().order_by('reminder_date')

    return render(request, 'parent/reminders.html', {
        'reminders': reminders
    })




@login_required
def book_appointment(request):
    hospitals = Hospital.objects.filter(approved=True)
    vaccines = Vaccine.objects.all()
    children = Child.objects.filter(parent=request.user)

    if request.method == 'POST':

        
        appointment_date = datetime.strptime(
            request.POST['date'],
            "%Y-%m-%d"
        ).date()

    
        if appointment_date < date.today():
            return render(request, 'parent/book_appointment.html', {
                'error': 'You cannot book appointment in the past',
                'hospitals': hospitals,
                'vaccines': vaccines,
                'children': children
            })

        appointment = Appointment.objects.create(
            child_id=request.POST['child'],
            hospital_id=request.POST['hospital'],
            vaccine_id=request.POST['vaccine'],
            appointment_date=appointment_date
        )

        Reminder.objects.create(
            child=appointment.child,
            vaccine=appointment.vaccine,
            reminder_date=appointment_date - timedelta(days=2)
        )

        return redirect('parent_dashboard')

    return render(request, 'parent/book_appointment.html', {
        'hospitals': hospitals,
        'vaccines': vaccines,
        'children': children
    })


@login_required
def update_appointment_status(request, id):
    appointment = Appointment.objects.get(id=id)

    appointment.status = request.POST['status']
    appointment.result_notes = request.POST['notes']
    appointment.save()

    # 🔥 If completed → delete reminder
    if appointment.status == 'COMPLETED':
        Reminder.objects.filter(
            child=appointment.child,
            vaccine=appointment.vaccine
        ).delete()

    return redirect('hospital_appointments')



@login_required
def hospital_appointments(request):
    hospital = Hospital.objects.get(user=request.user)

    appointments = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(
        hospital=hospital
    ).order_by('-appointment_date', '-id')  

    return render(request, 'hospital/appointments.html', {
        'appointments': appointments
    })




@login_required
def add_child(request):
    if request.method == 'POST':
        Child.objects.create(
            parent=request.user,
            name=request.POST['name'],
            dob=request.POST['dob'],
            gender=request.POST['gender'],
            blood_group=request.POST['blood_group']
        )
        return redirect('parent_dashboard')

    return render(request, 'parent/add_child.html')


@admin_only
def admin_appointments(request):
    appointments = Appointment.objects.select_related(
        'child__parent', 'hospital__user', 'vaccine'
    ).order_by('-appointment_date', '-id')

    return render(request, 'system-admin/appointments.html', {
        'appointments': appointments
    })



@admin_only
def toggle_hospital_approval(request, id):
    hospital = get_object_or_404(Hospital, id=id)
    hospital.approved = not hospital.approved
    hospital.save()
    return redirect('admin_dashboard')


@admin_only
def admin_dashboard(request):
    hospitals = Hospital.objects.all()

    appointments = Appointment.objects.select_related(
        'child__parent', 'hospital__user', 'vaccine'
    ).order_by('-appointment_date', '-id')[:10]

    # 🔥 Get all parents with their children
    parents = User.objects.filter(role='PARENT').prefetch_related(
        Prefetch('child_set')
    )

    return render(request, 'system-admin/dashboard.html', {
        'hospitals': hospitals,
        'appointments': appointments,
        'parents': parents
    })



def user_login(request):
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST['username'],
            password=request.POST['password']
        )

        if user:
            login(request, user)

            if user.role == 'ADMIN':
                return redirect('admin_dashboard')

            elif user.role == 'PARENT':
                return redirect('parent_dashboard')

            elif user.role == 'HOSPITAL':
                hospital = Hospital.objects.filter(user=user).first()
                if hospital and hospital.approved:
                    return redirect('hospital_dashboard')
                else:
                    logout(request)
                    return render(request, 'login.html', {
                        'error': 'Hospital not approved by admin'
                    })

        return render(request, 'login.html', {
            'error': 'Invalid username or password'
        })

    return render(request, 'login.html')




def home(request):
    return render(request, 'home.html')


def parent_register(request):
    if request.method == 'POST':
        User.objects.create_user(
            username=request.POST['username'],
            password=request.POST['password'],
            role='PARENT',
            phone=request.POST['phone'],
            address=request.POST['address'],
            photo=request.FILES.get('photo')
        )
        return redirect('login')

    return render(request, 'parent/register.html')




@login_required
def parent_dashboard(request):
    children = Child.objects.filter(parent=request.user)

    # 🔥 Only latest 5 appointments
    appointments = Appointment.objects.select_related(
        'child', 'hospital__user', 'vaccine'
    ).filter(
        child__parent=request.user
    ).order_by('-appointment_date')[:5]

    return render(request, 'parent/dashboard.html', {
        'children': children,
        'appointments': appointments
    })





def hospital_register(request):
    if request.method == 'POST':
        user = User.objects.create_user(
            username=request.POST['username'],
            password=request.POST['password'],
            role='HOSPITAL',
            phone=request.POST['phone'],
            address=request.POST['address']
        )
        Hospital.objects.create(user=user)
        return redirect('login')

    return render(request, 'hospital/register.html')


@login_required
def hospital_dashboard(request):
    if request.user.role != 'HOSPITAL':
        return redirect('login')

    hospital = Hospital.objects.get(user=request.user)

    
    latest_appointments = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(
        hospital=hospital
    ).order_by('-appointment_date')[:10]

    
    completed_records = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(
        hospital=hospital,
        status='COMPLETED'
    ).order_by('-appointment_date', '-id')[:10]   # ✅ latest 10 only



    return render(request, 'hospital/dashboard.html', {
        'appointments': latest_appointments,
        'completed_records': completed_records
    })


@login_required
def all_patient_records(request):
    if request.user.role != 'HOSPITAL':
        return redirect('login')

    hospital = Hospital.objects.get(user=request.user)

    records = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(
        hospital=hospital,
        status='COMPLETED'
    ).order_by('-appointment_date', '-id')

    return render(request, 'hospital/all_patient_records.html', {
        'records': records
    })



def user_logout(request):
    logout(request)
    return redirect('home')