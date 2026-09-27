from django import forms

from apps.accounts.forms import INPUT_CLASS
from apps.accounts.models import User
from apps.classrooms.models import Classroom


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ("code", "name")
        widgets = {
            "code": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
        }

    def clean_code(self):
        return self.cleaned_data["code"].strip()

    def clean_name(self):
        return self.cleaned_data["name"].strip()


class AssignTeacherForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="Unassigned",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = User.objects.filter(
            role=User.Role.TEACHER,
            is_active=True,
        ).order_by("last_name", "first_name", "username")


class AddStudentForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, classroom=None, **kwargs):
        super().__init__(*args, **kwargs)
        current_ids = []
        if classroom is not None:
            current_ids = classroom.student_memberships.filter(
                left_at__isnull=True
            ).values_list("student_id", flat=True)
        self.fields["student"].queryset = User.objects.filter(
            role=User.Role.STUDENT,
            is_active=True,
        ).exclude(pk__in=current_ids).order_by("last_name", "first_name", "username")


class ReasonForm(forms.Form):
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise forms.ValidationError("A reason is required.")
        return reason
