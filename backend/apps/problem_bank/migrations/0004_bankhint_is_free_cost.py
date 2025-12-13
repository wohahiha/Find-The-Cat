from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("problem_bank", "0003_bankchallenge_machine_contest_slug_and_machine_challenge_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankhint",
            name="cost",
            field=models.PositiveIntegerField(default=0, verbose_name="扣分成本"),
        ),
        migrations.AddField(
            model_name="bankhint",
            name="is_free",
            field=models.BooleanField(default=True, verbose_name="是否免费"),
        ),
    ]
