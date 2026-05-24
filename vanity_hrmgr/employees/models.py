"""Modelos para gestión de empleados, sucursales y auditoría."""

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Modelo de usuario personalizado con roles y autenticación múltiple."""

    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('manager', 'Gerente'),
        ('user', 'Colaborador'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True)
    api_key = models.CharField(max_length=64, blank=True, null=True, unique=True)

    class Meta:
        db_table = 'users'


class Branch(models.Model):
    """Representa una sucursal física de la empresa."""

    DAY_CHOICES = [
        ('lunes', 'Lunes'),
        ('martes', 'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves', 'Jueves'),
        ('viernes', 'Viernes'),
        ('sabado', 'Sábado'),
    ]

    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    calle = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    num_letra = models.CharField(max_length=200, blank=True, help_text='Número en texto')
    colonia = models.CharField(max_length=200, blank=True)
    cp = models.CharField(max_length=10, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    dia_pago = models.CharField(max_length=20, choices=DAY_CHOICES, blank=True)
    link_location = models.URLField(blank=True, help_text='Link de Google Maps')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'

    def __str__(self):
        return self.name

    @property
    def direccion_completa(self):
        parts = [self.calle, self.numero, self.colonia, self.cp, self.ciudad, self.estado]
        return ', '.join(p for p in parts if p)


class Employee(models.Model):
    """Perfil extendido del empleado con datos laborales, personales y evaluación."""

    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('baja', 'Baja'),
    ]

    CONTRACT_CHOICES = [
        ('laboral', 'Laboral'),
    ]

    SKILL_LEVEL_CHOICES = [
        ('basic', 'Básico'),
        ('intermediate', 'Intermedio'),
        ('advanced', 'Avanzado'),
    ]

    RELATION_CHOICES = [
        ('familiar', 'Familiar'),
        ('amigo', 'Amigo'),
        ('vecino', 'Vecino'),
        ('otro', 'Otro'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_number = models.CharField(max_length=50, unique=True)
    n_socio = models.CharField(max_length=50, blank=True, help_text='Número de socio')
    tipo_contrato = models.CharField(max_length=20, choices=CONTRACT_CHOICES, default='laboral')
    fecha_ingreso = models.DateField()
    saldo_vacaciones = models.FloatField(default=0)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='activo')
    rfc = models.CharField(max_length=20, blank=True)
    curp = models.CharField(max_length=20, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    calle = models.CharField(max_length=200, blank=True)
    num_ext = models.CharField(max_length=20, blank=True)
    num_int = models.CharField(max_length=20, blank=True)
    num_text = models.CharField(max_length=200, blank=True, help_text='Número en texto')
    colonia = models.CharField(max_length=200, blank=True)
    cp = models.CharField(max_length=10, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    dia_pago = models.CharField(max_length=20, choices=Branch.DAY_CHOICES, blank=True)
    emergency_contact = models.CharField(max_length=200, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    emergency_relation = models.CharField(max_length=50, choices=RELATION_CHOICES, blank=True)
    ref1_nombre = models.CharField(max_length=200, blank=True)
    ref1_tipo = models.CharField(max_length=50, blank=True)
    ref1_tiempo = models.CharField(max_length=50, blank=True)
    ref1_telefono = models.CharField(max_length=20, blank=True)
    ref2_nombre = models.CharField(max_length=200, blank=True)
    ref2_tipo = models.CharField(max_length=50, blank=True)
    ref2_tiempo = models.CharField(max_length=50, blank=True)
    ref2_telefono = models.CharField(max_length=20, blank=True)
    ref3_nombre = models.CharField(max_length=200, blank=True)
    ref3_tipo = models.CharField(max_length=50, blank=True)
    ref3_tiempo = models.CharField(max_length=50, blank=True)
    ref3_telefono = models.CharField(max_length=20, blank=True)
    ine_front_ref = models.CharField(max_length=500, blank=True, help_text='Referencia archivo INE frente')
    ine_back_ref = models.CharField(max_length=500, blank=True, help_text='Referencia archivo INE reverso')
    consentimiento_ref = models.CharField(max_length=500, blank=True, help_text='Referencia archivo consentimiento')
    skill_level = models.CharField(max_length=20, choices=SKILL_LEVEL_CHOICES, default='basic', help_text='1-5 estrellas')
    service = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    teamwork = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    feedback = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    selfhelp = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    behavior = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    time_attendance = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    availability = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    fecha_registro = models.TextField(blank=True, help_text='Fecha de registro en sistema')
    baja_motivo = models.TextField(blank=True, help_text='Motivo de baja detallado')
    baja_motivo_selector = models.CharField(max_length=100, blank=True, help_text='Motivo genérico de baja')
    fecha_baja = models.DateField(null=True, blank=True, help_text='Fecha de baja del empleado')
    recontratable = models.BooleanField(default=True, help_text='¿Puede ser recontratado?')
    end_term = models.BooleanField(default=False, help_text='Terminación voluntaria')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'

    def __str__(self):
        return f"{self.employee_number} - {self.user.get_full_name() or self.user.username}"

    @property
    def skill_score(self):
        fields = [self.service, self.teamwork, self.feedback, self.selfhelp, self.behavior, self.time_attendance, self.availability]
        values = [float(f) for f in fields if f]
        return round(sum(values) / len(values), 2) if values else 0

    def calcular_antiguedad(self):
        from datetime import date
        if not self.fecha_ingreso:
            return 0
        today = date.today()
        years = today.year - self.fecha_ingreso.year
        if today.month < self.fecha_ingreso.month or (today.month == self.fecha_ingreso.month and today.day < self.fecha_ingreso.day):
            years -= 1
        return max(0, years)

    def get_dias_vacaciones(self):
        years = self.calcular_antiguedad()
        if years < 1:
            return 6
        elif years < 5:
            return 10
        elif years < 10:
            return 14
        elif years < 20:
            return 18
        return 22

    def actualizar_skill_score(self):
        pass


class EmployeeAudit(models.Model):
    """Registro de auditoría para cambios en datos de empleados."""

    ACTION_CHOICES = [
        ('create', 'Creación'),
        ('update', 'Actualización'),
        ('delete', 'Eliminación'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_changed = models.CharField(max_length=100, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audits'