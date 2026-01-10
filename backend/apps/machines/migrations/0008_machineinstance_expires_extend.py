from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('machines', '0007_alter_challengemachineconfig_port_cache_ttl'),
    ]

    operations = [
        migrations.AddField(
            model_name='machineinstance',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='过期时间'),
        ),
        migrations.AddField(
            model_name='machineinstance',
            name='extend_count',
            field=models.PositiveIntegerField(default=0, verbose_name='延时次数'),
        ),
    ]
