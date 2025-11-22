from django.db import migrations


def ensure_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    from apps.common.permission_sets import GROUP_PERMISSION_PRESETS

    for name, perm_keys in GROUP_PERMISSION_PRESETS.items():
        group, _ = Group.objects.get_or_create(name=name)
        perm_ids = []
        for app_label, codename in perm_keys:
            perm = Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).first()
            if perm:
                perm_ids.append(perm.pk)
        if perm_ids:
            group.permissions.set(perm_ids)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_create_default_groups"),
    ]

    operations = [
        migrations.RunPython(ensure_default_groups, migrations.RunPython.noop),
    ]
