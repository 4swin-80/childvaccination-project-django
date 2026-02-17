from django.contrib import admin
from .models import User, Child, Hospital, Vaccine, Appointment, Reminder

admin.site.register(User)
admin.site.register(Child)
admin.site.register(Hospital)
admin.site.register(Vaccine)
admin.site.register(Appointment)
admin.site.register(Reminder)