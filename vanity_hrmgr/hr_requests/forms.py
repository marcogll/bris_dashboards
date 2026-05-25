"""Formularios Django para solicitudes de vacaciones y permisos."""

from django import forms
from datetime import date


class RequestForm(forms.Form):
    """Formulario de solicitud de vacaciones o permiso con validación.

    Valida:
    - Tipo de solicitud válido
    - Fechas no vacías y en formato correcto
    - Fecha inicio <= fecha fin
    - Fecha inicio >= hoy (no fechas pasadas)
    - Sanitización de inputs
    """
    TIPO_CHOICES = [
        ('vacacion', 'Vacación'),
        ('permiso', 'Permiso'),
    ]
    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de solicitud',
    )
    fecha_inicio = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha de inicio',
    )
    fecha_fin = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha de fin',
    )
    fuera_de_condiciones = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Enviar fuera de condiciones',
    )

    def clean_fecha_inicio(self):
        fecha_inicio = self.cleaned_data.get('fecha_inicio')
        if fecha_inicio and fecha_inicio < date.today():
            raise forms.ValidationError('No se pueden solicitar fechas pasadas')
        return fecha_inicio

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise forms.ValidationError('La fecha de inicio debe ser anterior o igual a la fecha de fin')
        return cleaned_data