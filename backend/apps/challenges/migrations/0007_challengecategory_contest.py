from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0006_alter_contestannouncement_options"),
        ("challenges", "0006_alter_challenge_dynamic_prefix_and_more"),
        ("challenges", "0004_challenge_blood_reward"),
    ]

    operations = [
        migrations.AddField(
            model_name="challengecategory",
            name="contest",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="challenge_categories",
                to="contests.contest",
                verbose_name="所属比赛",
            ),
        ),
        migrations.AlterModelOptions(
            name="challengecategory",
            options={"ordering": ["contest_id", "name"], "verbose_name": "题目分类", "verbose_name_plural": "题目分类"},
        ),
        migrations.AlterField(
            model_name="challengecategory",
            name="name",
            field=models.CharField(max_length=80, verbose_name="分类名称"),
        ),
        migrations.AlterField(
            model_name="challengecategory",
            name="slug",
            field=models.SlugField(max_length=80, verbose_name="分类标识"),
        ),
        migrations.AlterUniqueTogether(
            name="challengecategory",
            unique_together={("contest", "slug")},
        ),
    ]
