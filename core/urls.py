from django.urls import path
from . import views

urlpatterns = [

    # Home
    path('', views.home, name='home'),

    # Common Login & Logout
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Registration (separate)
    path('register/parent/', views.parent_register, name='parent_register'),
    path('register/hospital/', views.hospital_register, name='hospital_register'),

    # Dashboards
    path('parent/dashboard/', views.parent_dashboard, name='parent_dashboard'),
    path('hospital/dashboard/', views.hospital_dashboard, name='hospital_dashboard'),

    # Admin
    path('system-admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('system-admin/toggle-hospital/<int:id>/',views.toggle_hospital_approval,name='toggle_hospital'),

    path('parent/add-child/', views.add_child, name='add_child'),
    path('parent/book-appointment/', views.book_appointment, name='book_appointment'),
    path('parent/reminders/', views.my_reminders, name='my_reminders'),

    path('hospital/appointments/', views.hospital_appointments, name='hospital_appointments'),
    path('hospital/update-appointment/<int:id>/',views.update_appointment_status,name='update_appointment'),

    path('parent/edit-child/<int:id>/', views.edit_child, name='edit_child'),
    path('parent/delete-child/<int:id>/', views.delete_child, name='delete_child'),

    path('parent/profile/', views.parent_profile, name='parent_profile'),
    path('parent/edit-profile/', views.edit_parent_profile, name='edit_parent_profile'),

    path('parent/all-appointments/', views.all_appointments, name='all_appointments'),

    path('hospital/add-vaccine/', views.add_vaccine, name='add_vaccine'),
    path('hospital/delete-appointment/<int:id>/',views.delete_appointment,name='delete_appointment'),
    path('hospital/all-records/', views.all_patient_records, name='all_patient_records'),

    path('system-admin/appointments/', views.admin_appointments, name='admin_appointments'),
    path('system-admin/edit-parent/<int:id>/',views.edit_parent_admin,name='edit_parent_admin'),
    path('system-admin/delete-parent/<int:id>/',views.delete_parent_admin,name='delete_parent_admin'),

]