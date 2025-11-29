from __future__ import annotations

from django.contrib import admin, messages
from django import forms
from django.forms.models import BaseInlineFormSet
from django.urls import reverse, path
from django.http import JsonResponse

from apps.contests.models import Contest
from apps.challenges.models import Challenge, ChallengeCategory
from apps.problem_bank.importer import BankChallengeImporter

from .models import ProblemBank, BankCategory, BankChallenge


class BankCategoryInline(admin.TabularInline):
    """题库内分类配置：在题库详情页按需维护"""

    model = BankCategory
    extra = 0
    fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class BankChallengeInlineForm(forms.ModelForm):
    """题库题目内联表单：支持选择比赛/分类/题目导入"""

    contest = forms.ModelChoiceField(
        queryset=Contest.objects.none(),
        required=False,
        label="比赛",
        help_text="请选择需要导入题目的比赛，仅支持已结束的比赛",
    )
    contest_category = forms.ModelChoiceField(
        queryset=ChallengeCategory.objects.none(),
        required=False,
        label="题目分类",
        help_text="可选：指定比赛中的分类；为空则导入比赛所有题目",
    )
    contest_challenge = forms.ModelChoiceField(
        queryset=Challenge.objects.none(),
        required=False,
        label="具体题目",
        help_text="可选：指定某道题；为空则导入所选分类下全部题目",
    )

    class Meta:
        model = BankChallenge
        fields = ("title", "category", "is_active")
        widgets = {
            "title": forms.TextInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, *args, bank: ProblemBank | None = None, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank = bank
        self.request = request
        self.fields["title"].required = False
        self.fields["title"].label = "题目标题"
        self.fields["category"].label = "题库分类"
        self.fields["category"].required = False
        if bank:
            self.fields["category"].queryset = bank.categories.all().order_by("name")
        else:
            self.fields["category"].queryset = BankCategory.objects.none()
        self.fields["is_active"].label = "是否可见"

        self.fields["contest"].widget.attrs.setdefault(
            "data-category-url",
            reverse("admin:challenges_challenge_category_options"),
        )
        self.fields["contest"].widget.attrs.setdefault(
            "data-challenge-url",
            reverse("admin:problem_bank_problemchallenge_options"),
        )
        self.fields["contest"].widget.attrs.setdefault("data-field", "contest")
        self.fields["contest_category"].widget.attrs.setdefault("data-field", "contest_category")
        self.fields["contest_challenge"].widget.attrs.setdefault("data-field", "contest_challenge")

        self.fields["contest"].queryset = Contest.objects.order_by("-end_time", "name")
        contest_id = self._current_selection("contest")
        category_id = self._current_selection("contest_category")
        challenge_id = self._current_selection("contest_challenge")
        contest = None
        if contest_id:
            contest = Contest.objects.filter(pk=contest_id).first()
        if contest:
            self.fields["contest_category"].queryset = ChallengeCategory.objects.filter(contest=contest).order_by(
                "name"
            )
            self.fields["contest_challenge"].queryset = Challenge.objects.filter(contest=contest).order_by("slug")
        else:
            self.fields["contest_category"].queryset = ChallengeCategory.objects.none()
            self.fields["contest_challenge"].queryset = Challenge.objects.none()
        if contest and category_id:
            category = ChallengeCategory.objects.filter(pk=category_id, contest=contest).first()
            if category:
                self.fields["contest_challenge"].queryset = self.fields["contest_challenge"].queryset.filter(
                    category=category
                )
        self.fields["contest_category"].widget.attrs.setdefault("data-initial", str(category_id or ""))
        self.fields["contest_challenge"].widget.attrs.setdefault("data-initial", str(challenge_id or ""))

        if self.instance and self.instance.pk:
            # 编辑已有题目：隐藏导入字段，仅允许调整分类与可见性
            for field in ("contest", "contest_category", "contest_challenge"):
                self.fields[field].widget = forms.HiddenInput()
                self.fields[field].required = False
            self.fields["title"].widget.attrs["readonly"] = True
        else:
            self.fields["contest"].required = True

    def _current_selection(self, field_name: str) -> int | None:
        key = self.add_prefix(field_name)
        value = self.data.get(key) if self.data else None
        if not value:
            value = self.initial.get(field_name)
        try:
            return int(value) if value else None
        except (TypeError, ValueError):
            return None

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk:
            return cleaned
        contest = cleaned.get("contest")
        category = cleaned.get("contest_category")
        challenge = cleaned.get("contest_challenge")
        if not contest:
            raise forms.ValidationError("请选择比赛")
        if category and category.contest_id != contest.id:
            raise forms.ValidationError("请选择该比赛下的题目分类")
        if challenge and challenge.contest_id != contest.id:
            raise forms.ValidationError("请选择该比赛下的题目")
        if challenge and category and challenge.category_id != category.id:
            raise forms.ValidationError("题目不属于所选分类")
        cleaned["source_contest"] = contest
        cleaned["source_category"] = category
        cleaned["source_challenge"] = challenge
        return cleaned


class BankChallengeInlineFormSet(BaseInlineFormSet):
    """自定义 formset：向表单传入题库实例"""

    def __init__(self, *args, bank: ProblemBank | None = None, request=None, **kwargs):
        self.bank = bank
        self.request = request
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["bank"] = self.bank
        kwargs["request"] = self.request
        return super()._construct_form(i, **kwargs)


class BankChallengeInline(admin.TabularInline):
    """题库题目导入：通过选择比赛/分类/题目批量复制"""

    model = BankChallenge
    form = BankChallengeInlineForm
    formset = BankChallengeInlineFormSet
    extra = 1
    fields = ("title", "contest", "contest_category", "contest_challenge", "category", "is_active")
    verbose_name_plural = "题库题目（从比赛导入）"

    class Media:
        js = ("problem_bank/js/bank_inline.js",)

    def get_formset(self, request, obj=None, **kwargs):
        FormSet = super().get_formset(request, obj, **kwargs)

        class WrappedFormSet(FormSet):
            def __init__(self2, *args, **kw):
                kw["bank"] = obj
                kw["request"] = request
                super().__init__(*args, **kw)

        return WrappedFormSet


@admin.register(ProblemBank)
class ProblemBankAdmin(admin.ModelAdmin):
    """题库后台：仅保留“题库”板块，分类与题目在题库详情内维护"""

    list_display = ("name", "is_public", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_public",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BankCategoryInline, BankChallengeInline]
    challenge_importer = BankChallengeImporter.default()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "name": "题库名称，对外展示使用，需保证唯一且易于辨认",
            "slug": "题库唯一标识，用于接口/URL，建议使用英文与短横线组合",
            "description": "题库简介或备注信息，可为空，便于运营记录用途",
            "is_public": "是否对前台选手开放；不公开时仅管理员可见题库内容",
        }
        for field, text in help_texts.items():
            if field in form.base_fields:
                form.base_fields[field].help_text = text
        return form

    def save_formset(self, request, form, formset, change):
        if isinstance(formset, BankChallengeInlineFormSet):
            self._save_challenge_inline(request, form.instance, formset)
            return
        super().save_formset(request, form, formset, change)

    def get_inline_instances(self, request, obj=None):
        """新增题库时不展示题目导入 inline，避免未保存实例出现空表单"""
        instances = []
        for inline_class in self.inlines:
            if inline_class is BankChallengeInline and obj is None:
                continue
            inline = inline_class(self.model, self.admin_site)
            instances.append(inline)
        return instances

    def _save_challenge_inline(self, request, bank: ProblemBank, formset: BankChallengeInlineFormSet):
        total_imported = 0
        for inline_form in formset.forms:
            if not inline_form.has_changed():
                continue
            if not inline_form.cleaned_data:
                continue
            if inline_form.cleaned_data.get("DELETE"):
                if inline_form.instance.pk:
                    inline_form.instance.delete()
                continue
            if inline_form.instance and inline_form.instance.pk:
                inline_form.save()
                continue
            contest = inline_form.cleaned_data.get("source_contest")
            category = inline_form.cleaned_data.get("source_category")
            challenge = inline_form.cleaned_data.get("source_challenge")
            target_category = inline_form.cleaned_data.get("category")
            is_active = inline_form.cleaned_data.get("is_active", True)
            if not contest:
                inline_form.add_error("contest", "请选择比赛")
                continue
            if not contest.has_ended:
                inline_form.add_error("contest", "比赛尚未结束，请先终止比赛后再导入")
                continue
            try:
                created = self._import_challenges(
                    bank=bank,
                    contest=contest,
                    contest_category=category,
                    challenge=challenge,
                    target_category=target_category,
                    is_active=is_active,
                )
            except forms.ValidationError as exc:
                inline_form.add_error(None, exc)
                continue
            total_imported += len(created)
        if total_imported:
            self.message_user(request, f"已导入 {total_imported} 道题目", level=messages.SUCCESS)

    def _import_challenges(
            self,
            *,
            bank: ProblemBank,
            contest: Contest,
            contest_category: ChallengeCategory | None,
            challenge: Challenge | None,
            target_category: BankCategory | None,
            is_active: bool,
    ) -> list[BankChallenge]:
        qs = Challenge.objects.filter(contest=contest)
        if contest_category:
            qs = qs.filter(category=contest_category)
        if challenge:
            qs = qs.filter(pk=challenge.pk)
        qs = qs.select_related("category", "author").prefetch_related("attachments", "hints")
        if not qs.exists():
            raise forms.ValidationError("所选条件下没有可导入的题目")
        return self.challenge_importer.copy_many(
            bank=bank,
            challenges=qs,
            target_category=target_category,
            is_active=is_active,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "challenge-options/",
                self.admin_site.admin_view(self.challenge_options_view),
                name="problem_bank_problemchallenge_options",
            ),
        ]
        return custom + urls

    def challenge_options_view(self, request):
        contest_id = request.GET.get("contest_id")
        if not contest_id:
            return JsonResponse({"results": []})
        qs = Challenge.objects.filter(contest_id=contest_id)
        category_id = request.GET.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)
        results = [
            {
                "id": str(item.id),
                "title": item.title,
                "slug": item.slug,
            }
            for item in qs.order_by("slug", "id")
        ]
        return JsonResponse({"results": results})

# 其余模型不单独出现在后台菜单，避免多余板块：
# - BankCategory/BankChallenge 通过题库内联管理
# - BankSolve 仅用于用户已解标记，无需后台查询
