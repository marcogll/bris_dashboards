import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('absences', '0001_initial'),
        ('employees', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='absence',
            name='empleado',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='absences', to='employees.employee'),
        ),
        migrations.AddField(
            model_name='absence',
            name='registrado_por',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='absence',
            name='sucursal',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='employees.branch'),
        ),
        migrations.AddField(
            model_name='absenceaudit',
            name='absence',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audits', to='absences.absence'),
        ),
        migrations.AddField(
            model_name='absenceaudit',
            name='changed_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]