from django.contrib import admin

from .models import Answer, AnswerLike, Question, QuestionLike, Tag


class AnswerInline(admin.TabularInline):
    model = Answer
    fields = ('author', 'text', 'is_correct', 'created_at')
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')
    search_fields = ('title', 'author__username')
    list_filter = ('created_at',)
    list_select_related = ('author',)
    autocomplete_fields = ('author', 'tags')
    show_full_result_count = False
    inlines = (AnswerInline,)

    def get_inlines(self, request, obj=None):
        return self.inlines if obj is not None else ()


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'author', 'is_correct', 'created_at')
    search_fields = ('text', 'question__title', 'author__username')
    list_filter = ('is_correct', 'created_at')
    list_select_related = ('question', 'author')
    autocomplete_fields = ('question', 'author')
    show_full_result_count = False


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('created_at',)


@admin.register(QuestionLike)
class QuestionLikeAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'value', 'created_at')
    search_fields = ('question__title', 'user__username')
    list_filter = ('value', 'created_at')
    list_select_related = ('question', 'user')
    autocomplete_fields = ('question', 'user')
    show_full_result_count = False


@admin.register(AnswerLike)
class AnswerLikeAdmin(admin.ModelAdmin):
    list_display = ('answer', 'user', 'value', 'created_at')
    search_fields = ('answer__text', 'user__username')
    list_filter = ('value', 'created_at')
    list_select_related = ('answer', 'user')
    autocomplete_fields = ('answer', 'user')
    show_full_result_count = False
