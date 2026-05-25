import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('employees', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Request',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('vacacion', 'Vacación'), ('permiso', 'Permiso')], max_length=20)),
                ('fecha_inicio', models.DateField()),
                ('fecha_fin', models.DateField()),
                ('estatus', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado')], default='pendiente', max_length=20)),
                ('observaciones_sistema', models.TextField(blank=True)),
                ('comentario_admin', models.TextField(blank=True)),
                ('fuera_de_condiciones', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('empleado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', to='employees.employee')),
            ],
            options={
                'db_table': 'requests',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RequestComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contenido', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='employees.user')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='hr_requests.request')),
            ],
            options={
                'db_table': 'request_comments',
                'ordering': ['created_at'],
            },
        ),
    ]