from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_alter_emailverificationcode_code_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mailaccount",
            name="host",
            field=models.CharField(max_length=120, verbose_name="SMTP 主机"),
        ),
    ]
