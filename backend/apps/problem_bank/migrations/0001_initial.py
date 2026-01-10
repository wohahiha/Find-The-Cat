from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProblemBank",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, unique=True, verbose_name="题库名称")),
                ("slug", models.SlugField(max_length=200, unique=True, verbose_name="标识")),
                ("description", models.TextField(blank=True, verbose_name="题库描述")),
                ("is_public", models.BooleanField(default=False, verbose_name="是否公开")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "题库",
                "verbose_name_plural": "题库",
                "ordering": ["-created_at", "name"],
            },
        ),
        migrations.CreateModel(
            name="BankCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, verbose_name="分类名称")),
                ("slug", models.SlugField(max_length=80, verbose_name="标识")),
                ("bank", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="categories", to="problem_bank.problembank", verbose_name="所属题库")),
            ],
            options={
                "verbose_name": "题库分类",
                "verbose_name_plural": "题库分类",
                "ordering": ["name"],
                "unique_together": {("bank", "slug"), ("bank", "name")},
            },
        ),
        migrations.CreateModel(
            name="BankChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="题目标题")),
                ("slug", models.SlugField(max_length=200, verbose_name="题目标识")),
                ("short_description", models.CharField(blank=True, max_length=255, verbose_name="题目简介")),
                ("content", models.TextField(verbose_name="题目内容")),
                ("difficulty", models.CharField(choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], default="medium", max_length=20, verbose_name="难度")),
                ("flag", models.CharField(max_length=256, verbose_name="Flag")),
                ("flag_case_insensitive", models.BooleanField(default=True, verbose_name="忽略大小写")),
                ("flag_type", models.CharField(choices=[("static", "静态 Flag"), ("dynamic", "动态 Flag")], default="static", max_length=16, verbose_name="Flag 类型")),
                ("dynamic_prefix", models.CharField(blank=True, default="FLAG", max_length=64, verbose_name="Flag 前缀")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否可见")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("author", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bank_challenges", to=settings.AUTH_USER_MODEL, verbose_name="作者")),
                ("bank", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="challenges", to="problem_bank.problembank", verbose_name="所属题库")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="challenges", to="problem_bank.bankcategory", verbose_name="分类")),
            ],
            options={
                "verbose_name": "题库题目",
                "verbose_name_plural": "题库题目",
                "ordering": ["bank", "slug"],
                "unique_together": {("bank", "slug"), ("bank", "title")},
            },
        ),
        migrations.CreateModel(
            name="BankSolve",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("solved_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="解题时间")),
                ("challenge", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="solves", to="problem_bank.bankchallenge", verbose_name="题目")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bank_solves", to=settings.AUTH_USER_MODEL, verbose_name="用户")),
            ],
            options={
                "verbose_name": "题库解题记录",
                "verbose_name_plural": "题库解题记录",
                "ordering": ["solved_at"],
                "unique_together": {("challenge", "user")},
            },
        ),
        migrations.CreateModel(
            name="BankHint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="提示标题")),
                ("content", models.TextField(verbose_name="提示内容")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="排序")),
                ("challenge", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hints", to="problem_bank.bankchallenge", verbose_name="题目")),
            ],
            options={
                "verbose_name": "题库提示",
                "verbose_name_plural": "题库提示",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="BankAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="附件名称")),
                ("url", models.URLField(max_length=500, verbose_name="附件链接")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="排序")),
                ("challenge", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="problem_bank.bankchallenge", verbose_name="题目")),
            ],
            options={
                "verbose_name": "题库附件",
                "verbose_name_plural": "题库附件",
                "ordering": ["order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="banksolve",
            index=models.Index(fields=["challenge", "user"], name="problem_ba_challen_9ce2a9_idx"),
        ),
    ]
