from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0009_contestparticipant_is_valid"),
    ]

    operations = [
        migrations.AddField(
            model_name="contestannouncement",
            name="summary",
            field=models.CharField(default="", max_length=500, verbose_name="公告摘要"),
        ),
    ]

