from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contests", "0011_alter_contestannouncement_summary"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="registration_end_time",
            field=models.DateTimeField(blank=True, null=True, verbose_name="报名截止时间"),
        ),
        migrations.AddField(
            model_name="contest",
            name="registration_start_time",
            field=models.DateTimeField(blank=True, null=True, verbose_name="报名开始时间"),
        ),
    ]
