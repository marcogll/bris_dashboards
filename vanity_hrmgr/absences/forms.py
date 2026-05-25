"""Formularios Django para registro de inasistencias."""

from django import forms
from .models import Absence
from employees.models import Employee, Branch


class AbsenceForm(forms.ModelForm):
    """Formulario de registro de inasistencia con filtros por sucursal.

    Para managers, limita las opciones de sucursal y empleado
    a las sucursales que tienen asignadas.
    """

    class Meta:
        model = Absence
        fields = ('empleado', 'fecha', 'sucursal', 'tipo', 'motivo')
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'empleado': forms.Select(attrs={'class': 'form-select'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.role == 'manager':
            branches = user.branch_set.all()
            self.fields['sucursal'].queryset = branches
            Employee.objects.filter(branch__in=branches).order_by('id')
            self.fields['empleado'].queryset = Employee.objects.filter(branch__in=branches)