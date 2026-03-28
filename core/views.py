from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import admin_only
from .forms import ChildForm
from .models import (
    Appointment,
    Child,
    Hospital,
    Reminder,
    User,
    Vaccine,
    VaccineCompletion,
)


UPCOMING_WINDOW_DAYS = 30


def add_months(source_date, months):
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    month_lengths = [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ]
    day = min(source_date.day, month_lengths[month - 1])
    return date(year, month, day)


def get_vaccine_due_date(child, vaccine):
    if vaccine.recommended_age_unit == Vaccine.AGE_UNIT_WEEK:
        return child.dob + timedelta(weeks=vaccine.recommended_age_value)
    if vaccine.recommended_age_unit == Vaccine.AGE_UNIT_YEAR:
        return add_months(child.dob, vaccine.recommended_age_value * 12)
    return add_months(child.dob, vaccine.recommended_age_value)


def get_child_age_display(child):
    today = timezone.now().date()
    total_days = max((today - child.dob).days, 0)

    if total_days < 30:
        weeks = total_days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''}"

    total_months = total_days // 30
    if total_months < 12:
        return f"{total_months} month{'s' if total_months != 1 else ''}"

    years = total_months // 12
    months = total_months % 12
    if months:
        return f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}"
    return f"{years} year{'s' if years != 1 else ''}"


def get_child_vaccination_chart(child):
    today = timezone.now().date()
    upcoming_cutoff = today + timedelta(days=UPCOMING_WINDOW_DAYS)

    vaccines = Vaccine.objects.order_by('name')
    appointments = Appointment.objects.select_related(
        'hospital__user', 'vaccine'
    ).filter(child=child).order_by('appointment_date', 'id')

    appointments_by_vaccine = defaultdict(list)
    for appointment in appointments:
        appointments_by_vaccine[appointment.vaccine_id].append(appointment)

    parent_completions = {
        completion.vaccine_id: completion
        for completion in VaccineCompletion.objects.filter(child=child)
    }

    due_vaccines = []
    upcoming_vaccines = []
    booked_vaccines = []
    completed_vaccines = []

    for vaccine in vaccines:
        due_date = get_vaccine_due_date(child, vaccine)
        vaccine_appointments = appointments_by_vaccine.get(vaccine.id, [])
        parent_completion = parent_completions.get(vaccine.id)
        completed_appointment = next(
            (appointment for appointment in reversed(vaccine_appointments)
             if appointment.status == 'COMPLETED'),
            None,
        )
        booked_appointment = next(
            (appointment for appointment in vaccine_appointments
             if appointment.status in ['PENDING', 'APPROVED']
             and appointment.appointment_date >= today),
            None,
        )

        chart_item = {
            'vaccine': vaccine,
            'due_date': due_date,
            'recommended_age': vaccine.recommended_age,
            'booked_appointment': booked_appointment,
            'completed_appointment': completed_appointment,
            'parent_completion': parent_completion,
            'is_due': due_date <= today,
        }

        if completed_appointment or parent_completion:
            chart_item['status'] = 'completed'
            chart_item['completed_date'] = (
                completed_appointment.appointment_date
                if completed_appointment else
                parent_completion.completed_date
            )
            chart_item['completed_source'] = (
                'Hospital record'
                if completed_appointment else
                'Marked completed by parent'
            )
            completed_vaccines.append(chart_item)
        elif booked_appointment:
            chart_item['status'] = 'booked'
            booked_vaccines.append(chart_item)
        elif due_date <= today:
            chart_item['status'] = 'due'
            due_vaccines.append(chart_item)
        elif due_date <= upcoming_cutoff:
            chart_item['status'] = 'upcoming'
            upcoming_vaccines.append(chart_item)

    return {
        'due_vaccines': sorted(due_vaccines, key=lambda item: item['due_date']),
        'upcoming_vaccines': sorted(upcoming_vaccines, key=lambda item: item['due_date']),
        'booked_vaccines': sorted(
            booked_vaccines,
            key=lambda item: item['booked_appointment'].appointment_date
        ),
        'completed_vaccines': sorted(
            completed_vaccines,
            key=lambda item: item['completed_date'],
            reverse=True
        ),
        'today': today,
    }


def sync_child_reminders(child):
    today = timezone.now().date()
    chart = get_child_vaccination_chart(child)
    desired_dates = {}

    for item in chart['upcoming_vaccines']:
        desired_dates[item['vaccine'].id] = item['due_date'] - timedelta(days=2)

    for item in chart['booked_vaccines']:
        desired_dates[item['vaccine'].id] = max(
            today,
            item['booked_appointment'].appointment_date - timedelta(days=2)
        )

    existing_reminders = list(Reminder.objects.filter(child=child))
    existing_vaccine_ids = {reminder.vaccine_id for reminder in existing_reminders}

    for reminder in existing_reminders:
        desired_date = desired_dates.get(reminder.vaccine_id)
        if desired_date is None:
            reminder.delete()
        elif reminder.reminder_date != desired_date:
            reminder.reminder_date = desired_date
            reminder.save(update_fields=['reminder_date'])

    for vaccine_id, reminder_date in desired_dates.items():
        if vaccine_id not in existing_vaccine_ids:
            Reminder.objects.create(
                child=child,
                vaccine_id=vaccine_id,
                reminder_date=reminder_date
            )


def build_reminder_rows(reminders):
    rows = []
    for reminder in reminders:
        appointment = Appointment.objects.filter(
            child=reminder.child,
            vaccine=reminder.vaccine,
            status__in=['PENDING', 'APPROVED']
        ).order_by('appointment_date', 'id').first()

        if appointment:
            scheduled_or_due_date = appointment.appointment_date
            date_context = 'Appointment date'
        else:
            scheduled_or_due_date = get_vaccine_due_date(reminder.child, reminder.vaccine)
            date_context = 'Upcoming vaccine date'

        rows.append({
            'child': reminder.child,
            'vaccine': reminder.vaccine,
            'reminder_date': reminder.reminder_date,
            'scheduled_or_due_date': scheduled_or_due_date,
            'date_context': date_context,
        })
    return rows


@admin_only
def delete_parent_admin(request, id):
    parent = get_object_or_404(User, id=id, role='PARENT')
    if request.method == 'POST':
        parent.delete()
        return redirect('admin_dashboard')
    return render(request, 'system-admin/confirm_delete.html', {'parent': parent})


@admin_only
def edit_parent_admin(request, id):
    parent = get_object_or_404(User, id=id, role='PARENT')
    if request.method == 'POST':
        parent.username = request.POST['username']
        parent.phone = request.POST['phone']
        parent.address = request.POST['address']
        parent.save()
        return redirect('admin_dashboard')
    return render(request, 'system-admin/edit_parent.html', {'parent': parent})


@login_required
def delete_appointment(request, id):
    hospital = Hospital.objects.get(user=request.user)
    appointment = get_object_or_404(Appointment, id=id, hospital=hospital)
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
            recommended_age_value=request.POST['recommended_age_value'],
            recommended_age_unit=request.POST['recommended_age_unit'],
        )
        return redirect('hospital_dashboard')

    return render(request, 'hospital/add_vaccine.html')


@login_required
def edit_vaccine(request, id):
    if request.user.role != 'HOSPITAL':
        return redirect('login')

    vaccine = get_object_or_404(Vaccine, id=id)
    if request.method == 'POST':
        vaccine.name = request.POST['name']
        vaccine.description = request.POST['description']
        vaccine.recommended_age_value = request.POST['recommended_age_value']
        vaccine.recommended_age_unit = request.POST['recommended_age_unit']
        vaccine.save()
        return redirect('hospital_dashboard')

    return render(request, 'hospital/edit_vaccine.html', {'vaccine': vaccine})


@login_required
def delete_vaccine(request, id):
    if request.user.role != 'HOSPITAL':
        return redirect('login')

    vaccine = get_object_or_404(Vaccine, id=id)
    appointment_count = Appointment.objects.filter(vaccine=vaccine).count()
    reminder_count = Reminder.objects.filter(vaccine=vaccine).count()

    if request.method == 'POST':
        vaccine.delete()
        return redirect('hospital_dashboard')

    return render(request, 'hospital/delete_vaccine.html', {
        'vaccine': vaccine,
        'appointment_count': appointment_count,
        'reminder_count': reminder_count,
    })


@login_required
def all_appointments(request):
    appointments = Appointment.objects.select_related(
        'child', 'hospital__user', 'vaccine'
    ).filter(
        child__parent=request.user
    ).order_by('-appointment_date')
    return render(request, 'parent/all_appointments.html', {'appointments': appointments})


@login_required
def mark_vaccine_completed(request, child_id, vaccine_id):
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    vaccine = get_object_or_404(Vaccine, id=vaccine_id)

    if request.method == 'POST':
        completion, created = VaccineCompletion.objects.get_or_create(
            child=child,
            vaccine=vaccine,
            defaults={'completed_date': timezone.now().date()}
        )
        if not created and not completion.completed_date:
            completion.completed_date = timezone.now().date()
            completion.save(update_fields=['completed_date'])
        Reminder.objects.filter(child=child, vaccine=vaccine).delete()

    return redirect('child_vaccination_chart', id=child.id)


@login_required
def child_vaccination_chart(request, id):
    child = get_object_or_404(Child, id=id, parent=request.user)
    sync_child_reminders(child)
    chart = get_child_vaccination_chart(child)
    return render(request, 'parent/vaccination_chart.html', {
        'child': child,
        **chart,
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
    return render(request, 'parent/profile.html', {'children_count': children_count})


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
    return render(request, 'parent/edit_child.html', {'form': form})


@login_required
def delete_child(request, id):
    child = get_object_or_404(Child, id=id, parent=request.user)
    child.delete()
    return redirect('parent_dashboard')


@login_required
def my_reminders(request):
    children = Child.objects.filter(parent=request.user)
    for child in children:
        sync_child_reminders(child)

    reminders = Reminder.objects.select_related('child', 'vaccine').filter(
        child__parent=request.user
    ).order_by('reminder_date', 'child__name', 'vaccine__name')

    return render(request, 'parent/reminders.html', {
        'reminders': build_reminder_rows(reminders)
    })


@login_required
def book_appointment(request):
    hospitals = Hospital.objects.filter(approved=True)
    vaccines = Vaccine.objects.all()
    children = Child.objects.filter(parent=request.user)
    selected_child_id = request.GET.get('child', '')
    selected_vaccine_id = request.GET.get('vaccine', '')
    suggested_date = request.GET.get('due_date', '')
    min_appointment_date = date.today().isoformat()

    if request.method == 'POST':
        raw_appointment_date = request.POST.get('date', '')
        try:
            appointment_date = datetime.strptime(raw_appointment_date, "%Y-%m-%d").date()
        except ValueError:
            return render(request, 'parent/book_appointment.html', {
                'error': 'Please choose a valid appointment date.',
                'hospitals': hospitals,
                'vaccines': vaccines,
                'children': children,
                'selected_child_id': request.POST.get('child', ''),
                'selected_vaccine_id': request.POST.get('vaccine', ''),
                'suggested_date': raw_appointment_date,
                'min_appointment_date': min_appointment_date,
            })

        if appointment_date < date.today():
            return render(request, 'parent/book_appointment.html', {
                'error': 'You cannot book appointment in the past',
                'hospitals': hospitals,
                'vaccines': vaccines,
                'children': children,
                'selected_child_id': request.POST.get('child', ''),
                'selected_vaccine_id': request.POST.get('vaccine', ''),
                'suggested_date': raw_appointment_date,
                'min_appointment_date': min_appointment_date,
            })

        appointment = Appointment.objects.create(
            child_id=request.POST['child'],
            hospital_id=request.POST['hospital'],
            vaccine_id=request.POST['vaccine'],
            appointment_date=appointment_date,
        )

        Reminder.objects.filter(child=appointment.child, vaccine=appointment.vaccine).delete()
        Reminder.objects.create(
            child=appointment.child,
            vaccine=appointment.vaccine,
            reminder_date=max(date.today(), appointment_date - timedelta(days=2))
        )

        return redirect('parent_dashboard')

    return render(request, 'parent/book_appointment.html', {
        'hospitals': hospitals,
        'vaccines': vaccines,
        'children': children,
        'selected_child_id': str(selected_child_id),
        'selected_vaccine_id': str(selected_vaccine_id),
        'suggested_date': suggested_date,
        'min_appointment_date': min_appointment_date,
    })


@login_required
def update_appointment_status(request, id):
    appointment = Appointment.objects.get(id=id)
    appointment.status = request.POST['status']
    appointment.result_notes = request.POST['notes']
    appointment.save()

    if appointment.status == 'COMPLETED':
        Reminder.objects.filter(child=appointment.child, vaccine=appointment.vaccine).delete()

    return redirect(request.POST.get('next') or 'hospital_appointments')


@login_required
def hospital_appointments(request):
    hospital = Hospital.objects.get(user=request.user)
    status_filter = request.GET.get('status', '')
    booking_order = request.GET.get('booking_order', 'newest')

    appointments = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(hospital=hospital)

    if status_filter:
        appointments = appointments.filter(status=status_filter)

    if booking_order == 'oldest':
        appointments = appointments.order_by('created_at', 'id')
    else:
        appointments = appointments.order_by('-created_at', '-id')

    return render(request, 'hospital/appointments.html', {
        'appointments': appointments,
        'status_filter': status_filter,
        'booking_order': booking_order,
    })


@login_required
def add_child(request):
    if request.method == 'POST':
        Child.objects.create(
            parent=request.user,
            name=request.POST['name'],
            dob=request.POST['dob'],
            gender=request.POST['gender'],
            blood_group=request.POST['blood_group'],
        )
        return redirect('parent_dashboard')

    return render(request, 'parent/add_child.html')


@admin_only
def admin_appointments(request):
    appointments = Appointment.objects.select_related(
        'child__parent', 'hospital__user', 'vaccine'
    ).order_by('-appointment_date', '-id')
    return render(request, 'system-admin/appointments.html', {'appointments': appointments})


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
    parents = User.objects.filter(role='PARENT').prefetch_related(Prefetch('child_set'))

    return render(request, 'system-admin/dashboard.html', {
        'hospitals': hospitals,
        'appointments': appointments,
        'parents': parents,
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
            if user.role == 'PARENT':
                return redirect('parent_dashboard')
            if user.role == 'HOSPITAL':
                hospital = Hospital.objects.filter(user=user).first()
                if hospital and hospital.approved:
                    return redirect('hospital_dashboard')
                logout(request)
                return render(request, 'login.html', {'error': 'Hospital not approved by admin'})

        return render(request, 'login.html', {'error': 'Invalid username or password'})

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
    child_summaries = []

    for child in children:
        sync_child_reminders(child)
        chart = get_child_vaccination_chart(child)
        child_summaries.append({
            'child': child,
            'age_display': get_child_age_display(child),
            'due_count': len(chart['due_vaccines']),
            'upcoming_count': len(chart['upcoming_vaccines']),
            'booked_count': len(chart['booked_vaccines']),
        })

    appointments = Appointment.objects.select_related(
        'child', 'hospital__user', 'vaccine'
    ).filter(
        child__parent=request.user
    ).order_by('-appointment_date')[:5]

    return render(request, 'parent/dashboard.html', {
        'children': children,
        'child_summaries': child_summaries,
        'appointments': appointments,
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
    vaccines = Vaccine.objects.order_by('name')
    latest_appointments = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(
        hospital=hospital
    ).order_by('-appointment_date', '-id')[:10]
    completed_records = Appointment.objects.select_related(
        'child__parent', 'vaccine'
    ).filter(
        hospital=hospital,
        status='COMPLETED'
    ).order_by('-appointment_date', '-id')[:10]

    return render(request, 'hospital/dashboard.html', {
        'appointments': latest_appointments,
        'completed_records': completed_records,
        'vaccines': vaccines,
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
    return render(request, 'hospital/all_patient_records.html', {'records': records})


def user_logout(request):
    logout(request)
    return redirect('home')
