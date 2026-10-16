from django import forms


class ResponseForm(forms.Form):
    session_item = forms.UUIDField()
    choice = forms.UUIDField()
    hint_used = forms.BooleanField(required=False)
