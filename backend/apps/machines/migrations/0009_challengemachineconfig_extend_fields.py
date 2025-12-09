from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('machines', '0008_machineinstance_expires_extend'),
    ]

    operations = [
        migrations.AddField(
            model_name='challengemachineconfig',
            name='extend_minutes_default',
            field=models.PositiveIntegerField(default=30, help_text='用户点击延时时追加的时间（分钟）', verbose_name='单次延时分钟数'),
        ),
        migrations.AddField(
            model_name='challengemachineconfig',
            name='extend_max_times',
            field=models.IntegerField(default=-1, help_text='-1 表示不限制，0 表示禁止延时，正整数为允许的最大延时次数', verbose_name='单实例最大延时次数（-1 不限）'),
        ),
        migrations.AddField(
            model_name='challengemachineconfig',
            name='extend_threshold_minutes',
            field=models.IntegerField(default=15, help_text='仅当剩余时间小于等于该值时允许延时，0 或负数表示不检查阈值', verbose_name='允许延时的剩余时间阈值（分钟）'),
        ),
    ]
