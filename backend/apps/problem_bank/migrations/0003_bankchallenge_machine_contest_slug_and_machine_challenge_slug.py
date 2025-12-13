from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("problem_bank", "0002_rename_problem_ba_challen_9ce2a9_idx_problem_ban_challen_d5970b_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankchallenge",
            name="machine_challenge_slug",
            field=models.SlugField(
                blank=True,
                default="",
                help_text="与靶机比赛对应的题目 slug",
                max_length=200,
                verbose_name="靶机题目标识",
            ),
        ),
        migrations.AddField(
            model_name="bankchallenge",
            name="machine_contest_slug",
            field=models.SlugField(
                blank=True,
                default="",
                help_text="如需复用比赛靶机，填入已存在的比赛 slug",
                max_length=200,
                verbose_name="靶机比赛标识",
            ),
        ),
    ]
