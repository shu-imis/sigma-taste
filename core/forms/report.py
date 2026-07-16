"""Content report and steward decision forms."""

from django import forms

from core.models import ContentReport


class ContentReportForm(forms.Form):
    """Member-submitted content report form."""

    reason = forms.ChoiceField(choices=ContentReport.REASON_CHOICES, label='Report reason')
    details = forms.CharField(
        required=False,
        max_length=500,
        label='Report details (optional)',
        widget=forms.Textarea(attrs={'rows': 2}),
    )


class ContentReportResolveForm(forms.Form):
    """Steward action form for pending content reports."""

    action = forms.ChoiceField(
        choices=(
            (ContentReport.STATUS_RESOLVED, 'Resolve report'),
            (ContentReport.STATUS_DISMISSED, 'Dismiss report'),
        ),
        label='Action',
    )
    resolution_note = forms.CharField(
        required=False,
        max_length=500,
        label='Resolution note (optional)',
        widget=forms.Textarea(attrs={'rows': 2}),
    )
