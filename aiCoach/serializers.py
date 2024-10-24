# serializers.py
from rest_framework import serializers
from .models import Category, CategoryLevel, CategoryLevelExample, CoachingPrompt, User, UserCallStatementsWithLevel, UserConversationHistory, UserGoal, UserPerformanceData

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'is_active', 'first_name', 'last_name']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class CategoryLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryLevel
        fields = '__all__'


class CategoryLevelExampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryLevelExample
        fields = '__all__'


class UserCallStatementsWithLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCallStatementsWithLevel
        fields = '__all__'


class UserGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGoal
        fields = '__all__'


class UserPerformanceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPerformanceData
        fields = '__all__'

class UserConversationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConversationHistory
        fields = ['chat_id', 'messages', 'summary', 'chat_label', 'isGoalStepCompleted', 'isRealityStepCompleted', 'isOptionStepCompleted', 'isOptionImprovementStepCompleted', 'isWillStepCompleted', 'is_active']


class CoachingPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachingPrompt
        fields = '__all__'

