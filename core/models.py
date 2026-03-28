from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ('PARENT', 'Parent'),
        ('HOSPITAL', 'Hospital'),
        ('ADMIN', 'Admin'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='parent_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Child(models.Model):
    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'PARENT'}
    )
    name = models.CharField(max_length=100)
    dob = models.DateField()
    gender = models.CharField(max_length=10)
    blood_group = models.CharField(max_length=5)

    def __str__(self):
        return self.name


class Hospital(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'HOSPITAL'}
    )
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class Vaccine(models.Model):
    AGE_UNIT_WEEK = 'weeks'
    AGE_UNIT_MONTH = 'months'
    AGE_UNIT_YEAR = 'years'
    AGE_UNIT_CHOICES = (
        (AGE_UNIT_WEEK, 'Weeks'),
        (AGE_UNIT_MONTH, 'Months'),
        (AGE_UNIT_YEAR, 'Years'),
    )

    name = models.CharField(max_length=100)
    description = models.TextField()
    recommended_age_value = models.PositiveIntegerField()
    recommended_age_unit = models.CharField(
        max_length=10,
        choices=AGE_UNIT_CHOICES,
        default=AGE_UNIT_MONTH
    )

    @property
    def recommended_age(self):
        return f"{self.recommended_age_value} {self.recommended_age_unit}"

    def __str__(self):
        return self.name


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    )

    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE)
    appointment_date = models.DateField()
    result_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.child.name} - {self.vaccine.name}"


class Reminder(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE)
    reminder_date = models.DateField()

    def __str__(self):
        return f"Reminder for {self.child.name} - {self.vaccine.name}"


class VaccineCompletion(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE)
    completed_date = models.DateField()
    marked_by_parent = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['child', 'vaccine'],
                name='unique_vaccine_completion_per_child'
            )
        ]

    def __str__(self):
        return f"{self.child.name} - {self.vaccine.name} completed"
