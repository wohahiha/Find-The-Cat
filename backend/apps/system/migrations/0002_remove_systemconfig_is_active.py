from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("configs", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="systemconfig",
            name="is_active",
        ),
    ]

