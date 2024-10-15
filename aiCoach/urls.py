# urls.py
from django.urls import path
from aiCoach.views import (coach_chat, create_category_level_example_view,
  create_category_level_view, create_category_view, create_user_call_statements_view,
  create_user_performance_data_view, create_user_goal_view, get_categories_view,
  get_category_level_examples_view, get_category_levels_view, get_chat, get_last_calls_view,
  get_performance_data_view, get_user, get_user_chat_history, get_user_goals_view, login_signup)

urlpatterns = [
    path('categories/', get_categories_view, name='get-categories'),
    path('categories/create/', create_category_view, name='create-category'),
    
    path('category-levels/', get_category_levels_view, name='get-category-levels'),
    path('category-levels/create/', create_category_level_view, name='create-category-level'),

    path('category-level-examples/', get_category_level_examples_view, name='get-category-level-examples'),
    path('category-level-examples/create/', create_category_level_example_view, name='create-category-level-example'),

    path('last-calls/', get_last_calls_view, name='get-last-calls'),
    path('last-calls/create/', create_user_call_statements_view, name='create-last-call'),

    path('user-goals/', get_user_goals_view, name='get-user-goals'),
    path('user-goals/create/', create_user_goal_view, name='create-user-goal'),

    path('performance-data/', get_performance_data_view, name='get-performance-data'),
    path('performance-data/create/', create_user_performance_data_view, name='create-performance-data'),

    path('login/', login_signup, name='login'),
    path('get-user/', get_user, name='get-user'),
    path('chat/', coach_chat, name='coach-chat'),

    path('chat-messages/<str:chat_id>/', get_chat, name='conversation_history_messages'),
    path('chat-history/<int:user_id>/', get_user_chat_history, name='user_conversation_history'),

]
