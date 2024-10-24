from django.contrib import admin
from .models import Category, CategoryLevel, CategoryLevelExample, CoachingPrompt, User, UserCallStatementsWithLevel, UserGoal, UserPerformanceData, UserConversationHistory

# Custom admin for user model
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'first_name', 'last_name', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')


# Custom admin for Category model
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'definition', 'is_active')
    search_fields = ('category',)
    list_filter = ('is_active',)
    ordering = ('category',)

# Custom admin for CategoryLevel model
class CategoryLevelAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'level', 'description', 'is_active')
    search_fields = ('category__category', 'level')
    list_filter = ('category', 'is_active')
    ordering = ('category', 'level')

# Custom admin for CategoryLevelExample model
class CategoryLevelExampleAdmin(admin.ModelAdmin):
    list_display = ('id', 'category_level', 'example_text')
    search_fields = ('category_level__category__category', 'example_text')
    list_filter = ('category_level__category',)

# Custom admin for UserCallStatementsWithLevel model
class UserCallStatementsWithLevelAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'statement', 'level', 'confidence_score', 'is_active')
    search_fields = ('user__id', 'user__first_name', 'user__last_name', 'statement', 'category', 'level')
    list_filter = ('user__id', 'category', 'is_active')
    ordering = ('user__id', 'category')

# Custom admin for UserGoal model
class UserGoalAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'initial_level', 'current_level', 'goal_level', 'goal_confirmation', 'is_active')
    search_fields = ('user__id', 'user__first_name', 'user__last_name', 'category')
    list_filter = ('user__id', 'category', 'goal_confirmation', 'is_active')
    ordering = ('user__id', 'category')

# Custom admin for UserPerformanceData model
class UserPerformanceDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'category', 'date')
    list_filter = ('category', 'date', 'is_active')
    ordering = ('user__id', 'date', 'category')

# Custom admin for UserConversationHistory model
class UserConversationHistoryAdmin(admin.ModelAdmin):
    list_display = ('chat_id', 'user', 'messages', 'is_active', )
    search_fields = ('user__id', 'user__first_name', 'user__last_name',"chat_id", )
    list_filter = ('chat_id', 'isGoalStepCompleted', 'isRealityStepCompleted', 'isOptionStepCompleted', 'isWillStepCompleted', 'is_active')
    ordering = ('user__id', 'created_at')

# Custom admin for CoachingPrompt model
class CoachingPromptAdmin(admin.ModelAdmin):
    list_display = ('category', 'prompt', 'is_active', )
    search_fields = ('category', 'is_active')
    list_filter = ('category', 'is_active')
    ordering = ('category', 'created_at')


# Register all models with the admin site
admin.site.register(User, UserAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(CategoryLevel, CategoryLevelAdmin)
admin.site.register(CategoryLevelExample, CategoryLevelExampleAdmin)
admin.site.register(UserCallStatementsWithLevel, UserCallStatementsWithLevelAdmin)
admin.site.register(UserGoal, UserGoalAdmin)
admin.site.register(UserPerformanceData, UserPerformanceDataAdmin)
admin.site.register(UserConversationHistory, UserConversationHistoryAdmin)
admin.site.register(CoachingPrompt, CoachingPromptAdmin)
