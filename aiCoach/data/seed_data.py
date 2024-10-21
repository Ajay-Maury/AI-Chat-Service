import uuid
from django.utils import timezone
from aiCoach.models import User, Category, CategoryLevel, UserCallStatementsWithLevel, UserGoal, UserPerformanceData

# Create User
user = User.objects.create(
    email='johndoe@email.com',
    first_name='John',
    last_name='Doe',
    is_active=True
)
user.set_password('12345')
user.save()

# Create Categories and Category Levels
category_data = [
    {
        'category': 'OPENING',
        'definition': 'Opening stage of a sales call.',
        'instruction': 'Start the conversation.',
        'examples': 'Introduce yourself.',
        'invalid_examples': 'Being vague.'
    },
    {
        'category': 'QUESTIONING',
        'definition': 'Questioning during a sales call.',
        'instruction': 'Ask relevant questions.',
        'examples': 'Ask about needs.',
        'invalid_examples': 'Ask irrelevant questions.'
    },
    {
        'category': 'PRESENTING',
        'definition': 'Presenting the product.',
        'instruction': 'Present the product.',
        'examples': 'Provide product details.',
        'invalid_examples': 'Focus on irrelevant points.'
    },
    {
        'category': 'CLOSING',
        'definition': 'Closing the sale.',
        'instruction': 'Conclude the conversation.',
        'examples': 'Ask for the sale.',
        'invalid_examples': 'Being aggressive.'
    },
    {
        'category': 'OUTCOME',
        'definition': 'Final outcomes of the call.',
        'instruction': 'Wrap up the call.',
        'examples': 'Summarize the call.',
        'invalid_examples': 'Leave it open-ended.'
    }
]

for category_info in category_data:
    category = Category.objects.create(
        category=category_info['category'],
        definition=category_info['definition'],
        instruction=category_info['instruction'],
        examples=category_info['examples'],
        invalid_examples=category_info['invalid_examples'],
        is_active=True
    )
    for level in range(1, 5): # Create Category Levels for each category
        CategoryLevel.objects.create(
            category=category_info['category'],  # Pass the actual Category instance
            level=level,
            description=f"Description for level {level} of {category_info['category']}.",
            examples=f"Examples for level {level} of {category_info['category']}.",
            invalid_examples=f"Invalid examples for level {level} of {category_info['category']}.",
            is_active=True
        )

# Create User Performance Data
performance_data = [
    {"date": "2024-02-12", "category": "OPENING", "not_observed": 0.0, "foundational": 90.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
    {"date": "2024-05-15", "category": "OPENING", "not_observed": 0.0, "foundational": 90.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
    {"date": "2024-02-12", "category": "QUESTIONING", "not_observed": 0.0, "foundational": 90.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
    {"date": "2024-05-15", "category": "QUESTIONING", "not_observed": 0.0, "foundational": 80.0, "developing": 10.0, "accomplished": 10.0, "combined_DA": 20.0},
    {"date": "2024-02-12", "category": "PRESENTING", "not_observed": 0.0, "foundational": 80.0, "developing": 10.0, "accomplished": 10.0, "combined_DA": 20.0},
    {"date": "2024-05-15", "category": "PRESENTING", "not_observed": 0.0, "foundational": 80.0, "developing": 10.0, "accomplished": 10.0, "combined_DA": 20.0},
    {"date": "2024-02-12", "category": "CLOSING", "not_observed": 10.0, "foundational": 80.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
    {"date": "2024-05-15", "category": "CLOSING", "not_observed": 10.0, "foundational": 80.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
    {"date": "2024-02-12", "category": "OUTCOME", "not_observed": 10.0, "foundational": 80.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
    {"date": "2024-05-15", "category": "OUTCOME", "not_observed": 10.0, "foundational": 80.0, "developing": 10.0, "accomplished": 0.0, "combined_DA": 10.0},
]

for data in performance_data:
    UserPerformanceData.objects.create(
        user=user,
        category=data["category"],
        date=data["date"],
        not_observed=data["not_observed"],
        foundational=data["foundational"],
        developing=data["developing"],
        accomplished=data["accomplished"],
        combined_DA=data["combined_DA"],
        is_active=True
    )

# Create User Call Statements with Level
call_statements = [
    {
        "statement": "Excellent, well I haven't spoken to you about this before but I want to show you some exciting information about Gaboderm ointment for your moderate to severe eczema patients.",
        "category": "OPENING",
        "level": "2",
        "reason": "The REP is sharing information about Gaboderm ointment.",
        "confidence_score": 90
    },
    {
        "statement": "Who is it that mainly sees the eczema patients here?",
        "category": "QUESTIONING",
        "level": "2",
        "reason": "Business information request about responsibilities.",
        "confidence_score": 90
    },
    {
        "statement": "If you look at this graph, this is a study comparing Gaboderm against adalimumab and we showed equivalent efficacy.",
        "category": "PRESENTING",
        "level": "2",
        "reason": "The statement presents research-based information.",
        "confidence_score": 90
    },
    {
        "statement": "So today I hope I've answered your questions regarding efficacy and side effects, can we book another meeting?",
        "category": "CLOSING",
        "level": "2",
        "reason": "Asking to book another meeting.",
        "confidence_score": 90
    },
    {
        "statement": "Outcome confirmed to book another meeting.",
        "category": "OUTCOME",
        "level": "2",
        "reason": "Agrees to another meeting.",
        "confidence_score": 90
    }
]

for call in call_statements:
    UserCallStatementsWithLevel.objects.create(
        user=user,
        statement=call["statement"],
        category=call["category"],
        level=call["level"],
        reason=call["reason"],
        confidence_score=call["confidence_score"],
        is_active=True
    )

# Create User Goal
UserGoal.objects.create(
    user=user,
    category="QUESTIONING",
    initial_level="8% DEVELOPING",
    current_level="22% DEVELOPING or ACCOMPLISHED",
    goal_level="35% DEVELOPING or ACCOMPLISHED",
    goal_confirmation=True,
    is_active=True
)

print("Data seeded successfully!")
