from django.db import migrations


REMOVED_KEYS = [
    "DOCKER_IMAGE_PREFIX",
    "DOCKER_IMAGE_TAG",
    "DOCKER_CONTAINER_PORT",
]


def delete_removed_configs(apps, schema_editor):
    SystemConfig = apps.get_model("configs", "SystemConfig")
    SystemConfig.objects.filter(key__in=REMOVED_KEYS).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("configs", "0011_systemlogcategory"),
    ]

    operations = [
        migrations.RunPython(delete_removed_configs, reverse_code=noop),
    ]
