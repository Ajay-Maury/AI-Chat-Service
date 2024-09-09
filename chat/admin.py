from django.contrib import admin
from .models import User, Message

# Define an admin class for the User model
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'is_active', 'first_name', 'last_name', 'created_at', 'updated_at')
    search_fields = ('email', 'first_name', 'last_name')

# Register the User model with the admin site
admin.site.register(User, UserAdmin)


# Define an admin class for the Message model
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user__id', 'chat_id', 'chat_label', 'messages', 'is_active', 'updated_at')
    search_fields = ('user__id','chat_id', 'is_active', 'chat_label')

# Register the Message model with the admin site
admin.site.register(Message, MessageAdmin)
