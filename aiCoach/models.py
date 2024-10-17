import uuid
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone

# Category types for classification
CATEGORY_TYPES = [
    ('OPENING', 'Opening'),
    ('QUESTIONING', 'Questioning'),
    ('PRESENTING', 'Presenting'),
    ('CLOSING', 'Closing'),
    ('OUTCOME', 'Outcome'),
]

# Define category levels
LEVEL_CHOICES = [(i, str(i)) for i in range(1, 5)]  # Creates tuples: [(1, '1'), (2, '2'), (3, '3'), (4, '4')]


# User Model
class User(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)  # Automatically updates when a record is saved

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"



# Category Model
class Category(models.Model):
    category = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    definition = models.TextField()
    instruction = models.TextField( blank=True, null=True)
    examples = models.TextField( blank=True, null=True)
    invalid_examples = models.TextField( blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category}"


# Category Level Model
class CategoryLevel(models.Model):
    category = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    level = models.IntegerField(choices=LEVEL_CHOICES) 
    description = models.TextField( blank=True, null=True)
    examples = models.TextField( blank=True, null=True)
    invalid_examples = models.TextField( blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('category', 'level')  # Prevent duplicate levels for the same category

    # def __str__(self):
    #     return f"{self.category} - Level: {self.level}"


# Category Level Example Model
class CategoryLevelExample(models.Model):
    category_level = models.ForeignKey(CategoryLevel, on_delete=models.CASCADE, related_name='level_examples')  # Renamed from 'examples' to 'level_examples'
    example_text = models.TextField()
    reason = models.TextField( blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Examples of {self.category_level.category.category} - Level: {self.category_level.level}"


# User call statement with level Model
class UserCallStatementsWithLevel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='last_calls')
    statement = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    level = models.TextField()
    reason = models.TextField( blank=True, null=True)
    confidence_score = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Calls of {self.user.first_name} {self.user.last_name}, with {self.category}"


# UserGoal Model
class UserGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    category = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    initial_level = models.TextField( blank=True, null=True)
    current_level = models.TextField( blank=True, null=True)
    goal_level = models.TextField()
    goal_confirmation = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'is_active'], name='unique_category_is_active')
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.category} - Goal Level: {self.goal_level}"


# UserPerformanceData Model
class UserPerformanceData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance_data')
    category = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    date = models.DateField()
    not_observed = models.FloatField( blank=True, null=True)
    foundational = models.FloatField( blank=True, null=True)
    developing = models.FloatField( blank=True, null=True)
    accomplished = models.FloatField( blank=True, null=True)
    combined_DA = models.FloatField( blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} performance data of {self.category}"


# UserConversationHistory Model
class UserConversationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversation_history')
    chat_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    messages = models.JSONField(default=list)
    chat_label = models.CharField(max_length=100, blank=True, null=True)
    summary = models.JSONField(default=dict)
    isGoalStepCompleted: bool = models.BooleanField(default=False)
    isRealityStepCompleted: bool = models.BooleanField(default=False)
    isOptionStepCompleted: bool = models.BooleanField(default=False)
    isOptionImprovementStepCompleted: bool = models.BooleanField(default=False)
    isWillStepCompleted: bool = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation history for {self.user.first_name} {self.user.last_name}"



