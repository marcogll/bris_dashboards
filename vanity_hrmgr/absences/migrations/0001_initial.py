from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Absence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('tipo', models.CharField(choices=[('injustificada', 'Injustificada'), ('enfermedad', 'Enfermedad'), ('suspension', 'Suspensión'), ('retardo', 'Retardo'), ('permiso_sin_goce', 'Permiso sin goce'), ('otro', 'Otro')], max_length=30)),
                ('motivo', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'absences',
                'ordering': ['-fecha', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AbsenceAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('create', 'Creado'), ('update', 'Actualizado'), ('delete', 'Eliminado')], max_length=20)),
                ('field_changed', models.CharField(blank=True, max_length=50)),
                ('old_value', models.TextField(blank=True)),
                ('new_value', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'absence_audits',
                'ordering': ['-created_at'],
            },
        ),
    ]