from django.db import migrations


def ensure_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    from apps.common.permission_sets import GROUP_PERMISSION_PRESETS

    for name, perm_keys in GROUP_PERMISSION_PRESETS.items():
        group, _ = Group.objects.get_or_create(name=name)
        perm_ids = []
        for key in perm_keys:
            if isinstance(key, str) and "." in key:
                app_label, codename = key.split(".", 1)
            elif isinstance(key, (tuple, list)) and len(key) == 2:
                app_label, codename = key
            else:
                continue
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
