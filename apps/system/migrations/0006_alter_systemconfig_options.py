from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("configs", "0005_alter_systemconfig_options"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="systemconfig",
            options={
                "ordering": ["key"],
                "verbose_name": "SYSTEM",
                "verbose_name_plural": "SYSTEM",
            },
        ),
    ]
