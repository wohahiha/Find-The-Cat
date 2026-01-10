from django.db import migrations, models


def mark_challenges_with_machine(apps, schema_editor):
    """
    数据迁移：已有靶机配置的题目自动标记为启用靶机，避免前台误判
    """
    Challenge = apps.get_model("challenges", "Challenge")
    ChallengeMachineConfig = apps.get_model("machines", "ChallengeMachineConfig")
    ids = list(
        ChallengeMachineConfig.objects.values_list("challenge_id", flat=True)
    )
    if ids:
        Challenge.objects.filter(id__in=ids).update(has_machine=True)


def reset_has_machine(apps, schema_editor):
    """回滚时统一重置标记"""
    Challenge = apps.get_model("challenges", "Challenge")
    Challenge.objects.update(has_machine=False)


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0009_alter_challenge_author_alter_challenge_base_points_and_more"),
        ("machines", "0007_alter_challengemachineconfig_port_cache_ttl"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="has_machine",
            field=models.BooleanField(
                default=False,
                help_text="开启后需要配置靶机模板；关闭则视为纯题目，不提供靶机实例",
                verbose_name="启用靶机",
            ),
        ),
        migrations.RunPython(mark_challenges_with_machine, reverse_code=reset_has_machine),
    ]
