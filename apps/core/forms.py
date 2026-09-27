from django import forms

from apps.accounts.forms import INPUT_CLASS


class OverrideForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    setting_name = forms.ChoiceField(
        choices=(("study_access", "Study Access"), ("posttest_access", "Post-test Access")),
        widget=forms.HiddenInput,
    )
    enabled = forms.BooleanField(required=False, widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={"class": INPUT_CLASS, "rows": 4, "placeholder": "Why is this change needed?"}
        ),
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise forms.ValidationError("A reason is required.")
        return reason
